"""
Custom Dataset Loader Plugin Example

This plugin demonstrates how to create a custom dataset loader
for special data formats or sources.
"""

from typing import List, Dict, Any, Iterator
import logging

logger = logging.getLogger(__name__)


class CustomDatasetLoader:
    """
    Example custom dataset loader plugin
    
    This is a template - implement your own loading logic here.
    """
    
    def __init__(self, config: Dict[str, Any] = None):
        """
        Initialize the loader
        
        Args:
            config: Configuration dictionary
        """
        self.config = config or {}
        self.name = "custom_loader"
        self.version = "0.1.0"
        self.supported_formats = [".custom", ".mydata"]
    
    def load(self, file_path: str, **kwargs) -> List[Dict[str, Any]]:
        """
        Load dataset from custom format
        
        Args:
            file_path: Path to dataset file
            **kwargs: Additional loading parameters
            
        Returns:
            List of data samples
        """
        logger.info(f"Loading dataset from {file_path}")
        
        # TODO: Implement your custom loading logic
        # Example steps:
        # 1. Open and read the file
        # 2. Parse the custom format
        # 3. Convert to standard format
        # 4. Return list of samples
        
        samples = []
        
        # Placeholder implementation
        # Replace with actual logic
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                # Parse your custom format here
                for line in f:
                    # Convert to standard format
                    sample = {
                        "instruction": "Sample instruction",
                        "input": "",
                        "output": line.strip()
                    }
                    samples.append(sample)
        except Exception as e:
            logger.error(f"Failed to load dataset: {e}")
            raise
        
        logger.info(f"Loaded {len(samples)} samples")
        return samples
    
    def stream(self, file_path: str, batch_size: int = 100) -> Iterator[List[Dict]]:
        """
        Stream dataset in batches (for large files)
        
        Args:
            file_path: Path to dataset file
            batch_size: Number of samples per batch
            
        Yields:
            Batches of data samples
        """
        logger.info(f"Streaming dataset from {file_path}")
        
        batch = []
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                for line in f:
                    sample = {
                        "instruction": "Sample instruction",
                        "input": "",
                        "output": line.strip()
                    }
                    batch.append(sample)
                    
                    if len(batch) >= batch_size:
                        yield batch
                        batch = []
                
                # Yield remaining samples
                if batch:
                    yield batch
                    
        except Exception as e:
            logger.error(f"Failed to stream dataset: {e}")
            raise
    
    def validate(self, file_path: str) -> bool:
        """
        Validate dataset file format
        
        Args:
            file_path: Path to dataset file
            
        Returns:
            True if valid
        """
        # TODO: Implement validation logic
        # Check file exists, format is correct, etc.
        
        import os
        if not os.path.exists(file_path):
            return False
        
        # Add more validation as needed
        return True
    
    def get_metadata(self, file_path: str) -> Dict[str, Any]:
        """
        Get dataset metadata
        
        Args:
            file_path: Path to dataset file
            
        Returns:
            Metadata dictionary
        """
        import os
        
        metadata = {
            "name": os.path.basename(file_path),
            "path": file_path,
            "format": self.name,
            "size_bytes": os.path.getsize(file_path) if os.path.exists(file_path) else 0
        }
        
        # Add custom metadata
        try:
            samples = self.load(file_path)
            metadata["num_samples"] = len(samples)
            metadata["avg_length"] = sum(len(s.get("output", "")) for s in samples) / len(samples) if samples else 0
        except:
            metadata["num_samples"] = "unknown"
            metadata["avg_length"] = "unknown"
        
        return metadata
    
    def convert_format(
        self,
        file_path: str,
        output_path: str,
        output_format: str = "jsonl"
    ) -> str:
        """
        Convert custom format to standard format
        
        Args:
            file_path: Input file path
            output_path: Output file path
            output_format: Target format (jsonl, csv, etc.)
            
        Returns:
            Path to converted file
        """
        logger.info(f"Converting {file_path} to {output_format}")
        
        # Load data
        samples = self.load(file_path)
        
        # Convert to target format
        if output_format == "jsonl":
            import json
            with open(output_path, 'w', encoding='utf-8') as f:
                for sample in samples:
                    f.write(json.dumps(sample, ensure_ascii=False) + '\n')
        elif output_format == "csv":
            import csv
            with open(output_path, 'w', newline='', encoding='utf-8') as f:
                if samples:
                    writer = csv.DictWriter(f, fieldnames=samples[0].keys())
                    writer.writeheader()
                    writer.writerows(samples)
        else:
            raise ValueError(f"Unsupported output format: {output_format}")
        
        logger.info(f"Converted dataset saved to {output_path}")
        return output_path


# Plugin registration
def register():
    """
    Register this plugin with CraftML Studio
    
    Returns:
        Plugin instance
    """
    return CustomDatasetLoader()


# Example usage
if __name__ == "__main__":
    loader = CustomDatasetLoader()
    
    # Load dataset
    samples = loader.load("./my_dataset.custom")
    print(f"Loaded {len(samples)} samples")
    
    # Get metadata
    metadata = loader.get_metadata("./my_dataset.custom")
    print(f"Metadata: {metadata}")
    
    # Convert format
    output = loader.convert_format(
        "./my_dataset.custom",
        "./my_dataset.jsonl",
        output_format="jsonl"
    )
    print(f"Converted to: {output}")

