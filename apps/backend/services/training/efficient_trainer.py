"""
Efficient Training Service
Optimized for fast training with minimal GPU/CPU consumption
"""

import math
import os
import threading

import torch
import logging
from pathlib import Path
from typing import Dict, Any, Callable, Optional

from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    TrainingArguments,
    Trainer,
)
from peft import (
    LoraConfig,
    get_peft_model,
    prepare_model_for_kbit_training,
)

logger = logging.getLogger(__name__)



def _cached_first(load, name_or_path, **kwargs):
    """
    ``load(name_or_path, **kwargs)`` from the local Hugging Face cache when the model is already
    downloaded, so training works offline (and doesn't stall on flaky networks). Kept local to
    this module because it also runs on remote GPU workers (see core/utils/hub.py).
    """
    if os.path.exists(name_or_path):
        return load(name_or_path, **kwargs)
    try:
        return load(name_or_path, local_files_only=True, **kwargs)
    except (OSError, ValueError):
        return load(name_or_path, **kwargs)

class EfficientTrainer:
    """
    Optimized trainer with minimal resource consumption
    
    Features:
    - QLoRA (4-bit quantization) for 50-75% less memory
    - Gradient checkpointing for memory efficiency
    - Flash Attention 2 support
    - Auto batch size adjustment
    - CPU offloading when needed
    """
    
    def __init__(
        self,
        job_id: str,
        model_name: str,
        dataset_path: str,
        output_dir: str,
        training_method: str = 'qlora',
        lora_config: Optional[Dict[str, Any]] = None,
        training_config: Optional[Dict[str, Any]] = None,
        progress_callback: Optional[Callable] = None,
        log_callback: Optional[Callable] = None,
        should_cancel: Optional[Callable] = None,
    ):
        # Validate required parameters
        if not model_name:
            raise ValueError(f"model_name is required but got: {repr(model_name)}")
        if not dataset_path:
            raise ValueError(f"dataset_path is required but got: {repr(dataset_path)}")
        
        self.job_id = job_id
        self.model_name = model_name
        self.dataset_path = dataset_path
        
        # Ensure output_dir is properly set (handle None or empty string with fallback)
        if not output_dir:
            output_dir = f'models/{job_id}'
            logger.warning(f"output_dir was None/empty, using default: {output_dir}")
        
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        self.progress_callback = progress_callback
        self.log_callback = log_callback
        self.should_cancel = should_cancel
        
        # Training method (qlora, lora, or full)
        self.training_method = training_method.lower()
        
        # Default LoRA config (optimized for efficiency)
        # Ensure lora_config is a dict, not None
        if lora_config is None:
            lora_config = {}
        
        self.lora_config = {
            'r': lora_config.get('r', 16),
            'lora_alpha': lora_config.get('lora_alpha', 32),
            'lora_dropout': lora_config.get('lora_dropout', 0.05),
            'target_modules': lora_config.get('target_modules', None),
        }
        
        # Optimize training config based on method (faster for fine-tuning, balanced for scratch)
        # Base models train faster with higher learning rates and fewer epochs
        # QLoRA is fastest, LoRA is fast, Full fine-tuning is moderate
        if training_method == 'qlora':
            default_epochs = 2  # QLoRA converges very fast
            default_lr = 2e-4
            default_batch = 8  # Can handle larger batches with quantization
        elif training_method == 'lora':
            default_epochs = 3  # LoRA needs slightly more
            default_lr = 1e-4
            default_batch = 4
        else:  # full fine-tuning
            default_epochs = 5  # Full fine-tuning needs more epochs
            default_lr = 5e-5  # Lower LR for stability
            default_batch = 2  # Smaller batches due to memory
        
        # Ensure training_config is a dict, not None
        if training_config is None:
            training_config = {}
        
        def opt(key: str, default: Any) -> Any:
            """Explicit None (an omitted optional field) means "use the default"."""
            value = training_config.get(key)
            return default if value is None else value

        self.training_config = {
            'num_epochs': opt('num_epochs', default_epochs),
            'batch_size': opt('batch_size', default_batch),
            'learning_rate': opt('learning_rate', default_lr),
            # None -> warm up over 3% of the run (a fixed step count can exceed a small run entirely)
            'warmup_steps': training_config.get('warmup_steps'),
            'gradient_accumulation_steps': opt('gradient_accumulation_steps', 1),
            'max_grad_norm': opt('max_grad_norm', 0.3),
            'weight_decay': opt('weight_decay', 0.01),
            'save_steps': opt('save_steps', 100),
            'logging_steps': opt('logging_steps', 5),
            'max_seq_length': opt('max_seq_length', 512),
        }
        want_8bit = bool(training_config.get('use_8bit'))
        
        # Auto-detect device
        self.device = self._detect_device()
        
        # Determine quantization based on method
        # Note: 4-bit quantization requires CUDA
        if self.training_method == 'qlora':
            if torch.cuda.is_available():
                self.use_4bit = True
                self.use_8bit = False
            else:
                # Fallback to LoRA on CPU (4-bit not supported)
                self._log("⚠️  Warning: QLoRA requires CUDA. Falling back to LoRA on CPU.")
                self.use_4bit = False
                self.use_8bit = False
        elif self.training_method == 'lora':
            self.use_4bit = False
            # 8-bit LoRA (bitsandbytes) needs CUDA; otherwise standard precision
            self.use_8bit = want_8bit and torch.cuda.is_available()
            if want_8bit and not self.use_8bit:
                self._log("⚠️  Warning: 8-bit training requires CUDA. Using standard precision LoRA.")
        else:  # full
            self.use_4bit = False
            self.use_8bit = False
        
    def _detect_device(self) -> str:
        """Auto-detect best available device"""
        if torch.cuda.is_available():
            return "cuda"
        elif hasattr(torch.backends, 'mps') and torch.backends.mps.is_available():
            return "mps"
        else:
            return "cpu"
    
    def _log(self, message: str):
        """Log message"""
        logger.info(f"[{self.job_id}] {message}")
        if self.log_callback:
            self.log_callback(self.job_id, message)
    
    def _memory_gb(self) -> Optional[float]:
        """Accelerator memory currently allocated by this process, in GB."""
        try:
            if self.device == "cuda":
                return round(torch.cuda.memory_allocated() / 1024 ** 3, 3)
            if self.device == "mps":
                return round(torch.mps.current_allocated_memory() / 1024 ** 3, 3)
        except Exception:
            pass
        return None

    def _update_progress(self, current_epoch: int, total_epochs: int, current_step: int, total_steps: int, loss: float = 0.0, metrics: Optional[Dict[str, Any]] = None):
        """Update progress"""
        if self.progress_callback:
            self.progress_callback(
                job_id=self.job_id,
                current_epoch=current_epoch,
                total_epochs=total_epochs,
                current_step=current_step,
                total_steps=total_steps,
                loss=loss,
                metrics=metrics
            )
    
    def load_model_and_tokenizer(self):
        """
        Load model based on training method (QLoRA/LoRA/Full)
        Memory efficient loading with automatic device mapping
        """
        self._log(f"Loading model: {self.model_name}")
        self._log(f"Training method: {self.training_method.upper()}")
        self._log(f"Device: {self.device}")
        
        # Load tokenizer
        self._log("📥 Loading tokenizer...")
        tokenizer = _cached_first(
            AutoTokenizer.from_pretrained,
            self.model_name,
            trust_remote_code=True,
            use_fast=True,
        )
        self._log("✓ Tokenizer loaded")
        
        # Set padding token
        if tokenizer.pad_token is None:
            tokenizer.pad_token = tokenizer.eos_token
            tokenizer.pad_token_id = tokenizer.eos_token_id
        
        # Load model based on training method
        if self.training_method == 'qlora' and self.use_4bit:
            # QLoRA: 4-bit quantization (GPU only)
            from transformers import BitsAndBytesConfig
            
            self._log("📥 Downloading/loading model weights (this may take a few minutes)...")
            self._log("💡 Tip: Large models will be cached locally for future use")
            
            bnb_config = BitsAndBytesConfig(
                load_in_4bit=True,
                bnb_4bit_quant_type="nf4",  # Normal Float 4-bit
                bnb_4bit_compute_dtype=torch.float16,
                bnb_4bit_use_double_quant=True,  # Nested quantization
            )
            
            model = _cached_first(
                AutoModelForCausalLM.from_pretrained,
                self.model_name,
                quantization_config=bnb_config,
                device_map="auto",
                trust_remote_code=True,
                dtype=torch.float16,
            )
            
            # Prepare model for k-bit training
            model = prepare_model_for_kbit_training(model)
            self._log("✓ Model loaded with 4-bit quantization (QLoRA)")
            
        elif self.training_method == 'lora' and self.use_8bit:
            from transformers import BitsAndBytesConfig

            self._log("📥 Downloading/loading model weights in 8-bit (this may take a few minutes)...")
            model = _cached_first(
                AutoModelForCausalLM.from_pretrained,
                self.model_name,
                quantization_config=BitsAndBytesConfig(load_in_8bit=True),
                device_map="auto",
                trust_remote_code=True,
                dtype=torch.float16,
            )
            model = prepare_model_for_kbit_training(model)
            self._log("✓ Model loaded with 8-bit quantization")

        elif self.training_method in ['lora', 'qlora']:
            # LoRA: Standard precision, more speed
            self._log("📥 Downloading/loading model weights (this may take a few minutes)...")
            self._log("💡 Tip: Large models will be cached locally for future use")
            
            model = _cached_first(
                AutoModelForCausalLM.from_pretrained,
                self.model_name,
                device_map="auto",
                trust_remote_code=True,
                dtype=torch.float16 if self.device == "cuda" else (
                    torch.bfloat16 if self.device == "mps" else torch.float32
                ),
            )
            self._log("✓ Model loaded for LoRA (standard precision)")
            
        else:  # full fine-tuning
            # Full: No quantization, all parameters trainable
            self._log("📥 Downloading/loading model weights (this may take a few minutes)...")
            self._log("💡 Tip: Large models will be cached locally for future use")
            
            model = _cached_first(
                AutoModelForCausalLM.from_pretrained,
                self.model_name,
                device_map="auto",
                trust_remote_code=True,
                dtype=torch.float16 if self.device == "cuda" else (
                    torch.bfloat16 if self.device == "mps" else torch.float32
                ),
            )
            self._log("✓ Model loaded for full fine-tuning")
        
        # Enable gradient checkpointing for memory efficiency (except full fine-tuning)
        if self.training_method != 'full':
            model.gradient_checkpointing_enable()
            self._log("✓ Gradient checkpointing enabled")
        
        return model, tokenizer
    
    def load_dataset_from_file(self, tokenizer):
        """Load the dataset (JSONL/JSON/CSV/Parquet/TXT), render it to text and tokenize"""
        from core.data.finetune_dataset import detect_format, load_raw, to_text_dataset

        self._log(f"Loading dataset: {self.dataset_path}")
        raw = load_raw(self.dataset_path)
        self._log(f"✓ Dataset loaded: {len(raw)} samples (format: {detect_format(raw.column_names)})")

        texts = to_text_dataset(raw, tokenizer)
        eos = tokenizer.eos_token or ""
        max_length = self.training_config['max_seq_length']

        def tokenize_function(examples):
            batch = [t if (not eos or t.endswith(eos)) else t + eos for t in examples['text']]
            return tokenizer(batch, truncation=True, max_length=max_length, padding=False)

        tokenized = texts.map(tokenize_function, batched=True, remove_columns=['text'])
        self._log("✓ Dataset tokenized")
        return tokenized

    def setup_lora(self, model):
        """Setup LoRA configuration or full fine-tuning"""
        if self.training_method == 'full':
            # Full fine-tuning: all parameters trainable
            self._log("Configuring full fine-tuning (all parameters trainable)...")
            
            # Make all parameters trainable
            for param in model.parameters():
                param.requires_grad = True
            
            # Print trainable parameters
            trainable_params = sum(p.numel() for p in model.parameters() if p.requires_grad)
            all_params = sum(p.numel() for p in model.parameters())
            
            self._log(f"✓ Full fine-tuning: {trainable_params:,} / {all_params:,} params (100%)")
            
            return model
        
        else:
            # LoRA or QLoRA
            method_display = "QLORA" if self.use_4bit else "LoRA"
            self._log(f"Configuring {method_display} adapters...")
            
            # Auto-detect target modules if not specified
            target_modules = self.lora_config.get('target_modules')
            if target_modules is None:
                # Common patterns for different model architectures
                if hasattr(model.config, 'model_type'):
                    model_type = model.config.model_type
                    if 'llama' in model_type or 'mistral' in model_type:
                        target_modules = ["q_proj", "k_proj", "v_proj", "o_proj"]
                    elif 'gpt' in model_type:
                        target_modules = ["c_attn", "c_proj"]
                    else:
                        target_modules = ["q_proj", "v_proj"]  # Generic fallback
            
            # GPT-2 style models use Conv1D layers, whose weights are stored transposed.
            model_type = getattr(model.config, 'model_type', '') or ''
            lora_config = LoraConfig(
                r=self.lora_config['r'],
                lora_alpha=self.lora_config['lora_alpha'],
                lora_dropout=self.lora_config['lora_dropout'],
                target_modules=target_modules,
                bias="none",
                task_type="CAUSAL_LM",
                fan_in_fan_out=model_type in ("gpt2", "gpt_bigcode"),
            )
            
            model = get_peft_model(model, lora_config)
            
            # Print trainable parameters
            trainable_params = sum(p.numel() for p in model.parameters() if p.requires_grad)
            all_params = sum(p.numel() for p in model.parameters())
            trainable_percent = 100 * trainable_params / all_params
            
            method_display = "QLORA" if self.use_4bit else "LoRA"
            self._log(f"✓ {method_display} configured: {trainable_params:,} / {all_params:,} params ({trainable_percent:.2f}%)")
            
            return model
    
    def train(self):
        """Execute training"""
        try:
            # Check for cancellation before starting
            if self.should_cancel and self.should_cancel():
                self._log("⚠️ Training cancelled before start")
                if self.log_callback:
                    self.log_callback(self.job_id, "STATUS:stopped")
                return {
                    "status": "stopped",
                    "message": "Training cancelled by user"
                }
            
            # Load model and tokenizer
            model, tokenizer = self.load_model_and_tokenizer()
            
            # Check for cancellation after model load
            if self.should_cancel and self.should_cancel():
                self._log("⚠️ Training cancelled after model load")
                if self.log_callback:
                    self.log_callback(self.job_id, "STATUS:stopped")
                return {
                    "status": "stopped",
                    "message": "Training cancelled by user"
                }
            
            # Setup LoRA
            model = self.setup_lora(model)
            
            # Load dataset
            train_dataset = self.load_dataset_from_file(tokenizer)
            
            # Check for cancellation after dataset load
            if self.should_cancel and self.should_cancel():
                self._log("⚠️ Training cancelled after dataset load")
                if self.log_callback:
                    self.log_callback(self.job_id, "STATUS:stopped")
                return {
                    "status": "stopped",
                    "message": "Training cancelled by user"
                }
            
            # Training arguments (optimized for efficiency and speed)
            # Warmup as a step count computed here: works on every transformers version
            # (transformers 5 removed `warmup_ratio`) and never exceeds a small run.
            steps_per_epoch = max(1, math.ceil(
                len(train_dataset) / (self.training_config['batch_size'] * self.training_config['gradient_accumulation_steps'])
            ))
            total_steps = steps_per_epoch * self.training_config['num_epochs']
            warmup_steps = self.training_config['warmup_steps']
            if warmup_steps is None:
                warmup_steps = int(total_steps * 0.03)
            warmup_steps = min(int(warmup_steps), max(0, total_steps - 1))

            training_args = TrainingArguments(
                output_dir=str(self.output_dir),
                num_train_epochs=self.training_config['num_epochs'],
                per_device_train_batch_size=self.training_config['batch_size'],
                gradient_accumulation_steps=self.training_config['gradient_accumulation_steps'],
                learning_rate=self.training_config['learning_rate'],
                warmup_steps=warmup_steps,
                max_grad_norm=self.training_config['max_grad_norm'],
                weight_decay=self.training_config['weight_decay'],
                
                # Efficiency optimizations
                fp16=self.device == "cuda",  # Mixed precision for GPU
                bf16=self.device == "mps",   # Brain float for Apple Silicon
                optim="paged_adamw_8bit" if self.use_4bit else "adamw_torch",
                gradient_checkpointing=self.training_method != 'full',  # Skip for full to speed up
                
                # Aggressive logging for faster feedback
                logging_steps=self.training_config['logging_steps'],
                logging_first_step=True,  # Log immediately
                save_steps=self.training_config['save_steps'],  # automatic checkpoints
                save_total_limit=2,  # keep the two latest checkpoints
                
                # Speed optimizations
                remove_unused_columns=True,
                dataloader_pin_memory=self.device == "cuda",  # pinned memory only helps (and works) on CUDA
                report_to="none",  # Disable wandb/tensorboard for speed
                dataloader_num_workers=0,  # Reduce CPU usage
                disable_tqdm=False,  # Keep progress bar
                load_best_model_at_end=False,  # Skip evaluation for speed
                save_strategy="steps",
            )
            
            # Data collator
            def data_collator(features):
                # Mask padding via the attention mask (not the pad id: pad == eos here,
                # and the model must still learn to emit EOS).
                batch = tokenizer.pad(features, return_tensors="pt")
                labels = batch["input_ids"].clone()
                labels[batch["attention_mask"] == 0] = -100
                batch["labels"] = labels
                return batch
            
            # Custom callback for progress updates and cancellation
            from transformers import TrainerCallback
            
            class ProgressCallback(TrainerCallback):
                def __init__(self, trainer_instance):
                    self.trainer_instance = trainer_instance
                
                def on_step_begin(self, args, state, control, **kwargs):
                    """Check for cancellation at the start of each training step"""
                    if self.trainer_instance.should_cancel and self.trainer_instance.should_cancel():
                        self.trainer_instance._log("⚠️ Training cancelled during training loop")
                        control.should_training_stop = True
                        control.should_save = False
                        control.should_evaluate = False
                        return control
                
                def on_log(self, args, state, control, logs=None, **kwargs):
                    if logs and 'loss' in logs:
                        # Calculate current epoch from global step
                        current_epoch = int(state.epoch) if hasattr(state, 'epoch') else 0
                        total_epochs = int(args.num_train_epochs)
                        
                        self.trainer_instance._update_progress(
                            current_epoch=current_epoch,
                            total_epochs=total_epochs,
                            current_step=state.global_step,
                            total_steps=state.max_steps,
                            loss=logs['loss'],
                            metrics={
                                "epoch": round(state.epoch or 0, 3),
                                "learning_rate": logs.get('learning_rate'),
                                "vram_gb": self.trainer_instance._memory_gb(),
                            },
                        )
                        self.trainer_instance._log(
                            f"Epoch {current_epoch}/{total_epochs} - Step {state.global_step}/{state.max_steps} - Loss: {logs['loss']:.4f}"
                        )
                    
                    # Also check for cancellation during logging
                    if self.trainer_instance.should_cancel and self.trainer_instance.should_cancel():
                        self.trainer_instance._log("⚠️ Training cancelled")
                        control.should_training_stop = True
                        control.should_save = False
                        control.should_evaluate = False
                        return control
            
            # Initialize trainer
            trainer = Trainer(
                model=model,
                args=training_args,
                train_dataset=train_dataset,
                data_collator=data_collator,
                callbacks=[ProgressCallback(self)],
            )
            
            self._log("🚀 Starting training...")
            
            # Train
            trainer.train()
            
            # Check if cancelled after training
            if self.should_cancel and self.should_cancel():
                self._log("⚠️ Training was cancelled")
                if self.log_callback:
                    self.log_callback(self.job_id, "STATUS:stopped")
                return {
                    "status": "stopped",
                    "message": "Training cancelled by user"
                }
            
            # Save final model
            self._log("💾 Saving model...")
            trainer.save_model(str(self.output_dir / "final"))
            tokenizer.save_pretrained(str(self.output_dir / "final"))
            
            self._log("✅ Training completed successfully!")
            
            # Mark as completed (will be saved to DB by callback)
            if self.log_callback:
                self.log_callback(self.job_id, "STATUS:completed")
            
            return {
                "status": "completed",
                "output_dir": str(self.output_dir / "final"),
                "message": "Training completed successfully"
            }
            
        except Exception as e:
            if "out of memory" in str(e).lower():
                self._log(
                    "💡 Out of memory: try QLoRA (4-bit), a smaller batch size or max sequence length, "
                    "or a smaller base model."
                )
            self._log(f"❌ Training failed: {str(e)}")
            logger.error(f"Training error for job {self.job_id}: {e}", exc_info=True)
            
            # Mark as failed (will be saved to DB by callback)
            if self.log_callback:
                self.log_callback(self.job_id, f"STATUS:failed:{str(e)}")
            
            return {
                "status": "failed",
                "error": str(e),
                "message": "Training failed"
            }


