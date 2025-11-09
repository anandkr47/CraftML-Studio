"""
Training from Scratch Module
Handles creating and training models from scratch without pretrained weights
"""

import logging
from typing import Dict, Any, Optional
from pathlib import Path
import torch
from transformers import (
    AutoConfig,
    AutoTokenizer,
    AutoModelForCausalLM,
    AutoModelForMaskedLM,
    BertConfig,
    GPT2Config,
    Trainer,
    TrainingArguments,
    DataCollatorForLanguageModeling,
)
from datasets import load_dataset

logger = logging.getLogger(__name__)


class ScratchModelTrainer:
    """Trainer for building models from scratch"""
    
    ARCHITECTURE_CONFIGS = {
        "scratch-transformer": {
            "base_class": GPT2Config,
            "model_class": AutoModelForCausalLM,
            "default_config": {
                "vocab_size": 32000,
                "n_positions": 1024,
                "n_embd": 768,
                "n_layer": 12,
                "n_head": 12,
                "n_inner": 3072,
                "activation_function": "gelu_new",
                "resid_pdrop": 0.1,
                "embd_pdrop": 0.1,
                "attn_pdrop": 0.1,
            },
            "task": "causal-lm"
        },
        "scratch-bert": {
            "base_class": BertConfig,
            "model_class": AutoModelForMaskedLM,
            "default_config": {
                "vocab_size": 32000,
                "hidden_size": 768,
                "num_hidden_layers": 12,
                "num_attention_heads": 12,
                "intermediate_size": 3072,
                "hidden_act": "gelu",
                "hidden_dropout_prob": 0.1,
                "attention_probs_dropout_prob": 0.1,
                "max_position_embeddings": 512,
            },
            "task": "masked-lm"
        },
        "scratch-gpt": {
            "base_class": GPT2Config,
            "model_class": AutoModelForCausalLM,
            "default_config": {
                "vocab_size": 32000,
                "n_positions": 1024,
                "n_embd": 768,
                "n_layer": 12,
                "n_head": 12,
                "n_inner": 3072,
                "activation_function": "gelu_new",
            },
            "task": "causal-lm"
        },
    }
    
    def __init__(
        self,
        model_type: str,
        dataset_path: str,
        output_dir: str,
        vocab_size: int = 32000,
        hidden_size: int = 768,
        num_layers: int = 12,
        num_heads: int = 12,
    ):
        """
        Initialize scratch trainer
        
        Args:
            model_type: Type of model architecture
            dataset_path: Path to training dataset
            output_dir: Directory to save model
            vocab_size: Size of vocabulary
            hidden_size: Hidden layer dimension
            num_layers: Number of transformer layers
            num_heads: Number of attention heads
        """
        self.model_type = model_type
        self.dataset_path = dataset_path
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Get architecture configuration
        if model_type not in self.ARCHITECTURE_CONFIGS:
            raise ValueError(f"Unsupported model type: {model_type}")
        
        self.arch_config = self.ARCHITECTURE_CONFIGS[model_type]
        
        # Update config with custom parameters
        self.model_config = self.arch_config["default_config"].copy()
        self.model_config["vocab_size"] = vocab_size
        
        if "n_embd" in self.model_config:
            self.model_config["n_embd"] = hidden_size
            self.model_config["n_layer"] = num_layers
            self.model_config["n_head"] = num_heads
            self.model_config["n_inner"] = hidden_size * 4
        else:
            self.model_config["hidden_size"] = hidden_size
            self.model_config["num_hidden_layers"] = num_layers
            self.model_config["num_attention_heads"] = num_heads
            self.model_config["intermediate_size"] = hidden_size * 4
    
    def create_tokenizer(self) -> AutoTokenizer:
        """
        Create a new tokenizer from the dataset
        
        Returns:
            Trained tokenizer
        """
        logger.info("Creating custom tokenizer from dataset")
        
        try:
            # Load dataset for tokenizer training
            file_path = Path(self.dataset_path)
            if file_path.suffix in ['.jsonl', '.json']:
                ds = load_dataset('json', data_files=str(file_path), split='train')
                # flatten instruction/output to text
                def to_text(example):
                    inst = example.get('instruction') or ''
                    out = example.get('output') or ''
                    inp = example.get('input') or ''
                    text = f"### Instruction:\n{inst}\n\n"
                    if inp:
                        text += f"### Input:\n{inp}\n\n"
                    text += f"### Response:\n{out}"
                    return {'text': text}
                ds = ds.map(to_text)
                dataset = {'train': ds}
            else:
                dataset = load_dataset('text', data_files=self.dataset_path)
            
            # Use a base tokenizer as template
            tokenizer = AutoTokenizer.from_pretrained("gpt2")
            
            # Train new tokenizer on custom corpus
            def get_training_corpus():
                for i in range(0, len(dataset["train"]), 1000):
                    yield dataset["train"][i : i + 1000]["text"]
            
            new_tokenizer = tokenizer.train_new_from_iterator(
                get_training_corpus(),
                vocab_size=self.model_config["vocab_size"]
            )
            
            # Save tokenizer
            tokenizer_dir = self.output_dir / "tokenizer"
            tokenizer_dir.mkdir(parents=True, exist_ok=True)
            new_tokenizer.save_pretrained(str(tokenizer_dir))
            
            logger.info(f"Custom tokenizer created with vocab size: {len(new_tokenizer)}")
            return new_tokenizer
            
        except Exception as e:
            logger.error(f"Error creating tokenizer: {e}")
            logger.info("Falling back to pre-trained tokenizer")
            # Fallback to existing tokenizer
            tokenizer = AutoTokenizer.from_pretrained("gpt2")
            return tokenizer
    
    def create_model(self, tokenizer: AutoTokenizer):
        """
        Create a new model with random initialization
        
        Args:
            tokenizer: Tokenizer for the model
            
        Returns:
            Initialized model
        """
        logger.info(f"Creating {self.model_type} model from scratch")
        
        # Update vocab size to match tokenizer
        self.model_config["vocab_size"] = len(tokenizer)
        
        # Create configuration
        config_class = self.arch_config["base_class"]
        config = config_class(**self.model_config)
        
        # Create model with random weights
        model_class = self.arch_config["model_class"]
        model = model_class.from_config(config)
        
        # Resize token embeddings
        model.resize_token_embeddings(len(tokenizer))
        
        logger.info(f"Model created with {model.num_parameters():,} parameters")
        return model
    
    def prepare_dataset(self, tokenizer: AutoTokenizer):
        """
        Load and prepare dataset for training
        
        Args:
            tokenizer: Tokenizer for preprocessing
            
        Returns:
            Tokenized dataset
        """
        logger.info(f"Loading dataset from {self.dataset_path}")
        
        # Load dataset (support instruction JSON/JSONL and plain text)
        file_path = Path(self.dataset_path)
        if file_path.suffix in ['.jsonl', '.json']:
            ds = load_dataset('json', data_files=str(file_path), split='train')
            def to_text(example):
                inst = example.get('instruction') or ''
                out = example.get('output') or ''
                inp = example.get('input') or ''
                text = f"### Instruction:\n{inst}\n\n"
                if inp:
                    text += f"### Input:\n{inp}\n\n"
                text += f"### Response:\n{out}"
                return {'text': text}
            ds = ds.map(to_text)
            dataset = {'train': ds}
        else:
            dataset = load_dataset('text', data_files=self.dataset_path)
        
        # Tokenize function
        def tokenize_function(examples):
            return tokenizer(
                examples["text"],
                truncation=True,
                padding="max_length",
                max_length=512
            )
        
        # Tokenize dataset
        train_dataset = dataset["train"]
        tokenized_dataset = train_dataset.map(
            tokenize_function,
            batched=True,
            remove_columns=train_dataset.column_names
        )
        
        logger.info(f"Dataset prepared with {len(tokenized_dataset)} examples")
        return {'train': tokenized_dataset}
    
    def train(
        self,
        num_epochs: int = 3,
        batch_size: int = 8,
        learning_rate: float = 5e-4,
        warmup_steps: int = 500,
        save_steps: int = 1000,
        logging_steps: int = 100,
        progress_callback=None,
        log_callback=None,
    ) -> Dict[str, Any]:
        """
        Train the model from scratch
        
        Args:
            num_epochs: Number of training epochs
            batch_size: Training batch size
            learning_rate: Learning rate
            warmup_steps: Warmup steps
            save_steps: Save checkpoint interval
            logging_steps: Logging interval
            
        Returns:
            Training metrics
        """
        try:
            if log_callback:
                log_callback("Creating custom tokenizer from dataset...")
            # Create tokenizer
            tokenizer = self.create_tokenizer()
            
            if log_callback:
                log_callback("Initializing model architecture...")
            # Create model
            model = self.create_model(tokenizer)
            
            if log_callback:
                log_callback("Preparing training dataset...")
            # Prepare dataset
            tokenized_dataset = self.prepare_dataset(tokenizer)
            
            # Data collator
            task_type = self.arch_config["task"]
            data_collator = DataCollatorForLanguageModeling(
                tokenizer=tokenizer,
                mlm=(task_type == "masked-lm"),
                mlm_probability=0.15 if task_type == "masked-lm" else None
            )
            
            # Training arguments
            training_args = TrainingArguments(
                output_dir=str(self.output_dir),
                num_train_epochs=num_epochs,
                per_device_train_batch_size=batch_size,
                learning_rate=learning_rate,
                warmup_steps=warmup_steps,
                save_steps=save_steps,
                logging_steps=logging_steps,
                save_total_limit=2,
                fp16=torch.cuda.is_available(),
                logging_dir=str(self.output_dir / "logs"),
                report_to="none",
            )
            
            # Custom callback for progress updates
            from transformers import TrainerCallback
            
            class ProgressCallback(TrainerCallback):
                def __init__(self, trainer_instance):
                    self.trainer_instance = trainer_instance
                
                def on_log(self, args, state, control, logs=None, **kwargs):
                    if logs and 'loss' in logs:
                        current_epoch = int(state.epoch) if hasattr(state, 'epoch') else 0
                        total_epochs = int(args.num_train_epochs)
                        if self.trainer_instance.progress_callback:
                            self.trainer_instance.progress_callback(
                                current_epoch=current_epoch,
                                total_epochs=total_epochs,
                                current_step=state.global_step,
                                total_steps=state.max_steps,
                                loss=logs['loss']
                            )
                        if self.trainer_instance.log_callback:
                            self.trainer_instance.log_callback(
                                f"Epoch {current_epoch}/{total_epochs} - Step {state.global_step}/{state.max_steps} - Loss: {logs['loss']:.4f}"
                            )
            
            # Create trainer
            trainer = Trainer(
                model=model,
                args=training_args,
                train_dataset=tokenized_dataset["train"],
                data_collator=data_collator,
                callbacks=[ProgressCallback(self)],
            )
            
            # Store callbacks for progress updates
            self.progress_callback = progress_callback
            self.log_callback = log_callback
            
            # Train model
            logger.info("Starting training from scratch")
            if log_callback:
                log_callback(f"Starting training: {num_epochs} epochs, batch_size={batch_size}, lr={learning_rate}")
            train_result = trainer.train()
            
            # Save final model
            trainer.save_model()
            tokenizer.save_pretrained(str(self.output_dir))
            
            logger.info("Training completed successfully")
            
            return {
                "success": True,
                "output_dir": str(self.output_dir),
                "model_type": self.model_type,
                "num_parameters": model.num_parameters(),
                "metrics": train_result.metrics,
            }
            
        except Exception as e:
            logger.error(f"Training failed: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e),
            }


def train_from_scratch(
    model_type: str,
    dataset_path: str,
    output_dir: str,
    config: Dict[str, Any],
    progress_callback=None,
    log_callback=None,
) -> Dict[str, Any]:
    """
    Train a model from scratch
    
    Args:
        model_type: Type of model architecture
        dataset_path: Path to training dataset
        output_dir: Output directory
        config: Training configuration
        
    Returns:
        Training results
    """
    trainer = ScratchModelTrainer(
        model_type=model_type,
        dataset_path=dataset_path,
        output_dir=output_dir,
        vocab_size=config.get("vocab_size", 32000),
        hidden_size=config.get("hidden_size", 768),
        num_layers=config.get("num_layers", 12),
        num_heads=config.get("num_heads", 12),
    )
    
    return trainer.train(
        num_epochs=config.get("num_epochs", 3),
        batch_size=config.get("batch_size", 8),
        learning_rate=config.get("learning_rate", 5e-4),
        warmup_steps=config.get("warmup_steps", 500),
        save_steps=config.get("save_steps", 1000),
        logging_steps=config.get("logging_steps", 100),
        progress_callback=progress_callback,
        log_callback=log_callback,
    )

