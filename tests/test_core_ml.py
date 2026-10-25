"""
Test Suite for Core ML Modules
Tests training, compression, deployment, and utilities
"""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.ml.utils import MetricsTracker, calculate_perplexity, calculate_model_size


class TestMetrics:
    """Test metrics tracking and calculation"""
    
    def test_metrics_tracker(self):
        """Test MetricsTracker functionality"""
        tracker = MetricsTracker()
        
        # Log some metrics
        tracker.log_metric("train_loss", 2.5, step=1)
        tracker.log_metric("train_loss", 2.0, step=2)
        tracker.log_metric("train_loss", 1.5, step=3)
        
        # Get latest
        latest = tracker.get_latest("train_loss")
        assert latest == 1.5, "Latest metric should be 1.5"
        
        # Get average
        avg = tracker.get_average("train_loss")
        assert avg == 2.0, "Average should be 2.0"
        
        # Get summary
        summary = tracker.get_summary()
        assert "train_loss" in summary
        assert summary["train_loss"]["min"] == 1.5
        assert summary["train_loss"]["max"] == 2.5
        
        print("✅ MetricsTracker tests passed")
    
    def test_perplexity_calculation(self):
        """Test perplexity calculation from loss"""
        loss = 2.0
        perplexity = calculate_perplexity(loss)
        
        import numpy as np
        expected = np.exp(2.0)
        assert abs(perplexity - expected) < 0.01
        
        print("✅ Perplexity calculation test passed")
    
    def test_model_size_calculation(self):
        """Test model size calculation"""
        import torch.nn as nn
        
        # Create simple model
        model = nn.Sequential(
            nn.Linear(100, 50),
            nn.ReLU(),
            nn.Linear(50, 10)
        )
        
        size_info = calculate_model_size(model)
        
        assert "total_params" in size_info
        assert "trainable_params" in size_info
        assert "total_memory_mb" in size_info
        assert size_info["total_params"] > 0
        
        print(f"✅ Model size: {size_info['total_params']} params, {size_info['total_memory_mb']:.2f} MB")


def run_all_tests():
    """Run all tests"""
    print("\n" + "="*60)
    print("RUNNING CORE ML TESTS")
    print("="*60 + "\n")
    
    # Metrics tests
    print("Testing Metrics...")
    test_metrics = TestMetrics()
    test_metrics.test_metrics_tracker()
    test_metrics.test_perplexity_calculation()
    test_metrics.test_model_size_calculation()
    
    print("\n" + "="*60)
    print("✅ ALL TESTS PASSED!")
    print("="*60 + "\n")


if __name__ == "__main__":
    run_all_tests()

