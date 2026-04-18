"""
Inference Service
Handles model loading and inference for trained models
"""

import torch
import logging
import json
from pathlib import Path
from typing import Dict, Any, Optional, List
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    GenerationConfig,
    TextIteratorStreamer,
)
from peft import PeftModel
from threading import Thread

from core.utils import setup_logger
from core.config import settings

logger = setup_logger("inference_service", log_file=str(settings.logs_dir / "inference_service.log"))

# Cache loaded models to avoid reloading
loaded_models: Dict[str, Dict[str, Any]] = {}


def list_available_models() -> List[Dict[str, Any]]:
    """
    List all available trained models
    
    Returns:
        List of model information dictionaries
    """
    models = []
    
    # Use configured models directory
    models_dir = Path(settings.models_dir)
    
    logger.info(f"Looking for models in: {models_dir.absolute()}")
    
    if not models_dir.exists():
        logger.warning(f"Models directory not found: {models_dir.absolute()}")
        return models
    
    # Find all model directories
    for model_dir in models_dir.iterdir():
        if not model_dir.is_dir():
            continue
        
        logger.info(f"Checking directory: {model_dir.name}")
        
        # Check for model files in 'final' subdirectory
        final_dir = model_dir / "final"
        if final_dir.exists():
            # Check for either full model (config.json) or LoRA adapter (adapter_config.json)
            has_config = (final_dir / "config.json").exists()
            has_adapter = (final_dir / "adapter_config.json").exists()
            
            if has_config or has_adapter:
                # Get model info
                try:
                    size_mb = sum(f.stat().st_size for f in final_dir.rglob("*") if f.is_file()) / (1024 * 1024)
                except Exception as e:
                    logger.warning(f"Error calculating size for {model_dir.name}: {e}")
                    size_mb = 0
                
                model_type = "full" if has_config else "lora"
                
                model_info = {
                    "model_id": model_dir.name,
                    "name": model_dir.name,
                    "path": str(final_dir.absolute()),
                    "size_mb": round(size_mb, 2),
                    "type": model_type,
                    "is_loaded": model_dir.name in loaded_models,
                }
                models.append(model_info)
                logger.info(f"Found {model_type} model: {model_info}")
            else:
                logger.debug(f"Skipping {model_dir.name}: no config.json or adapter_config.json found")
        else:
            logger.debug(f"Skipping {model_dir.name}: no final directory found")
    
    logger.info(f"Total models found: {len(models)}")
    return models


def load_model(model_path: str, device: str = "auto") -> Dict[str, Any]:
    """
    Load a trained model for inference (supports both full models and LoRA adapters)
    
    Args:
        model_path: Path to the model directory
        device: Device to load model on ('cuda', 'cpu', or 'auto')
    
    Returns:
        Dictionary with model and tokenizer
    """
    model_dir = Path(model_path)
    model_id = model_dir.parent.name
    
    # Check if already loaded
    if model_id in loaded_models:
        logger.info(f"Model {model_id} already loaded, returning cached version")
        return loaded_models[model_id]
    
    logger.info(f"Loading model from {model_path}")
    
    try:
        # Auto-detect device
        if device == "auto":
            if torch.cuda.is_available():
                device = "cuda"
            elif hasattr(torch.backends, 'mps') and torch.backends.mps.is_available():
                device = "mps"
            else:
                device = "cpu"
        
        logger.info(f"Loading on device: {device}")
        
        # Check if this is a LoRA adapter
        adapter_config_path = model_dir / "adapter_config.json"
        is_lora = adapter_config_path.exists()
        
        if is_lora:
            # Load adapter config to get base model name
            with open(adapter_config_path, 'r') as f:
                adapter_config = json.load(f)
            base_model_name = adapter_config.get('base_model_name_or_path')
            
            logger.info(f"Detected LoRA adapter, loading base model: {base_model_name}")
            
            # Load base model
            base_model = AutoModelForCausalLM.from_pretrained(
                base_model_name,
                device_map=device if device != "cpu" else None,
                trust_remote_code=True,
                torch_dtype=torch.float16 if device == "cuda" else torch.float32,
            )
            
            if device == "cpu":
                base_model = base_model.to(device)
            
            # Load LoRA adapter on top of base model
            logger.info(f"Loading LoRA adapter from {model_path}")
            model = PeftModel.from_pretrained(base_model, model_path)
            
            # Load tokenizer from adapter directory (or fallback to base model)
            try:
                tokenizer = AutoTokenizer.from_pretrained(
                    model_path,
                    trust_remote_code=True,
                )
            except:
                logger.info("Tokenizer not found in adapter directory, using base model tokenizer")
                tokenizer = AutoTokenizer.from_pretrained(
                    base_model_name,
                    trust_remote_code=True,
                )
        else:
            # Load full fine-tuned model
            logger.info("Loading full fine-tuned model")
            
            # Load tokenizer
            tokenizer = AutoTokenizer.from_pretrained(
                model_path,
                trust_remote_code=True,
            )
            
            # Load model
            model = AutoModelForCausalLM.from_pretrained(
                model_path,
                device_map=device if device != "cpu" else None,
                trust_remote_code=True,
                torch_dtype=torch.float16 if device == "cuda" else torch.float32,
            )
            
            if device == "cpu":
                model = model.to(device)
        
        # Set padding token
        if tokenizer.pad_token is None:
            tokenizer.pad_token = tokenizer.eos_token
            tokenizer.pad_token_id = tokenizer.eos_token_id
        
        model.eval()  # Set to evaluation mode
        
        # Cache the model
        loaded_models[model_id] = {
            "model": model,
            "tokenizer": tokenizer,
            "device": device,
            "model_path": model_path,
            "is_lora": is_lora,
        }
        
        logger.info(f"Model {model_id} loaded successfully on {device}")
        return loaded_models[model_id]
        
    except Exception as e:
        logger.error(f"Failed to load model from {model_path}: {e}", exc_info=True)
        raise


