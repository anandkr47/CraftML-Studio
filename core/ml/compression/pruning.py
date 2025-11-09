"""
Model Pruning Engine
Supports magnitude pruning and structured pruning
"""

import torch
import torch.nn as nn
from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)


class ModelPruner:
    """Handles model pruning for compression"""
    
    def __init__(self, model):
        self.model = model
        
    def magnitude_pruning(
        self,
        amount: float = 0.3,
        layers_to_prune: Optional[list] = None
    ) -> Dict[str, Any]:
        """
        Apply magnitude-based unstructured pruning
        
        Args:
            amount: Fraction of parameters to prune (0.0 to 1.0)
            layers_to_prune: List of layer names to prune (None = all linear layers)
            
        Returns:
            Pruning statistics
        """
        import torch.nn.utils.prune as prune
        
        logger.info(f"Applying magnitude pruning with {amount*100}% sparsity")
        
        parameters_to_prune = []
        
        # Identify layers to prune
        for name, module in self.model.named_modules():
            if isinstance(module, nn.Linear):
                if layers_to_prune is None or name in layers_to_prune:
                    parameters_to_prune.append((module, 'weight'))
                    
        # Apply pruning
        prune.global_unstructured(
            parameters_to_prune,
            pruning_method=prune.L1Unstructured,
            amount=amount,
        )
        
        # Calculate sparsity
        total_params = 0
        pruned_params = 0
        
        for module, param_name in parameters_to_prune:
            total_params += module.weight.nelement()
            pruned_params += torch.sum(module.weight == 0).item()
            
        sparsity = pruned_params / total_params if total_params > 0 else 0
        
        logger.info(f"Pruning complete. Sparsity: {sparsity*100:.2f}%")
        
        return {
            "status": "success",
            "sparsity": sparsity,
            "total_params": total_params,
            "pruned_params": pruned_params,
        }
        
    def structured_pruning(
        self,
        amount: float = 0.3,
        dim: int = 0
    ) -> Dict[str, Any]:
        """
        Apply structured pruning (remove entire channels/neurons)
        
        Args:
            amount: Fraction of structures to prune
            dim: Dimension along which to prune (0=output, 1=input)
            
        Returns:
            Pruning statistics
        """
        import torch.nn.utils.prune as prune
        
        logger.info(f"Applying structured pruning with {amount*100}% sparsity")
        
        for name, module in self.model.named_modules():
            if isinstance(module, nn.Linear):
                prune.ln_structured(
                    module,
                    name='weight',
                    amount=amount,
                    n=2,
                    dim=dim
                )
                
        logger.info("Structured pruning complete")
        
        return {
            "status": "success",
            "pruning_type": "structured",
            "amount": amount,
        }
        
    def make_permanent(self):
        """Make pruning permanent by removing masks"""
        import torch.nn.utils.prune as prune
        
        for module in self.model.modules():
            if isinstance(module, nn.Linear):
                try:
                    prune.remove(module, 'weight')
                except ValueError:
                    pass  # No pruning mask to remove
                    
        logger.info("Pruning masks removed, changes are now permanent")


def prune_model(
    model,
    method: str = "magnitude",
    amount: float = 0.3,
    **kwargs
) -> Dict[str, Any]:
    """
    Prune a model using specified method
    
    Args:
        model: PyTorch model to prune
        method: Pruning method ("magnitude" or "structured")
        amount: Fraction of parameters/structures to prune
        **kwargs: Additional method-specific arguments
        
    Returns:
        Dict with pruning statistics
    """
    pruner = ModelPruner(model)
    
    if method == "magnitude":
        result = pruner.magnitude_pruning(amount=amount, **kwargs)
    elif method == "structured":
        result = pruner.structured_pruning(amount=amount, **kwargs)
    else:
        raise ValueError(f"Unknown pruning method: {method}")
        
    # Make pruning permanent
    pruner.make_permanent()
    
    return result

