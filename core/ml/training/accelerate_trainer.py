"""
Accelerate-Based Training Engine
Uses Hugging Face Accelerate for multi-GPU, mixed precision training
"""

import os
import torch
from typing import Dict, Any, Optional, Callable
from pathlib import Path
import logging
from dataclasses import dataclass

from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    TrainingArguments,
    Trainer,
    DataCollatorForLanguageModeling
)
from peft import (
    LoraConfig,
    get_peft_model,
    prepare_model_for_kbit_training,
    TaskType
)
from accelerate import Accelerator
from datasets import Dataset

logger = logging.getLogger(__name__)


@dataclass
class TrainingConfig:
    """Training configuration"""
    # Model
    model_name: str
    output_dir: str
    
    # Strategy
    strategy: str = "lora"  # lora, qlora, or full
    
    # LoRA config
    lora_r: int = 16
    lora_alpha: int = 32
    lora_dropout: float = 0.05
    lora_target_modules: Optional[list] = None
    
    # Training hyperparameters
    num_epochs: int = 3
    per_device_train_batch_size: int = 4
    gradient_accumulation_steps: int = 4
    learning_rate: float = 2e-4
    warmup_steps: int = 100
    max_grad_norm: float = 0.3
    
    # Optimization
    use_4bit: bool = False
    use_8bit: bool = False
    bf16: bool = False
    fp16: bool = False
    gradient_checkpointing: bool = True
    
    # Device
    device_map: Optional[str] = "auto"
    
    # Logging
    logging_steps: int = 10
    save_steps: int = 100
    eval_steps: int = 100


