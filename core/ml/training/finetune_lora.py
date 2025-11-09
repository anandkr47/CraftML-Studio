"""
LoRA/QLoRA Fine-tuning Engine
"""

import torch
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    TrainingArguments,
    Trainer,
)
from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)


class LoRATrainer:
    """Handles LoRA/QLoRA fine-tuning of language models"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.model = None
        self.tokenizer = None
        self.trainer = None
        
    def load_model(self, model_name: str, use_4bit: bool = False, use_8bit: bool = False):
        """Load base model and tokenizer"""
        logger.info(f"Loading model: {model_name}")
        
        load_kwargs = {
            "device_map": "auto",
            "torch_dtype": torch.float16,
        }
        
        if use_4bit:
            from transformers import BitsAndBytesConfig
            load_kwargs["quantization_config"] = BitsAndBytesConfig(
                load_in_4bit=True,
                bnb_4bit_compute_dtype=torch.float16,
                bnb_4bit_quant_type="nf4",
                bnb_4bit_use_double_quant=True,
            )
        elif use_8bit:
            load_kwargs["load_in_8bit"] = True
            
        self.model = AutoModelForCausalLM.from_pretrained(model_name, **load_kwargs)
        self.tokenizer = AutoTokenizer.from_pretrained(model_name)
        
        if self.tokenizer.pad_token is None:
            self.tokenizer.pad_token = self.tokenizer.eos_token
            
        logger.info("Model loaded successfully")
        
    def apply_lora(
        self,
        r: int = 16,
        lora_alpha: int = 32,
        target_modules: Optional[list] = None,
        lora_dropout: float = 0.05,
    ):
        """Apply LoRA adapters to the model"""
        if target_modules is None:
            target_modules = ["q_proj", "v_proj", "k_proj", "o_proj"]
            
        lora_config = LoraConfig(
            r=r,
            lora_alpha=lora_alpha,
            target_modules=target_modules,
            lora_dropout=lora_dropout,
            bias="none",
            task_type="CAUSAL_LM",
        )
        
        # Prepare model for k-bit training if using quantization
        if hasattr(self.model, "is_loaded_in_8bit") or hasattr(self.model, "is_loaded_in_4bit"):
            self.model = prepare_model_for_kbit_training(self.model)
            
        self.model = get_peft_model(self.model, lora_config)
        self.model.print_trainable_parameters()
        
    def train(
        self,
        train_dataset,
        eval_dataset=None,
        output_dir: str = "./trained_model",
        num_epochs: int = 3,
        batch_size: int = 4,
        learning_rate: float = 2e-4,
        logging_steps: int = 10,
        save_steps: int = 100,
    ):
        """Train the model with LoRA"""
        training_args = TrainingArguments(
            output_dir=output_dir,
            num_train_epochs=num_epochs,
            per_device_train_batch_size=batch_size,
            per_device_eval_batch_size=batch_size,
            learning_rate=learning_rate,
            logging_steps=logging_steps,
            save_steps=save_steps,
            evaluation_strategy="steps" if eval_dataset else "no",
            eval_steps=save_steps if eval_dataset else None,
            save_total_limit=3,
            fp16=True,
            gradient_checkpointing=True,
            optim="paged_adamw_32bit",
        )
        
        self.trainer = Trainer(
            model=self.model,
            args=training_args,
            train_dataset=train_dataset,
            eval_dataset=eval_dataset,
        )
        
        logger.info("Starting training...")
        self.trainer.train()
        logger.info("Training completed!")
        
    def save_model(self, output_path: str):
        """Save the fine-tuned model"""
        self.model.save_pretrained(output_path)
        self.tokenizer.save_pretrained(output_path)
        logger.info(f"Model saved to {output_path}")


def start_lora_training(job_id: str, params: Dict[str, Any]) -> str:
    """
    Start LoRA training job
    
    Args:
        job_id: Unique job identifier
        params: Training parameters including:
            - model_name: Base model to fine-tune
            - dataset_path: Path to training dataset
            - output_dir: Where to save the model
            - lora_config: LoRA hyperparameters
            - training_config: Training hyperparameters
            - max_length: Maximum sequence length (default: 512)
            - text_field: Field name for text data (default: "text")
            
    Returns:
        Status message
    """
    try:
        trainer = LoRATrainer(params)
        
        # Load model
        model_name = params.get("model_name", "meta-llama/Llama-2-7b-hf")
        trainer.load_model(
            model_name=model_name,
            use_4bit=params.get("use_4bit", True),
        )
        
        # Apply LoRA
        lora_config = params.get("lora_config", {})
        trainer.apply_lora(
            r=lora_config.get("r", 16),
            lora_alpha=lora_config.get("lora_alpha", 32),
            lora_dropout=lora_config.get("lora_dropout", 0.05),
        )
        
        # Load and prepare dataset
        dataset_path = params.get("dataset_path")
        if not dataset_path:
            raise ValueError("dataset_path is required")
        
        logger.info(f"Loading dataset from {dataset_path}")
        
        from core.data import DatasetLoader
        loader = DatasetLoader()
        
        # Load samples
        samples = loader.load_from_path(dataset_path)
        
        # Prepare for training
        train_dataset = loader.prepare_for_training(
            samples=samples,
            tokenizer=trainer.tokenizer,
            max_length=params.get("max_length", 512),
            text_field=params.get("text_field", "text")
        )
        
        logger.info(f"Prepared {len(train_dataset)} samples for training")
        
        # Optional: Create evaluation dataset
        eval_dataset = None
        eval_split = params.get("eval_split", 0.1)
        if eval_split > 0:
            split_dataset = train_dataset.train_test_split(test_size=eval_split)
            train_dataset = split_dataset['train']
            eval_dataset = split_dataset['test']
            logger.info(f"Split: {len(train_dataset)} train, {len(eval_dataset)} eval")
        
        # Train
        training_config = params.get("training_config", {})
        output_dir = params.get("output_dir", f"./models/{job_id}")
        
        trainer.train(
            train_dataset=train_dataset,
            eval_dataset=eval_dataset,
            output_dir=output_dir,
            num_epochs=training_config.get("num_epochs", 3),
            batch_size=training_config.get("batch_size", 4),
            learning_rate=training_config.get("learning_rate", 2e-4),
            logging_steps=training_config.get("logging_steps", 10),
            save_steps=training_config.get("save_steps", 100),
        )
        
        # Save final model
        trainer.save_model(output_dir)
        
        logger.info(f"Training completed! Model saved to {output_dir}")
        return f"Training completed successfully. Model saved to {output_dir}"
        
    except Exception as e:
        logger.error(f"Training failed: {str(e)}")
        raise

