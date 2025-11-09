"""
Training and Model Metrics
"""

from typing import Dict, List, Optional
import numpy as np
from sklearn.metrics import accuracy_score, f1_score, precision_score, recall_score
import logging

logger = logging.getLogger(__name__)


class MetricsTracker:
    """Track training metrics over time"""
    
    def __init__(self):
        self.metrics = {
            "train_loss": [],
            "eval_loss": [],
            "learning_rate": [],
            "epoch": [],
            "step": [],
        }
        
    def log_metric(self, name: str, value: float, step: Optional[int] = None):
        """
        Log a metric value
        
        Args:
            name: Metric name
            value: Metric value
            step: Training step (optional)
        """
        if name not in self.metrics:
            self.metrics[name] = []
            
        self.metrics[name].append(value)
        
        if step is not None and "step" in self.metrics:
            self.metrics["step"].append(step)
            
    def log_metrics(self, metrics: Dict[str, float], step: Optional[int] = None):
        """
        Log multiple metrics at once
        
        Args:
            metrics: Dictionary of metric names and values
            step: Training step (optional)
        """
        for name, value in metrics.items():
            self.log_metric(name, value, step=None)
            
        if step is not None:
            self.log_metric("step", step)
            
    def get_metric(self, name: str) -> List[float]:
        """Get all values for a metric"""
        return self.metrics.get(name, [])
        
    def get_latest(self, name: str) -> Optional[float]:
        """Get latest value for a metric"""
        values = self.get_metric(name)
        return values[-1] if values else None
        
    def get_average(self, name: str, last_n: Optional[int] = None) -> Optional[float]:
        """
        Get average value for a metric
        
        Args:
            name: Metric name
            last_n: Average over last N values (None = all)
            
        Returns:
            Average value
        """
        values = self.get_metric(name)
        if not values:
            return None
            
        if last_n:
            values = values[-last_n:]
            
        return np.mean(values)
        
    def get_summary(self) -> Dict[str, Dict[str, float]]:
        """Get summary statistics for all metrics"""
        summary = {}
        
        for name, values in self.metrics.items():
            if not values:
                continue
                
            summary[name] = {
                "latest": values[-1],
                "mean": np.mean(values),
                "min": np.min(values),
                "max": np.max(values),
                "std": np.std(values),
            }
            
        return summary
        
    def reset(self):
        """Clear all metrics"""
        for name in self.metrics:
            self.metrics[name] = []


def calculate_perplexity(loss: float) -> float:
    """
    Calculate perplexity from loss
    
    Args:
        loss: Cross-entropy loss
        
    Returns:
        Perplexity score
    """
    return np.exp(loss)


def calculate_classification_metrics(
    predictions: List[int],
    labels: List[int],
    average: str = "weighted"
) -> Dict[str, float]:
    """
    Calculate classification metrics
    
    Args:
        predictions: Model predictions
        labels: True labels
        average: Averaging strategy for multiclass
        
    Returns:
        Dictionary of metrics
    """
    return {
        "accuracy": accuracy_score(labels, predictions),
        "precision": precision_score(labels, predictions, average=average, zero_division=0),
        "recall": recall_score(labels, predictions, average=average, zero_division=0),
        "f1": f1_score(labels, predictions, average=average, zero_division=0),
    }


def calculate_token_throughput(
    num_tokens: int,
    elapsed_time: float
) -> float:
    """
    Calculate token generation throughput
    
    Args:
        num_tokens: Number of tokens generated
        elapsed_time: Time elapsed in seconds
        
    Returns:
        Tokens per second
    """
    return num_tokens / elapsed_time if elapsed_time > 0 else 0


def calculate_model_size(model) -> Dict[str, int]:
    """
    Calculate model size in parameters and memory
    
    Args:
        model: PyTorch model
        
    Returns:
        Size information
    """
    import torch
    
    total_params = sum(p.numel() for p in model.parameters())
    trainable_params = sum(p.numel() for p in model.parameters() if p.requires_grad)
    
    # Estimate memory (rough approximation)
    param_memory = sum(p.numel() * p.element_size() for p in model.parameters())
    buffer_memory = sum(b.numel() * b.element_size() for b in model.buffers())
    
    return {
        "total_params": total_params,
        "trainable_params": trainable_params,
        "non_trainable_params": total_params - trainable_params,
        "param_memory_bytes": param_memory,
        "buffer_memory_bytes": buffer_memory,
        "total_memory_bytes": param_memory + buffer_memory,
        "total_memory_mb": (param_memory + buffer_memory) / (1024 ** 2),
    }

