"""
Example: Model Compression
Demonstrates quantization, pruning, and distillation
"""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from core.ml.compression import quantize_model, prune_model, distill_model


def example_quantization():
    """
    Example of model quantization
    
    Demonstrates INT8, INT4, and GPTQ quantization
    """
    
    print("="*60)
    print("EXAMPLE: Model Quantization")
    print("="*60 + "\n")
    
    model_path = "./models/my_model"  # Replace with actual model path
    output_path = "./models/my_model_quantized"
    
    print("Quantization Methods:")
    print("  1. INT8 - 8-bit quantization")
    print("  2. INT4 - 4-bit quantization (NF4)")
    print("  3. GPTQ - Advanced quantization")
    print()
    
    # Example INT4 quantization
    print("Example: INT4 Quantization")
    print(f"  Input: {model_path}")
    print(f"  Output: {output_path}")
    print()
    
    try:
        result = quantize_model(
            model_path=model_path,
            output_path=output_path,
            method="int4",
            use_double_quant=True
        )
        
        print("Result:", result)
        
    except Exception as e:
        print(f"⚠️  Note: {e}")
        print("\nTo run this example:")
        print(f"  1. Ensure model exists at: {model_path}")
        print("  2. Install required packages: bitsandbytes, transformers")
        print("  3. Have sufficient storage for output")


def example_pruning():
    """
    Example of model pruning
    
    Demonstrates magnitude and structured pruning
    """
    
    print("\n" + "="*60)
    print("EXAMPLE: Model Pruning")
    print("="*60 + "\n")
    
    print("Pruning Methods:")
    print("  1. Magnitude - Remove smallest weights")
    print("  2. Structured - Remove entire channels/neurons")
    print()
    
    print("Example: Magnitude Pruning")
    print("  Amount: 30% sparsity")
    print()
    
    try:
        import torch
        import torch.nn as nn
        
        # Create simple example model
        model = nn.Sequential(
            nn.Linear(100, 50),
            nn.ReLU(),
            nn.Linear(50, 10)
        )
        
        # Apply pruning
        result = prune_model(
            model=model,
            method="magnitude",
            amount=0.3
        )
        
        print("Result:", result)
        print(f"  Sparsity: {result['sparsity']*100:.2f}%")
        print(f"  Pruned params: {result['pruned_params']:,}")
        print(f"  Total params: {result['total_params']:,}")
        
    except Exception as e:
        print(f"❌ Error: {e}")


def example_distillation():
    """
    Example of knowledge distillation
    
    Demonstrates transferring knowledge from teacher to student
    """
    
    print("\n" + "="*60)
    print("EXAMPLE: Knowledge Distillation")
    print("="*60 + "\n")
    
    teacher_path = "./models/teacher_model"
    student_path = "./models/student_model"
    dataset_path = "./resources/datasets/instruction-template.jsonl"
    output_path = "./models/distilled_model"
    
    print("Distillation Setup:")
    print(f"  Teacher: {teacher_path} (large model)")
    print(f"  Student: {student_path} (small model)")
    print(f"  Dataset: {dataset_path}")
    print(f"  Output: {output_path}")
    print()
    
    try:
        result = distill_model(
            teacher_model_path=teacher_path,
            student_model_path=student_path,
            train_dataset=dataset_path,
            output_path=output_path,
            temperature=2.0,
            alpha=0.7,
            num_epochs=3,
            batch_size=4
        )
        
        print("Result:", result)
        
    except Exception as e:
        print(f"⚠️  Note: {e}")
        print("\nTo run this example:")
        print("  1. Prepare teacher and student models")
        print("  2. Create training dataset")
        print("  3. Ensure sufficient GPU memory")


def run_all_examples():
    """Run all compression examples"""
    example_quantization()
    example_pruning()
    example_distillation()
    
    print("\n" + "="*60)
    print("✅ COMPRESSION EXAMPLES COMPLETE")
    print("="*60 + "\n")


if __name__ == "__main__":
    run_all_examples()

