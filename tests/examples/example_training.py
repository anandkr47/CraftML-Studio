"""
Example: Fine-tune a model with LoRA
Demonstrates the complete training workflow
"""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from core.ml.training import start_lora_training


def example_lora_training():
    """
    Example of LoRA fine-tuning
    
    This example shows how to:
    1. Configure training parameters
    2. Start a LoRA training job
    3. Save the fine-tuned model
    
    Note: This is a demonstration. Adjust paths and parameters for your use case.
    """
    
    print("="*60)
    print("EXAMPLE: LoRA Fine-Tuning")
    print("="*60 + "\n")
    
    # Training parameters
    params = {
        # Model configuration
        "model_name": "gpt2",  # Use a smaller model for testing
        "use_4bit": False,  # Set to True for QLoRA (requires bitsandbytes + CUDA)
        
        # Dataset configuration
        "dataset_path": "./resources/datasets/instruction-template.jsonl",
        "max_length": 128,
        "text_field": "text",
        "eval_split": 0.1,  # 10% for evaluation
        
        # LoRA configuration
        "lora_config": {
            "r": 8,  # LoRA rank
            "lora_alpha": 16,  # LoRA alpha
            "lora_dropout": 0.05,
        },
        
        # Training configuration
        "training_config": {
            "num_epochs": 1,  # Short for demo
            "batch_size": 2,
            "learning_rate": 2e-4,
            "logging_steps": 10,
            "save_steps": 50,
        },
        
        # Output
        "output_dir": "./models/example_lora_model"
    }
    
    print("Configuration:")
    print(f"  Model: {params['model_name']}")
    print(f"  Dataset: {params['dataset_path']}")
    print(f"  LoRA rank: {params['lora_config']['r']}")
    print(f"  Epochs: {params['training_config']['num_epochs']}")
    print(f"  Output: {params['output_dir']}")
    print()
    
    # Note: This will actually try to train if a dataset exists
    # For real training, ensure you have a proper dataset
    
    try:
        # Start training
        result = start_lora_training(
            job_id="example_job_001",
            params=params
        )
        
        print("\n" + "="*60)
        print("Training Result:")
        print(result)
        print("="*60)
        
    except FileNotFoundError as e:
        print(f"\n⚠️  Dataset not found: {e}")
        print("\nTo run this example:")
        print(f"  1. Create a dataset at: {params['dataset_path']}")
        print("  2. Format: JSONL with 'text' field")
        print("  3. Run this script again")
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        print("\nThis is expected if you don't have:")
        print("  - A valid dataset")
        print("  - Sufficient GPU memory")
        print("  - Required packages installed")


if __name__ == "__main__":
    example_lora_training()

