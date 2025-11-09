"""
Dataset Loading Utilities
Unified dataset loading for training, fine-tuning, and evaluation
"""

import json
from pathlib import Path
from typing import List, Dict, Any, Optional, Union
from datasets import Dataset, load_dataset
from torch.utils.data import DataLoader
import logging

logger = logging.getLogger(__name__)


class DatasetLoader:
    """Load and prepare datasets for training"""
    
    @staticmethod
    def load_jsonl(file_path: str) -> List[Dict[str, Any]]:
        """
        Load dataset from JSONL file
        
        Args:
            file_path: Path to JSONL file
            
        Returns:
            List of data samples
        """
        samples = []
        with open(file_path, 'r', encoding='utf-8') as f:
            for line in f:
                if line.strip():
                    samples.append(json.loads(line))
        
        logger.info(f"Loaded {len(samples)} samples from {file_path}")
        return samples
    
    @staticmethod
    def load_csv(file_path: str, text_column: str = "text") -> List[Dict[str, Any]]:
        """
        Load dataset from CSV file
        
        Args:
            file_path: Path to CSV file
            text_column: Name of the column containing text
            
        Returns:
            List of data samples
        """
        import pandas as pd
        
        df = pd.read_csv(file_path)
        samples = df.to_dict('records')
        
        logger.info(f"Loaded {len(samples)} samples from {file_path}")
        return samples
    
    @staticmethod
    def load_text(file_path: str, chunk_size: int = 512) -> List[Dict[str, Any]]:
        """
        Load plain text file and split into chunks
        
        Args:
            file_path: Path to text file
            chunk_size: Number of characters per chunk
            
        Returns:
            List of data samples
        """
        with open(file_path, 'r', encoding='utf-8') as f:
            text = f.read()
        
        # Split into chunks
        samples = []
        for i in range(0, len(text), chunk_size):
            chunk = text[i:i+chunk_size]
            if chunk.strip():
                samples.append({"text": chunk})
        
        logger.info(f"Created {len(samples)} chunks from {file_path}")
        return samples
    
    @staticmethod
    def load_from_path(
        file_path: str,
        format_type: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Auto-detect and load dataset from file
        
        Args:
            file_path: Path to dataset file
            format_type: Force specific format (jsonl, csv, txt)
            
        Returns:
            List of data samples
        """
        path = Path(file_path)
        
        if not path.exists():
            raise FileNotFoundError(f"Dataset file not found: {file_path}")
        
        # Detect format
        if format_type is None:
            format_type = path.suffix[1:]  # Remove dot
        
        format_type = format_type.lower()
        
        if format_type == "jsonl":
            return DatasetLoader.load_jsonl(file_path)
        elif format_type == "csv":
            return DatasetLoader.load_csv(file_path)
        elif format_type in ["txt", "text"]:
            return DatasetLoader.load_text(file_path)
        else:
            raise ValueError(f"Unsupported format: {format_type}")
    
    @staticmethod
    def prepare_for_training(
        samples: List[Dict[str, Any]],
        tokenizer,
        max_length: int = 512,
        text_field: str = "text"
    ) -> Dataset:
        """
        Prepare dataset for training with tokenization
        
        Args:
            samples: List of data samples
            tokenizer: HuggingFace tokenizer
            max_length: Maximum sequence length
            text_field: Field containing text to tokenize
            
        Returns:
            HuggingFace Dataset object
        """
        from datasets import Dataset
        
        # Create HuggingFace dataset
        dataset = Dataset.from_list(samples)
        
        # Tokenize
        def tokenize_function(examples):
            # Handle different field names
            texts = examples.get(text_field) or examples.get("input") or examples.get("instruction")
            
            return tokenizer(
                texts,
                padding="max_length",
                truncation=True,
                max_length=max_length,
                return_tensors=None
            )
        
        tokenized = dataset.map(
            tokenize_function,
            batched=True,
            remove_columns=dataset.column_names
        )
        
        logger.info(f"Tokenized {len(tokenized)} samples")
        return tokenized
    
    @staticmethod
    def create_dataloader(
        dataset: Dataset,
        batch_size: int = 4,
        shuffle: bool = True,
        num_workers: int = 0
    ) -> DataLoader:
        """
        Create PyTorch DataLoader from dataset
        
        Args:
            dataset: HuggingFace Dataset
            batch_size: Batch size
            shuffle: Whether to shuffle data
            num_workers: Number of data loading workers
            
        Returns:
            PyTorch DataLoader
        """
        from torch.utils.data import DataLoader as TorchDataLoader
        
        dataloader = TorchDataLoader(
            dataset,
            batch_size=batch_size,
            shuffle=shuffle,
            num_workers=num_workers
        )
        
        return dataloader


def load_and_prepare_dataset(
    file_path: str,
    tokenizer,
    batch_size: int = 4,
    max_length: int = 512,
    text_field: str = "text",
    train_test_split: float = 0.0
) -> Union[DataLoader, tuple]:
    """
    High-level function to load and prepare dataset
    
    Args:
        file_path: Path to dataset file
        tokenizer: HuggingFace tokenizer
        batch_size: Batch size for DataLoader
        max_length: Maximum sequence length
        text_field: Field containing text
        train_test_split: If > 0, split into train/test sets
        
    Returns:
        DataLoader or tuple of (train_loader, test_loader)
    """
    loader = DatasetLoader()
    
    # Load samples
    samples = loader.load_from_path(file_path)
    
    # Prepare dataset
    dataset = loader.prepare_for_training(
        samples=samples,
        tokenizer=tokenizer,
        max_length=max_length,
        text_field=text_field
    )
    
    # Split if requested
    if train_test_split > 0:
        split_dataset = dataset.train_test_split(test_size=train_test_split)
        train_loader = loader.create_dataloader(
            split_dataset['train'],
            batch_size=batch_size,
            shuffle=True
        )
        test_loader = loader.create_dataloader(
            split_dataset['test'],
            batch_size=batch_size,
            shuffle=False
        )
        return train_loader, test_loader
    else:
        return loader.create_dataloader(
            dataset,
            batch_size=batch_size,
            shuffle=True
        )


def format_for_instruction_tuning(
    samples: List[Dict[str, Any]],
    template: str = "{instruction}\n\n{input}\n\n{output}"
) -> List[Dict[str, str]]:
    """
    Format samples for instruction tuning
    
    Args:
        samples: List of samples with instruction/input/output fields
        template: Template string for formatting
        
    Returns:
        List of formatted samples
    """
    formatted = []
    
    for sample in samples:
        text = template.format(
            instruction=sample.get("instruction", ""),
            input=sample.get("input", ""),
            output=sample.get("output", "")
        )
        
        formatted.append({"text": text})
    
    return formatted


def format_for_chat(samples: List[Dict[str, Any]]) -> List[Dict[str, str]]:
    """
    Format samples for chat/conversation fine-tuning
    
    Args:
        samples: List of samples with 'messages' field
        
    Returns:
        List of formatted samples
    """
    formatted = []
    
    for sample in samples:
        if "messages" in sample:
            # Format as conversation
            conversation = []
            for msg in sample["messages"]:
                role = msg.get("role", "user")
                content = msg.get("content", "")
                conversation.append(f"{role.capitalize()}: {content}")
            
            text = "\n".join(conversation)
            formatted.append({"text": text})
        else:
            # Assume question/answer format
            text = f"User: {sample.get('question', '')}\nAssistant: {sample.get('answer', '')}"
            formatted.append({"text": text})
    
    return formatted