def unload_model(model_id: str) -> bool:
    """
    Unload a model from memory
    
    Args:
        model_id: Model identifier
    
    Returns:
        True if unloaded successfully
    """
    if model_id in loaded_models:
        del loaded_models[model_id]
        torch.cuda.empty_cache() if torch.cuda.is_available() else None
        logger.info(f"Model {model_id} unloaded from memory")
        return True
    return False


def generate_text(
    model_path: str,
    prompt: str,
    max_length: int = 256,
    temperature: float = 0.7,
    top_p: float = 0.9,
    top_k: int = 50,
    repetition_penalty: float = 1.1,
    num_return_sequences: int = 1,
) -> Dict[str, Any]:
    """
    Generate text using a loaded model
    
    Args:
        model_path: Path to the model
        prompt: Input text prompt
        max_length: Maximum length of generated text
        temperature: Sampling temperature (higher = more random)
        top_p: Nucleus sampling parameter
        top_k: Top-k sampling parameter
        repetition_penalty: Penalty for repeating tokens
        num_return_sequences: Number of sequences to generate
    
    Returns:
        Dictionary with generated text and metadata
    """
    try:
        # Load model if not already loaded
        model_data = load_model(model_path)
        model = model_data["model"]
        tokenizer = model_data["tokenizer"]
        device = model_data["device"]
        
        logger.info(f"Generating text for prompt: {prompt[:50]}...")
        
        # Encode input
        inputs = tokenizer(prompt, return_tensors="pt")
        
        # Move to device
        if device != "cpu":
            inputs = {k: v.to(device) for k, v in inputs.items()}
        else:
            inputs = {k: v.to("cpu") for k, v in inputs.items()}
        
        # Get input length for extracting only generated portion
        input_length = inputs["input_ids"].shape[1]
        
        # Generation config - use max_new_tokens for better control
        gen_config = GenerationConfig(
            max_new_tokens=max_length,  # Generate this many NEW tokens
            temperature=temperature,
            top_p=top_p,
            top_k=top_k,
            repetition_penalty=repetition_penalty,
            num_return_sequences=num_return_sequences,
            do_sample=temperature > 0,
            pad_token_id=tokenizer.pad_token_id,
            eos_token_id=tokenizer.eos_token_id,
        )
        
        # Generate
        with torch.no_grad():
            outputs = model.generate(
                **inputs,
                generation_config=gen_config,
            )
        
        # Decode outputs - extract only the generated portion (skip prompt)
        generated_texts = []
        full_texts = []
        for output in outputs:
            # Decode full text
            full_text = tokenizer.decode(output, skip_special_tokens=True)
            full_texts.append(full_text)
            
            # Extract only the generated part (after the prompt)
            generated_only = tokenizer.decode(output[input_length:], skip_special_tokens=True)
            generated_texts.append(generated_only)
        
        # Calculate tokens generated
        output_length = outputs.shape[1]
        tokens_generated = output_length - input_length
        
        logger.info(f"Generated {tokens_generated} new tokens")
        
        return {
            "success": True,
            "prompt": prompt,
            "generated_text": generated_texts[0] if num_return_sequences == 1 else generated_texts,
            "full_text": full_texts[0] if num_return_sequences == 1 else full_texts,
            "all_sequences": generated_texts,
            "tokens_generated": tokens_generated,
            "input_tokens": input_length,
            "total_tokens": output_length,
        }
        
    except Exception as e:
        logger.error(f"Generation failed: {e}", exc_info=True)
        return {
            "success": False,
            "error": str(e),
            "prompt": prompt,
        }


def generate_text_stream(
    model_path: str,
    prompt: str,
    max_length: int = 256,
    temperature: float = 0.7,
    top_p: float = 0.9,
    top_k: int = 50,
    repetition_penalty: float = 1.1,
):
    """
    Generate text with streaming (for real-time response)
    
    Yields:
        Generated text chunks
    """
    try:
        # Load model
        model_data = load_model(model_path)
        model = model_data["model"]
        tokenizer = model_data["tokenizer"]
        device = model_data["device"]
        
        # Encode input
        inputs = tokenizer(prompt, return_tensors="pt")
        
        # Move to device
        if device != "cpu":
            inputs = {k: v.to(device) for k, v in inputs.items()}
        else:
            inputs = {k: v.to("cpu") for k, v in inputs.items()}
        
        # Create streamer
        streamer = TextIteratorStreamer(tokenizer, skip_special_tokens=True)
        
        # Generation config
        gen_config = GenerationConfig(
            max_length=max_length,
            temperature=temperature,
            top_p=top_p,
            top_k=top_k,
            repetition_penalty=repetition_penalty,
            do_sample=temperature > 0,
            pad_token_id=tokenizer.pad_token_id,
            eos_token_id=tokenizer.eos_token_id,
        )
        
        # Generate in background thread
        generation_kwargs = {
            **inputs,
            "generation_config": gen_config,
            "streamer": streamer,
        }
        
        thread = Thread(target=model.generate, kwargs=generation_kwargs)
        thread.start()
        
        # Stream results
        for text_chunk in streamer:
            yield text_chunk
        
        thread.join()
        
    except Exception as e:
        logger.error(f"Streaming generation failed: {e}", exc_info=True)
        yield f"Error: {str(e)}"

