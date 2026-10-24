"""
Test Suite for Core Data Modules
Tests formatter and dataset utils
"""

import pytest
import sys
import json
import tempfile
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.data.formatter import save_as_jsonl
from core.data.dataset_utils import DatasetLoader, format_for_instruction_tuning


class TestDatasetFormatter:
    """Test dataset formatting"""
    
    def test_jsonl_saving(self):
        """Test saving to JSONL format"""
        data = [
            {"text": "Sample 1"},
            {"text": "Sample 2"},
            {"text": "Sample 3"}
        ]
        
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "test.jsonl"
            
            # Save
            save_as_jsonl(data, str(output_path))
            
            # Verify
            assert output_path.exists()
            
            # Read back
            with open(output_path, 'r') as f:
                lines = f.readlines()
            
            assert len(lines) == 3
            
            # Parse first line
            first_item = json.loads(lines[0])
            assert first_item["text"] == "Sample 1"
        
        print("✅ JSONL saving test passed")


class TestDatasetLoader:
    """Test dataset loading utilities"""
    
    def test_jsonl_loading(self):
        """Test loading JSONL files"""
        data = [
            {"text": "Sample 1"},
            {"text": "Sample 2"}
        ]
        
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create test file
            test_file = Path(tmpdir) / "test.jsonl"
            with open(test_file, 'w') as f:
                for item in data:
                    f.write(json.dumps(item) + '\n')
            
            # Load
            loader = DatasetLoader()
            loaded = loader.load_jsonl(str(test_file))
            
            assert len(loaded) == 2
            assert loaded[0]["text"] == "Sample 1"
            assert loaded[1]["text"] == "Sample 2"
        
        print("✅ JSONL loading test passed")
    
    def test_csv_loading(self):
        """Test loading CSV files"""
        import pandas as pd
        
        data = pd.DataFrame({
            "text": ["Sample 1", "Sample 2", "Sample 3"]
        })
        
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create test file
            test_file = Path(tmpdir) / "test.csv"
            data.to_csv(test_file, index=False)
            
            # Load
            loader = DatasetLoader()
            loaded = loader.load_csv(str(test_file))
            
            assert len(loaded) == 3
            assert loaded[0]["text"] == "Sample 1"
        
        print("✅ CSV loading test passed")
    
    def test_instruction_formatting(self):
        """Test instruction tuning format"""
        samples = [
            {
                "instruction": "Translate to French",
                "input": "Hello world",
                "output": "Bonjour le monde"
            }
        ]
        
        formatted = format_for_instruction_tuning(samples)
        
        assert len(formatted) == 1
        assert "Translate to French" in formatted[0]["text"]
        assert "Hello world" in formatted[0]["text"]
        assert "Bonjour le monde" in formatted[0]["text"]
        
        print("✅ Instruction formatting test passed")


def run_all_tests():
    """Run all tests"""
    print("\n" + "="*60)
    print("RUNNING CORE DATA TESTS")
    print("="*60 + "\n")
    
    
    # Dataset formatting tests
    print("\nTesting Dataset Formatting...")
    test_formatter = TestDatasetFormatter()
    test_formatter.test_jsonl_saving()
    
    # Dataset loading tests
    print("\nTesting Dataset Loading...")
    test_loader = TestDatasetLoader()
    test_loader.test_jsonl_loading()
    test_loader.test_csv_loading()
    test_loader.test_instruction_formatting()
    
    print("\n" + "="*60)
    print("✅ ALL TESTS PASSED!")
    print("="*60 + "\n")


if __name__ == "__main__":
    run_all_tests()

