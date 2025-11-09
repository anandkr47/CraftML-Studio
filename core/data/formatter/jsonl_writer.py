"""
Dataset Formatter
Convert data to various formats (JSONL, CSV, Parquet)
"""

import json
from typing import List, Dict, Any, Optional
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


class DatasetFormatter:
    """Format datasets for training"""
    
    def __init__(self, output_dir: str = "./datasets"):
        """
        Initialize formatter
        
        Args:
            output_dir: Directory to save formatted datasets
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
    def to_jsonl(
        self,
        data: List[Dict[str, Any]],
        filename: str = "dataset.jsonl"
    ) -> str:
        """
        Save data as JSONL (JSON Lines)
        
        Args:
            data: List of data dictionaries
            filename: Output filename
            
        Returns:
            Path to saved file
        """
        output_path = self.output_dir / filename
        
        with open(output_path, 'w', encoding='utf-8') as f:
            for item in data:
                f.write(json.dumps(item, ensure_ascii=False) + '\n')
                
        logger.info(f"Saved {len(data)} items to {output_path}")
        return str(output_path)
        
    def to_instruction_format(
        self,
        data: List[Dict[str, Any]],
        instruction_key: str = "instruction",
        input_key: str = "input",
        output_key: str = "output",
        filename: str = "instruction_dataset.jsonl"
    ) -> str:
        """
        Format data for instruction fine-tuning
        
        Args:
            data: List of data dictionaries
            instruction_key: Key for instruction field
            input_key: Key for input field
            output_key: Key for output field
            filename: Output filename
            
        Returns:
            Path to saved file
        """
        formatted_data = []
        
        for item in data:
            formatted_item = {
                "instruction": item.get(instruction_key, ""),
                "input": item.get(input_key, ""),
                "output": item.get(output_key, ""),
            }
            formatted_data.append(formatted_item)
            
        return self.to_jsonl(formatted_data, filename)
        
    def to_conversation_format(
        self,
        data: List[Dict[str, Any]],
        user_key: str = "user",
        assistant_key: str = "assistant",
        filename: str = "conversation_dataset.jsonl"
    ) -> str:
        """
        Format data for conversation fine-tuning
        
        Args:
            data: List of data dictionaries
            user_key: Key for user messages
            assistant_key: Key for assistant messages
            filename: Output filename
            
        Returns:
            Path to saved file
        """
        formatted_data = []
        
        for item in data:
            formatted_item = {
                "messages": [
                    {"role": "user", "content": item.get(user_key, "")},
                    {"role": "assistant", "content": item.get(assistant_key, "")},
                ]
            }
            formatted_data.append(formatted_item)
            
        return self.to_jsonl(formatted_data, filename)
        
    def to_text_format(
        self,
        texts: List[str],
        filename: str = "text_dataset.txt"
    ) -> str:
        """
        Save as plain text (one document per line)
        
        Args:
            texts: List of text strings
            filename: Output filename
            
        Returns:
            Path to saved file
        """
        output_path = self.output_dir / filename
        
        with open(output_path, 'w', encoding='utf-8') as f:
            for text in texts:
                f.write(text.strip() + '\n')
                
        logger.info(f"Saved {len(texts)} texts to {output_path}")
        return str(output_path)
        
    def to_csv(
        self,
        data: List[Dict[str, Any]],
        filename: str = "dataset.csv"
    ) -> str:
        """
        Save data as CSV
        
        Args:
            data: List of data dictionaries
            filename: Output filename
            
        Returns:
            Path to saved file
        """
        import csv
        
        if not data:
            logger.warning("No data to save")
            return ""
            
        output_path = self.output_dir / filename
        
        # Get all keys
        keys = set()
        for item in data:
            keys.update(item.keys())
        keys = sorted(keys)
        
        with open(output_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=keys)
            writer.writeheader()
            writer.writerows(data)
            
        logger.info(f"Saved {len(data)} items to {output_path}")
        return str(output_path)
        
    def crawled_to_training_format(
        self,
        crawled_pages: List[Dict[str, Any]],
        format_type: str = "text",
        filename: Optional[str] = None
    ) -> str:
        """
        Convert crawled pages to training format
        
        Args:
            crawled_pages: List of crawled page dictionaries
            format_type: Output format (text, jsonl, instruction)
            filename: Output filename (auto-generated if None)
            
        Returns:
            Path to saved file
        """
        if not filename:
            filename = f"crawled_dataset.{format_type}"
            
        if format_type == "text":
            texts = [page["content"] for page in crawled_pages if page.get("content")]
            return self.to_text_format(texts, filename)
            
        elif format_type == "jsonl":
            return self.to_jsonl(crawled_pages, filename)
            
        elif format_type == "instruction":
            # Convert crawled content to instruction format
            # Use title as instruction, content as output
            instruction_data = []
            for page in crawled_pages:
                if page.get("content") and page.get("title"):
                    instruction_data.append({
                        "instruction": f"Provide information about: {page['title']}",
                        "input": "",
                        "output": page["content"]
                    })
            return self.to_instruction_format(instruction_data, filename=filename)
            
        else:
            raise ValueError(f"Unknown format type: {format_type}")


def format_dataset(
    data: List[Dict[str, Any]],
    output_path: str,
    format_type: str = "jsonl",
    **kwargs
) -> str:
    """
    High-level function to format a dataset
    
    Args:
        data: List of data dictionaries
        output_path: Output file path
        format_type: Format type (jsonl, csv, text, instruction, conversation)
        **kwargs: Additional formatting options
        
    Returns:
        Path to saved file
    """
    output_path = Path(output_path)
    formatter = DatasetFormatter(output_dir=str(output_path.parent))
    
    if format_type == "jsonl":
        return formatter.to_jsonl(data, filename=output_path.name)
    elif format_type == "csv":
        return formatter.to_csv(data, filename=output_path.name)
    elif format_type == "instruction":
        return formatter.to_instruction_format(data, filename=output_path.name, **kwargs)
    elif format_type == "conversation":
        return formatter.to_conversation_format(data, filename=output_path.name, **kwargs)
    else:
        raise ValueError(f"Unknown format type: {format_type}")


def save_as_jsonl(
    data: List[Dict[str, Any]],
    output_path: str
) -> str:
    """
    Save data as JSONL format
    
    Args:
        data: List of data dictionaries
        output_path: Output file path
        
    Returns:
        Path to saved file
    """
    return format_dataset(data, output_path, format_type="jsonl")


def save_as_csv(
    data: List[Dict[str, Any]],
    output_path: str
) -> str:
    """
    Save data as CSV format
    
    Args:
        data: List of data dictionaries
        output_path: Output file path
        
    Returns:
        Path to saved file
    """
    return format_dataset(data, output_path, format_type="csv")