class AccelerateTrainer:
    """
    Training engine using Accelerate
    """
    
    def __init__(
        self,
        config: TrainingConfig,
        progress_callback: Optional[Callable] = None
    ):
        """
        Initialize trainer
        
        Args:
            config: Training configuration
            progress_callback: Optional callback for progress updates
        """
        self.config = config
        self.progress_callback = progress_callback
        
        # Initialize Accelerator
        self.accelerator = Accelerator(
            mixed_precision="bf16" if config.bf16 else ("fp16" if config.fp16 else "no"),
            gradient_accumulation_steps=config.gradient_accumulation_steps
        )
        
        self.model = None
        self.tokenizer = None
        self.trainer = None
        
        logger.info(f"Accelerator initialized: {self.accelerator.state}")
    
    def load_model(self):
        """Load model and tokenizer"""
        logger.info(f"Loading model: {self.config.model_name}")
        
        # Load tokenizer
        self.tokenizer = AutoTokenizer.from_pretrained(
            self.config.model_name,
            trust_remote_code=True
        )
        
        # Set padding token if not set
        if self.tokenizer.pad_token is None:
            self.tokenizer.pad_token = self.tokenizer.eos_token
        
        # Prepare model loading kwargs
        model_kwargs = {
            "trust_remote_code": True,
        }
        
        # Add quantization if needed
        if self.config.use_4bit:
            from transformers import BitsAndBytesConfig
            
            model_kwargs["quantization_config"] = BitsAndBytesConfig(
                load_in_4bit=True,
                bnb_4bit_compute_dtype=torch.bfloat16 if self.config.bf16 else torch.float16,
                bnb_4bit_quant_type="nf4",
                bnb_4bit_use_double_quant=True
            )
            logger.info("Using 4-bit quantization (QLoRA)")
        
        elif self.config.use_8bit:
            model_kwargs["load_in_8bit"] = True
            logger.info("Using 8-bit quantization")
        
        else:
            # Full precision or FP16/BF16
            if self.config.bf16:
                model_kwargs["torch_dtype"] = torch.bfloat16
            elif self.config.fp16:
                model_kwargs["torch_dtype"] = torch.float16
            
            if self.config.device_map:
                model_kwargs["device_map"] = self.config.device_map
        
        # Load model
        self.model = AutoModelForCausalLM.from_pretrained(
            self.config.model_name,
            **model_kwargs
        )
        
        # Enable gradient checkpointing
        if self.config.gradient_checkpointing:
            self.model.gradient_checkpointing_enable()
        
        # Apply LoRA if needed
        if self.config.strategy in ["lora", "qlora"]:
            self._apply_lora()
        
        logger.info(f"Model loaded: {self.config.model_name}")
        
        return self.model, self.tokenizer
    
    def _apply_lora(self):
        """Apply LoRA to model"""
        logger.info("Applying LoRA configuration")
        
        # Prepare model for k-bit training if using quantization
        if self.config.use_4bit or self.config.use_8bit:
            self.model = prepare_model_for_kbit_training(self.model)
        
        # LoRA configuration
        lora_config = LoraConfig(
            r=self.config.lora_r,
            lora_alpha=self.config.lora_alpha,
            lora_dropout=self.config.lora_dropout,
            target_modules=self.config.lora_target_modules or self._get_target_modules(),
            bias="none",
            task_type=TaskType.CAUSAL_LM
        )
        
        # Apply LoRA
        self.model = get_peft_model(self.model, lora_config)
        
        # Print trainable parameters
        self.model.print_trainable_parameters()
    
    def _get_target_modules(self) -> list:
        """Get default target modules for LoRA"""
        # Common target modules for different architectures
        # This covers most LLaMA-based models
        return ["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"]
    
    def prepare_dataset(
        self,
        dataset: Dataset,
        max_length: int = 512
    ) -> Dataset:
        """
        Prepare dataset for training
        
        Args:
            dataset: Input dataset
            max_length: Maximum sequence length
            
        Returns:
            Tokenized dataset
        """
        logger.info(f"Preparing dataset: {len(dataset)} samples")
        
        def tokenize_function(examples):
            # Tokenize
            result = self.tokenizer(
                examples["text"],
                truncation=True,
                max_length=max_length,
                padding="max_length"
            )
            
            # For causal LM, labels are the same as input_ids
            result["labels"] = result["input_ids"].copy()
            
            return result
        
        # Tokenize dataset
        tokenized_dataset = dataset.map(
            tokenize_function,
            batched=True,
            remove_columns=dataset.column_names
        )
        
        logger.info(f"Dataset prepared: {len(tokenized_dataset)} samples")
        
        return tokenized_dataset
    
    def train(
        self,
        train_dataset: Dataset,
        eval_dataset: Optional[Dataset] = None
    ) -> Dict[str, Any]:
        """
        Train the model
        
        Args:
            train_dataset: Training dataset
            eval_dataset: Optional evaluation dataset
            
        Returns:
            Training results
        """
        logger.info("Starting training...")
        
        # Training arguments
        training_args = TrainingArguments(
            output_dir=self.config.output_dir,
            num_train_epochs=self.config.num_epochs,
            per_device_train_batch_size=self.config.per_device_train_batch_size,
            gradient_accumulation_steps=self.config.gradient_accumulation_steps,
            learning_rate=self.config.learning_rate,
            warmup_steps=self.config.warmup_steps,
            max_grad_norm=self.config.max_grad_norm,
            logging_steps=self.config.logging_steps,
            save_steps=self.config.save_steps,
            eval_steps=self.config.eval_steps if eval_dataset else None,
            evaluation_strategy="steps" if eval_dataset else "no",
            save_strategy="steps",
            bf16=self.config.bf16,
            fp16=self.config.fp16,
            gradient_checkpointing=self.config.gradient_checkpointing,
            optim="paged_adamw_8bit" if (self.config.use_4bit or self.config.use_8bit) else "adamw_torch",
            report_to=["none"],  # Disable wandb, tensorboard, etc.
            load_best_model_at_end=True if eval_dataset else False,
        )
        
        # Data collator
        data_collator = DataCollatorForLanguageModeling(
            tokenizer=self.tokenizer,
            mlm=False  # Causal LM, not masked LM
        )
        
        # Create trainer
        self.trainer = Trainer(
            model=self.model,
            args=training_args,
            train_dataset=train_dataset,
            eval_dataset=eval_dataset,
            data_collator=data_collator,
            tokenizer=self.tokenizer
        )
        
        # Add progress callback if provided
        if self.progress_callback:
            from transformers import TrainerCallback
            
            class ProgressCallback(TrainerCallback):
                def __init__(self, callback_fn):
                    self.callback_fn = callback_fn
                
                def on_log(self, args, state, control, logs=None, **kwargs):
                    if logs:
                        self.callback_fn({
                            "step": state.global_step,
                            "epoch": state.epoch,
                            "loss": logs.get("loss", 0),
                            "learning_rate": logs.get("learning_rate", 0)
                        })
            
            self.trainer.add_callback(ProgressCallback(self.progress_callback))
        
        # Train
        train_result = self.trainer.train()
        
        # Save final model
        self.trainer.save_model()
        
        logger.info("Training complete!")
        
        return {
            "train_loss": train_result.training_loss,
            "train_runtime": train_result.metrics.get("train_runtime", 0),
            "train_samples_per_second": train_result.metrics.get("train_samples_per_second", 0),
            "output_dir": self.config.output_dir
        }
    
    def save_model(self, output_path: Optional[str] = None):
        """
        Save trained model
        
        Args:
            output_path: Optional custom output path
        """
        save_path = output_path or self.config.output_dir
        
        logger.info(f"Saving model to: {save_path}")
        
        if self.config.strategy in ["lora", "qlora"]:
            # Save LoRA adapters
            self.model.save_pretrained(save_path)
        else:
            # Save full model
            self.model.save_pretrained(save_path)
        
        # Save tokenizer
        self.tokenizer.save_pretrained(save_path)
        
        logger.info(f"Model saved to: {save_path}")

