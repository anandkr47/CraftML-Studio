"""
Example: Model Compression
Demonstrates quantization
"""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from core.ml.compression import quantize_model


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


def run_all_examples():
    """Run all compression examples"""
    example_quantization()
    
    print("\n" + "="*60)
    print("✅ COMPRESSION EXAMPLES COMPLETE")
    print("="*60 + "\n")


if __name__ == "__main__":
    run_all_examples()

