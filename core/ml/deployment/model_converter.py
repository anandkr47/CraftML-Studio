"""
Model Format Converter
Converts models between different formats (GGUF, ONNX, etc.)
"""

import os
import shutil
import subprocess
from pathlib import Path
from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)


class ModelConverter:
    """
    Handles conversion between different model formats
    """
    
    def __init__(self):
        self.supported_formats = ["gguf", "onnx", "safetensors"]
    
    def convert_to_gguf(
        self,
        model_path: str,
        output_path: str,
        quantization: str = "Q4_K_M"
    ) -> Dict[str, Any]:
        """
        Convert model to GGUF format (for llama.cpp/Ollama)
        
        Args:
            model_path: Path to source model
            output_path: Path for output GGUF file
            quantization: Quantization type (Q4_K_M, Q5_K_M, Q8_0, etc.)
            
        Returns:
            Conversion result
        """
        try:
            logger.info(f"Converting model to GGUF format: {quantization}")
            
            # Check if llama.cpp is available
            if not self._check_llama_cpp():
                return {
                    "status": "failed",
                    "error": "llama.cpp not found. Please install llama.cpp"
                }
            
            # Create output directory
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            
            # Step 1: Convert to FP16 GGUF
            fp16_path = output_path.replace(".gguf", "_fp16.gguf")
            
            convert_cmd = [
                "python",
                "convert.py",  # llama.cpp convert script
                model_path,
                "--outfile", fp16_path,
                "--outtype", "f16"
            ]
            
            logger.info(f"Running conversion: {' '.join(convert_cmd)}")
            result = subprocess.run(
                convert_cmd,
                capture_output=True,
                text=True,
                timeout=3600  # 1 hour timeout
            )
            
            if result.returncode != 0:
                logger.error(f"Conversion failed: {result.stderr}")
                return {
                    "status": "failed",
                    "error": result.stderr
                }
            
            # Step 2: Quantize if needed
            if quantization != "f16":
                quantize_cmd = [
                    "quantize",  # llama.cpp quantize tool
                    fp16_path,
                    output_path,
                    quantization
                ]
                
                logger.info(f"Quantizing: {' '.join(quantize_cmd)}")
                result = subprocess.run(
                    quantize_cmd,
                    capture_output=True,
                    text=True,
                    timeout=3600
                )
                
                if result.returncode != 0:
                    logger.error(f"Quantization failed: {result.stderr}")
                    return {
                        "status": "failed",
                        "error": result.stderr
                    }
                
                # Remove FP16 intermediate file
                os.remove(fp16_path)
            else:
                # Rename FP16 to final output
                shutil.move(fp16_path, output_path)
            
            # Get file size
            file_size = os.path.getsize(output_path)
            
            logger.info(f"GGUF conversion successful: {output_path} ({file_size / 1024 / 1024:.2f} MB)")
            
            return {
                "status": "success",
                "output_path": output_path,
                "format": "gguf",
                "quantization": quantization,
                "size_mb": file_size / 1024 / 1024
            }
            
        except subprocess.TimeoutExpired:
            logger.error("Conversion timed out")
            return {
                "status": "failed",
                "error": "Conversion timed out after 1 hour"
            }
        except Exception as e:
            logger.error(f"GGUF conversion failed: {str(e)}")
            return {
                "status": "failed",
                "error": str(e)
            }
    
    def convert_to_onnx(
        self,
        model_path: str,
        output_path: str,
        opset_version: int = 14,
        optimize: bool = True
    ) -> Dict[str, Any]:
        """
        Convert model to ONNX format
        
        Args:
            model_path: Path to source model
            output_path: Path for output ONNX file
            opset_version: ONNX opset version
            optimize: Apply ONNX optimizations
            
        Returns:
            Conversion result
        """
        try:
            from optimum.onnxruntime import ORTModelForCausalLM
            from transformers import AutoTokenizer
            
            logger.info(f"Converting model to ONNX format (opset={opset_version})")
            
            # Create output directory
            os.makedirs(output_path, exist_ok=True)
            
            # Load and convert model
            logger.info(f"Loading model from {model_path}")
            ort_model = ORTModelForCausalLM.from_pretrained(
                model_path,
                export=True,
                opset=opset_version
            )
            
            # Save ONNX model
            logger.info(f"Saving ONNX model to {output_path}")
            ort_model.save_pretrained(output_path)
            
            # Also save tokenizer
            tokenizer = AutoTokenizer.from_pretrained(model_path)
            tokenizer.save_pretrained(output_path)
            
            # Apply optimizations if requested
            if optimize:
                logger.info("Applying ONNX optimizations")
                self._optimize_onnx(output_path)
            
            # Calculate total size
            total_size = sum(
                os.path.getsize(os.path.join(output_path, f))
                for f in os.listdir(output_path)
                if os.path.isfile(os.path.join(output_path, f))
            )
            
            logger.info(f"ONNX conversion successful: {output_path} ({total_size / 1024 / 1024:.2f} MB)")
            
            return {
                "status": "success",
                "output_path": output_path,
                "format": "onnx",
                "opset_version": opset_version,
                "optimized": optimize,
                "size_mb": total_size / 1024 / 1024
            }
            
        except ImportError:
            logger.error("optimum not installed")
            return {
                "status": "failed",
                "error": "optimum library not installed. Install with: pip install optimum[onnxruntime]"
            }
        except Exception as e:
            logger.error(f"ONNX conversion failed: {str(e)}")
            return {
                "status": "failed",
                "error": str(e)
            }
    
    def convert_to_safetensors(
        self,
        model_path: str,
        output_path: str
    ) -> Dict[str, Any]:
        """
        Convert model to SafeTensors format
        
        Args:
            model_path: Path to source model
            output_path: Path for output
            
        Returns:
            Conversion result
        """
        try:
            from transformers import AutoModelForCausalLM, AutoTokenizer
            
            logger.info("Converting model to SafeTensors format")
            
            # Create output directory
            os.makedirs(output_path, exist_ok=True)
            
            # Load model
            model = AutoModelForCausalLM.from_pretrained(model_path)
            tokenizer = AutoTokenizer.from_pretrained(model_path)
            
            # Save with safetensors
            model.save_pretrained(
                output_path,
                safe_serialization=True  # Use safetensors format
            )
            tokenizer.save_pretrained(output_path)
            
            # Calculate total size
            total_size = sum(
                os.path.getsize(os.path.join(output_path, f))
                for f in os.listdir(output_path)
                if os.path.isfile(os.path.join(output_path, f))
            )
            
            logger.info(f"SafeTensors conversion successful: {output_path}")
            
            return {
                "status": "success",
                "output_path": output_path,
                "format": "safetensors",
                "size_mb": total_size / 1024 / 1024
            }
            
        except Exception as e:
            logger.error(f"SafeTensors conversion failed: {str(e)}")
            return {
                "status": "failed",
                "error": str(e)
            }
    
    def _check_llama_cpp(self) -> bool:
        """Check if llama.cpp tools are available"""
        try:
            result = subprocess.run(
                ["quantize", "--help"],
                capture_output=True,
                timeout=5
            )
            return result.returncode == 0 or "llama" in result.stdout.decode().lower()
        except:
            return False
    
    def _optimize_onnx(self, model_path: str):
        """Apply ONNX optimizations"""
        try:
            from onnxruntime.transformers import optimizer
            from onnxruntime.transformers.fusion_options import FusionOptions
            
            # Find ONNX model file
            onnx_files = [f for f in os.listdir(model_path) if f.endswith('.onnx')]
            
            for onnx_file in onnx_files:
                file_path = os.path.join(model_path, onnx_file)
                
                # Optimize
                optimization_options = FusionOptions('gpt2')
                optimizer.optimize_model(
                    file_path,
                    model_type='gpt2',
                    num_heads=0,  # Auto-detect
                    hidden_size=0,  # Auto-detect
                    optimization_options=optimization_options
                )
                
                logger.info(f"Optimized {onnx_file}")
                
        except Exception as e:
            logger.warning(f"ONNX optimization failed (non-critical): {str(e)}")
    
    def convert(
        self,
        model_path: str,
        output_format: str,
        output_path: str,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Convert model to specified format
        
        Args:
            model_path: Source model path
            output_format: Target format (gguf, onnx, safetensors)
            output_path: Output path
            **kwargs: Format-specific options
            
        Returns:
            Conversion result
        """
        if output_format not in self.supported_formats:
            return {
                "status": "failed",
                "error": f"Unsupported format: {output_format}. Supported: {self.supported_formats}"
            }
        
        if output_format == "gguf":
            return self.convert_to_gguf(
                model_path,
                output_path,
                quantization=kwargs.get("quantization", "Q4_K_M")
            )
        elif output_format == "onnx":
            return self.convert_to_onnx(
                model_path,
                output_path,
                opset_version=kwargs.get("opset_version", 14),
                optimize=kwargs.get("optimize", True)
            )
        elif output_format == "safetensors":
            return self.convert_to_safetensors(model_path, output_path)
        
        return {
            "status": "failed",
            "error": f"Unknown format: {output_format}"
        }


# Global converter instance
model_converter = ModelConverter()

