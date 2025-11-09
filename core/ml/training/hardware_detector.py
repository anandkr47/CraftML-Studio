"""
Hardware Detection and Configuration
Auto-detects available hardware (CUDA, ROCm, Metal) and configures training accordingly
"""

import torch
import platform
import logging
from typing import Dict, Any, Optional
import subprocess

logger = logging.getLogger(__name__)


class HardwareDetector:
    """
    Detects available hardware and recommends training configuration
    """
    
    def __init__(self):
        self.platform = platform.system()
        self.device_info = self._detect_device()
    
    def _detect_device(self) -> Dict[str, Any]:
        """
        Detect available hardware and capabilities
        
        Returns:
            Device information dict
        """
        info = {
            "platform": self.platform,
            "device_type": "cpu",
            "device_name": "CPU",
            "backend": "cpu",
            "cuda_available": False,
            "rocm_available": False,
            "mps_available": False,
            "gpu_count": 0,
            "total_vram_gb": 0,
            "recommended_strategy": "lora"
        }
        
        # Check CUDA (NVIDIA)
        if torch.cuda.is_available():
            info["cuda_available"] = True
            info["device_type"] = "cuda"
            info["backend"] = "cuda"
            info["gpu_count"] = torch.cuda.device_count()
            info["device_name"] = torch.cuda.get_device_name(0)
            
            # Get VRAM info
            if info["gpu_count"] > 0:
                total_memory = torch.cuda.get_device_properties(0).total_memory
                info["total_vram_gb"] = total_memory / (1024 ** 3)
            
            logger.info(f"CUDA detected: {info['device_name']}, VRAM: {info['total_vram_gb']:.2f} GB")
        
        # Check ROCm (AMD)
        elif self._check_rocm():
            info["rocm_available"] = True
            info["device_type"] = "cuda"  # ROCm uses CUDA API
            info["backend"] = "rocm"
            info["gpu_count"] = torch.cuda.device_count() if torch.cuda.is_available() else 0
            info["device_name"] = "AMD GPU (ROCm)"
            
            logger.info("ROCm detected")
        
        # Check Metal (Apple Silicon)
        elif hasattr(torch.backends, 'mps') and torch.backends.mps.is_available():
            info["mps_available"] = True
            info["device_type"] = "mps"
            info["backend"] = "metal"
            info["device_name"] = "Apple Silicon (M1/M2/M3)"
            info["gpu_count"] = 1
            
            # Estimate VRAM (Apple Unified Memory)
            info["total_vram_gb"] = self._estimate_apple_memory()
            
            logger.info(f"Metal (Apple Silicon) detected: {info['total_vram_gb']:.2f} GB unified memory")
        
        else:
            logger.info("No GPU detected, using CPU")
        
        # Recommend training strategy based on VRAM
        info["recommended_strategy"] = self._recommend_strategy(info["total_vram_gb"])
        
        return info
    
    def _check_rocm(self) -> bool:
        """Check if ROCm is available"""
        try:
            # Check for ROCm installation
            result = subprocess.run(
                ["rocm-smi"],
                capture_output=True,
                timeout=5
            )
            return result.returncode == 0
        except:
            return False
    
    def _estimate_apple_memory(self) -> float:
        """Estimate available memory on Apple Silicon"""
        try:
            import psutil
            # Apple Silicon uses unified memory
            # Assume ~70% of total RAM is available for ML
            total_ram = psutil.virtual_memory().total
            return (total_ram * 0.7) / (1024 ** 3)
        except:
            return 8.0  # Default estimate
    
    def _recommend_strategy(self, vram_gb: float) -> str:
        """
        Recommend training strategy based on available VRAM
        
        Args:
            vram_gb: Available VRAM in GB
            
        Returns:
            Recommended strategy
        """
        if vram_gb == 0:  # CPU
            return "lora"  # LoRA is most efficient for CPU
        elif vram_gb < 8:
            return "qlora"  # QLoRA for low VRAM
        elif vram_gb < 16:
            return "lora"  # Standard LoRA for mid VRAM
        else:
            return "full"  # Full fine-tuning for high VRAM
    
    def get_device(self) -> str:
        """
        Get PyTorch device string
        
        Returns:
            Device string (cuda, mps, cpu)
        """
        return self.device_info["device_type"]
    
    def get_device_map(self, auto: bool = True) -> Optional[str]:
        """
        Get device map for model loading
        
        Args:
            auto: Use auto device mapping
            
        Returns:
            Device map string
        """
        if auto and self.device_info["device_type"] != "cpu":
            return "auto"
        return None
    
    def get_compute_dtype(self) -> torch.dtype:
        """
        Get recommended compute dtype
        
        Returns:
            PyTorch dtype
        """
        if self.device_info["cuda_available"] or self.device_info["rocm_available"]:
            # Use bfloat16 if available, else float16
            if torch.cuda.is_bf16_supported():
                return torch.bfloat16
            return torch.float16
        elif self.device_info["mps_available"]:
            return torch.float16
        else:
            return torch.float32
    
    def supports_flash_attention(self) -> bool:
        """
        Check if hardware supports Flash Attention
        
        Returns:
            True if supported
        """
        # Flash Attention requires CUDA with compute capability >= 8.0
        if self.device_info["cuda_available"]:
            try:
                major, minor = torch.cuda.get_device_capability(0)
                return major >= 8
            except:
                return False
        return False
    
    def get_training_config(
        self,
        strategy: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get recommended training configuration
        
        Args:
            strategy: Override recommended strategy
            
        Returns:
            Training configuration dict
        """
        if strategy is None:
            strategy = self.device_info["recommended_strategy"]
        
        config = {
            "device": self.get_device(),
            "device_map": self.get_device_map(),
            "compute_dtype": self.get_compute_dtype(),
            "strategy": strategy,
            "use_4bit": strategy == "qlora",
            "use_8bit": False,
            "fp16": self.device_info["cuda_available"] and not torch.cuda.is_bf16_supported(),
            "bf16": self.device_info["cuda_available"] and torch.cuda.is_bf16_supported(),
            "use_flash_attention": self.supports_flash_attention(),
            "gradient_checkpointing": True,  # Save memory
            "per_device_train_batch_size": self._recommend_batch_size(strategy),
            "gradient_accumulation_steps": self._recommend_grad_accumulation(strategy)
        }
        
        logger.info(f"Training config: {config}")
        
        return config
    
    def _recommend_batch_size(self, strategy: str) -> int:
        """Recommend batch size based on strategy and VRAM"""
        vram_gb = self.device_info["total_vram_gb"]
        
        if strategy == "qlora":
            if vram_gb < 8:
                return 1
            elif vram_gb < 16:
                return 2
            else:
                return 4
        elif strategy == "lora":
            if vram_gb < 8:
                return 1
            elif vram_gb < 16:
                return 2
            elif vram_gb < 24:
                return 4
            else:
                return 8
        else:  # full
            if vram_gb < 16:
                return 1
            elif vram_gb < 24:
                return 2
            else:
                return 4
    
    def _recommend_grad_accumulation(self, strategy: str) -> int:
        """Recommend gradient accumulation steps"""
        vram_gb = self.device_info["total_vram_gb"]
        
        # More accumulation for less VRAM
        if vram_gb < 8:
            return 8
        elif vram_gb < 16:
            return 4
        else:
            return 2
    
    def print_info(self):
        """Print hardware information"""
        info = self.device_info
        
        print("\n" + "=" * 70)
        print("Hardware Detection Report")
        print("=" * 70)
        print(f"Platform: {info['platform']}")
        print(f"Device: {info['device_name']}")
        print(f"Backend: {info['backend']}")
        print(f"GPU Count: {info['gpu_count']}")
        print(f"VRAM: {info['total_vram_gb']:.2f} GB")
        print(f"Recommended Strategy: {info['recommended_strategy']}")
        print("=" * 70 + "\n")


# Global hardware detector
hardware_detector = HardwareDetector()

