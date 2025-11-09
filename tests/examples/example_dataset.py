"""
Example: Dataset Management
Demonstrates crawling, cleaning, formatting, and loading
"""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from core.data import (
    TextCleaner,
    DatasetFormatter,
    DatasetLoader,
    format_for_instruction_tuning,
    save_as_jsonl
)


def example_cleaning():
    """Example of text cleaning"""
    
    print("="*60)
    print("EXAMPLE: Text Cleaning")
    print("="*60 + "\n")
    
    # Sample dirty text
    dirty_texts = [
        "Check this out: https://example.com   with lots of   spaces",
        "Contact us at info@example.com or visit http://site.org",
        "This    has     irregular       spacing!",
    ]
    
    # Create cleaner
    cleaner = TextCleaner(
        remove_urls=True,
        remove_emails=True,
        remove_extra_whitespace=True
    )
    
    print("Original texts:")
    for i, text in enumerate(dirty_texts, 1):
        print(f"  {i}. {text}")
    
    # Clean texts
    cleaned_texts = cleaner.clean_batch(dirty_texts)
    
    print("\nCleaned texts:")
    for i, text in enumerate(cleaned_texts, 1):
        print(f"  {i}. {text}")
    
    print("\n✅ Text cleaning complete")


def example_formatting():
    """Example of dataset formatting"""
    
    print("\n" + "="*60)
    print("EXAMPLE: Dataset Formatting")
    print("="*60 + "\n")
    
    # Sample data
    raw_data = [
        {
            "instruction": "Translate to Spanish",
            "input": "Hello, how are you?",
            "output": "Hola, ¿cómo estás?"
        },
        {
            "instruction": "Summarize this text",
            "input": "Machine learning is a subset of artificial intelligence...",
            "output": "ML is an AI subset that enables systems to learn."
        },
        {
            "instruction": "Answer the question",
            "input": "What is the capital of France?",
            "output": "The capital of France is Paris."
        }
    ]
    
    print(f"Sample data: {len(raw_data)} items")
    
    # Format for instruction tuning
    formatted = format_for_instruction_tuning(raw_data)
    
    print("\nFormatted sample:")
    print(formatted[0]["text"][:200] + "...")
    
    # Save to JSONL
    output_dir = Path("./tests/examples/output")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    output_file = output_dir / "formatted_dataset.jsonl"
    save_as_jsonl(formatted, str(output_file))
    
    print(f"\n✅ Saved to: {output_file}")


def example_loading():
    """Example of dataset loading"""
    
    print("\n" + "="*60)
    print("EXAMPLE: Dataset Loading")
    print("="*60 + "\n")
    
    # Create sample dataset
    data = [
        {"text": "Sample text 1"},
        {"text": "Sample text 2"},
        {"text": "Sample text 3"}
    ]
    
    output_dir = Path("./tests/examples/output")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    test_file = output_dir / "test_dataset.jsonl"
    save_as_jsonl(data, str(test_file))
    
    print(f"Created test dataset: {test_file}")
    
    # Load dataset
    loader = DatasetLoader()
    loaded = loader.load_from_path(str(test_file))
    
    print(f"\nLoaded {len(loaded)} samples")
    print("\nFirst sample:")
    print(f"  {loaded[0]}")
    
    print("\n✅ Dataset loading complete")


def run_all_examples():
    """Run all dataset examples"""
    example_cleaning()
    example_formatting()
    example_loading()
    
    print("\n" + "="*60)
    print("✅ DATASET EXAMPLES COMPLETE")
    print("="*60 + "\n")


if __name__ == "__main__":
    run_all_examples()

