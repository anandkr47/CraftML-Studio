"""
Core Data Processing Module
Dataset loading and formatting for fine-tuning
"""

from core.data.formatter import (
    DatasetFormatter,
    format_dataset,
    save_as_jsonl,
    save_as_csv
)
from core.data.dataset_utils import (
    DatasetLoader,
    load_and_prepare_dataset,
    format_for_instruction_tuning,
    format_for_chat
)

__all__ = [
    'DatasetFormatter',
    'format_dataset',
    'save_as_jsonl',
    'save_as_csv',
    'DatasetLoader',
    'load_and_prepare_dataset',
    'format_for_instruction_tuning',
    'format_for_chat',
]
