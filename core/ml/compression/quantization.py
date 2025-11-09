"""
Model Quantization Engine
Supports INT8, INT4, and GPTQ quantization
"""

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer
from typing import Dict, Any, Literal
import logging

logger = logging.getLogger(__name__)


class ModelQuantizer:
    """Handles model quantization for compression"""
    
    def __init__(self, model_path: str):
        self.model_path = model_path
        self.model = None
        self.tokenizer = None
        
    def quantize_int8(self, output_path: str) -> Dict[str, Any]:
        """Quantize model to INT8"""
        logger.info(f"Loading model from {self.model_path}")
        
        self.model = AutoModelForCausalLM.from_pretrained(
            self.model_path,
            load_in_8bit=True,
            device_map="auto",
        )
        self.tokenizer = AutoTokenizer.from_pretrained(self.model_path)
        
        # Save quantized model
        self.model.save_pretrained(output_path)
        self.tokenizer.save_pretrained(output_path)
        
        logger.info(f"INT8 quantized model saved to {output_path}")
        
        return {
            "status": "success",
            "output_path": output_path,
            "compression_type": "int8",
        }
        
    def quantize_int4(self, output_path: str, use_double_quant: bool = True) -> Dict[str, Any]:
        """Quantize model to INT4 using bitsandbytes"""
        from transformers import BitsAndBytesConfig
        
        logger.info(f"Loading model from {self.model_path}")
        
        quantization_config = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_compute_dtype=torch.float16,
            bnb_4bit_quant_type="nf4",
            bnb_4bit_use_double_quant=use_double_quant,
        )
        
        self.model = AutoModelForCausalLM.from_pretrained(
            self.model_path,
            quantization_config=quantization_config,
            device_map="auto",
        )
        self.tokenizer = AutoTokenizer.from_pretrained(self.model_path)
        
        # Save quantized model
        self.model.save_pretrained(output_path)
        self.tokenizer.save_pretrained(output_path)
        
        logger.info(f"INT4 quantized model saved to {output_path}")
        
        return {
            "status": "success",
            "output_path": output_path,
            "compression_type": "int4",
        }
        
    def quantize_gptq(
        self,
        output_path: str,
        calibration_dataset: Any = None,
        bits: int = 4,
    ) -> Dict[str, Any]:
        """Quantize model using GPTQ"""
        try:
            from auto_gptq import AutoGPTQForCausalLM, BaseQuantizeConfig
        except ImportError:
            logger.error("auto-gptq not installed. Install with: pip install auto-gptq")
            raise
            
        logger.info(f"GPTQ quantization to {bits}-bit")
        
        quantize_config = BaseQuantizeConfig(
            bits=bits,
            group_size=128,
            desc_act=False,
        )
        
        # Load and quantize
        model = AutoGPTQForCausalLM.from_pretrained(
            self.model_path,
            quantize_config=quantize_config,
        )
        
        # Quantize with calibration data
        if calibration_dataset:
            model.quantize(calibration_dataset)
            
        # Save
        model.save_quantized(output_path)
        
        self.tokenizer = AutoTokenizer.from_pretrained(self.model_path)
        self.tokenizer.save_pretrained(output_path)
        
        logger.info(f"GPTQ quantized model saved to {output_path}")
        
        return {
            "status": "success",
            "output_path": output_path,
            "compression_type": f"gptq_{bits}bit",
        }


def quantize_model(
    model_path: str,
    output_path: str,
    method: Literal["int8", "int4", "gptq"] = "int4",
    **kwargs
) -> Dict[str, Any]:
    """
    Quantize a model using specified method
    
    Args:
        model_path: Path to the model to quantize
        output_path: Where to save quantized model
        method: Quantization method (int8, int4, gptq)
        **kwargs: Additional arguments for specific methods
        
    Returns:
        Dict with status and output information
    """
    quantizer = ModelQuantizer(model_path)
    
    if method == "int8":
        return quantizer.quantize_int8(output_path)
    elif method == "int4":
        return quantizer.quantize_int4(output_path, **kwargs)
    elif method == "gptq":
        return quantizer.quantize_gptq(output_path, **kwargs)
    else:
        raise ValueError(f"Unknown quantization method: {method}")