def start_efficient_training(
    job_id: str,
    model_name: str,
    dataset_path: str,
    output_dir: str,
    training_method: str = 'qlora',
    lora_config: Optional[Dict[str, Any]] = None,
    training_config: Optional[Dict[str, Any]] = None,
    progress_callback: Optional[Callable] = None,
    log_callback: Optional[Callable] = None,
    should_cancel: Optional[Callable] = None,
    run_async: bool = True,
) -> Dict[str, Any]:
    """
    Start efficient training with minimal resource consumption
    
    Args:
        job_id: Unique job identifier
        model_name: HuggingFace model name
        dataset_path: Path to dataset file
        output_dir: Output directory for model
        training_method: Training method ('qlora', 'lora', or 'full')
        lora_config: LoRA configuration
        training_config: Training hyperparameters
        progress_callback: Callback for progress updates
        log_callback: Callback for log messages
        should_cancel: Callback to check if training should be cancelled
        run_async: Run in background thread (default: True)
    
    Returns:
        Result dict with status and output_dir
    """
    # Log what we received for debugging
    logger.info(f"start_efficient_training called with: job_id={job_id}, model_name={model_name}, dataset_path={dataset_path}, output_dir={output_dir}")
    
    try:
        trainer = EfficientTrainer(
            job_id=job_id,
            model_name=model_name,
            dataset_path=dataset_path,
            output_dir=output_dir,
            training_method=training_method,
            lora_config=lora_config,
            training_config=training_config,
            progress_callback=progress_callback,
            log_callback=log_callback,
            should_cancel=should_cancel,
        )
    except Exception as e:
        error_msg = f"Failed to initialize EfficientTrainer: {str(e)}"
        logger.error(error_msg, exc_info=True)
        if log_callback:
            log_callback(job_id, f"ERROR: {error_msg}")
            log_callback(job_id, f"STATUS:failed:{error_msg}")
        raise
    
    if run_async:
        # Wrapper function to catch exceptions in thread
        def train_with_error_handling():
            try:
                trainer.train()
            except Exception as e:
                logger.error(f"Training thread failed for job {job_id}: {e}", exc_info=True)
                if log_callback:
                    log_callback(job_id, f"❌ Training failed: {str(e)}")
                    log_callback(job_id, f"STATUS:failed:{str(e)}")
        
        # Run in background thread (not daemon to ensure completion)
        thread = threading.Thread(target=train_with_error_handling, daemon=False)
        thread.start()
        return {
            "status": "started",
            "message": "Training started in background",
            "thread": thread
        }
    else:
        # Run synchronously
        return trainer.train()

