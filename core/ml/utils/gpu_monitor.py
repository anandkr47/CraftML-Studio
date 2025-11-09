"""
GPU and System Resource Monitoring
"""

import psutil
import platform
from typing import Dict, List, Optional
import logging

logger = logging.getLogger(__name__)


def get_gpu_info() -> List[Dict[str, any]]:
    """
    Get GPU information
    
    Returns:
        List of GPU details (name, memory, utilization, etc.)
    """
    gpus = []
    
    try:
        import GPUtil
        gpu_list = GPUtil.getGPUs()
        
        for gpu in gpu_list:
            gpus.append({
                "id": gpu.id,
                "name": gpu.name,
                "memory_total": gpu.memoryTotal,
                "memory_used": gpu.memoryUsed,
                "memory_free": gpu.memoryFree,
                "memory_util": gpu.memoryUtil * 100,
                "gpu_util": gpu.load * 100,
                "temperature": gpu.temperature,
            })
    except ImportError:
        logger.warning("GPUtil not installed. Install with: pip install gputil")
    except Exception as e:
        logger.error(f"Error getting GPU info: {str(e)}")
        
    # Try NVIDIA SMI if GPUtil fails
    if not gpus:
        try:
            import torch
            if torch.cuda.is_available():
                for i in range(torch.cuda.device_count()):
                    props = torch.cuda.get_device_properties(i)
                    memory_allocated = torch.cuda.memory_allocated(i) / 1024**2
                    memory_reserved = torch.cuda.memory_reserved(i) / 1024**2
                    total_memory = props.total_memory / 1024**2
                    
                    gpus.append({
                        "id": i,
                        "name": props.name,
                        "memory_total": total_memory,
                        "memory_used": memory_allocated,
                        "memory_free": total_memory - memory_allocated,
                        "memory_util": (memory_allocated / total_memory) * 100,
                        "gpu_util": 0,  # PyTorch doesn't provide utilization
                        "temperature": 0,  # Not available via PyTorch
                    })
        except Exception as e:
            logger.error(f"Error getting GPU info via PyTorch: {str(e)}")
            
    return gpus


def get_cpu_info() -> Dict[str, any]:
    """
    Get CPU information
    
    Returns:
        CPU details (cores, usage, frequency, etc.)
    """
    return {
        "cpu_count": psutil.cpu_count(logical=True),
        "cpu_count_physical": psutil.cpu_count(logical=False),
        "cpu_percent": psutil.cpu_percent(interval=1, percpu=False),
        "cpu_percent_per_core": psutil.cpu_percent(interval=1, percpu=True),
        "cpu_freq": psutil.cpu_freq()._asdict() if psutil.cpu_freq() else None,
        "cpu_stats": psutil.cpu_stats()._asdict(),
    }


def get_memory_info() -> Dict[str, any]:
    """
    Get system memory information
    
    Returns:
        Memory details (total, available, used, etc.)
    """
    memory = psutil.virtual_memory()
    swap = psutil.swap_memory()
    
    return {
        "total": memory.total,
        "available": memory.available,
        "used": memory.used,
        "free": memory.free,
        "percent": memory.percent,
        "swap_total": swap.total,
        "swap_used": swap.used,
        "swap_free": swap.free,
        "swap_percent": swap.percent,
    }


def get_disk_info() -> Dict[str, any]:
    """
    Get disk information
    
    Returns:
        Disk usage details
    """
    disk = psutil.disk_usage('/')
    
    return {
        "total": disk.total,
        "used": disk.used,
        "free": disk.free,
        "percent": disk.percent,
    }


def get_system_info() -> Dict[str, any]:
    """
    Get complete system information
    
    Returns:
        Full system details
    """
    return {
        "platform": platform.system(),
        "platform_release": platform.release(),
        "platform_version": platform.version(),
        "architecture": platform.machine(),
        "processor": platform.processor(),
        "hostname": platform.node(),
    }


def get_all_metrics() -> Dict[str, any]:
    """
    Get all system metrics at once
    
    Returns:
        Complete metrics snapshot
    """
    return {
        "timestamp": psutil.boot_time(),
        "system": get_system_info(),
        "cpu": get_cpu_info(),
        "memory": get_memory_info(),
        "disk": get_disk_info(),
        "gpus": get_gpu_info(),
    }


class ResourceMonitor:
    """Real-time resource monitoring"""
    
    def __init__(self, interval: float = 1.0):
        """
        Initialize monitor
        
        Args:
            interval: Sampling interval in seconds
        """
        self.interval = interval
        self.history = []
        
    def snapshot(self) -> Dict[str, any]:
        """Take a snapshot of current resources"""
        snapshot = get_all_metrics()
        self.history.append(snapshot)
        return snapshot
        
    def get_history(self, limit: Optional[int] = None) -> List[Dict[str, any]]:
        """
        Get monitoring history
        
        Args:
            limit: Maximum number of entries to return
            
        Returns:
            List of historical snapshots
        """
        if limit:
            return self.history[-limit:]
        return self.history
        
    def clear_history(self):
        """Clear monitoring history"""
        self.history = []

