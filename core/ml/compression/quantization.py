"""
Hugging Face model quantization: INT8 / INT4 (bitsandbytes), GPTQ and AWQ.

These methods run on NVIDIA GPUs; GGUF (CPU / Apple Silicon) lives in gguf.py.
LoRA adapters are merged into their base model first.
"""

import json
import logging
from pathlib import Path
from typing import Any, Dict

from core.ml.compression.calibration import SAMPLE_TEXTS
from core.utils.hub import cached_first

logger = logging.getLogger(__name__)


class QuantizationError(RuntimeError):
    """A quantization method can't run here (missing GPU/library) or failed."""


def _require_cuda(method: str) -> None:
    import torch

    if not torch.cuda.is_available():
        raise QuantizationError(
            f"{method.upper()} quantization needs an NVIDIA GPU (CUDA). "
            "On Apple Silicon or CPU, use GGUF instead."
        )


def merge_lora_adapter(adapter_dir: str, output_dir: str) -> str:
    """Merge a LoRA adapter into its base model and save the full model."""
    import torch
    from peft import PeftModel
    from transformers import AutoModelForCausalLM, AutoTokenizer

    base_name = json.loads((Path(adapter_dir) / "adapter_config.json").read_text())["base_model_name_or_path"]
    logger.info(f"Merging adapter {adapter_dir} into {base_name}")
    base = cached_first(AutoModelForCausalLM.from_pretrained, base_name, dtype=torch.float16, trust_remote_code=True)
    merged = PeftModel.from_pretrained(base, adapter_dir).merge_and_unload()
    merged.save_pretrained(output_dir, safe_serialization=True)
    try:
        tokenizer = AutoTokenizer.from_pretrained(adapter_dir, trust_remote_code=True)
    except Exception:  # noqa: BLE001 - adapter folder may lack a tokenizer
        tokenizer = cached_first(AutoTokenizer.from_pretrained, base_name, trust_remote_code=True)
    tokenizer.save_pretrained(output_dir)
    return output_dir


class ModelQuantizer:
    """Quantizes a full (non-adapter) Hugging Face model directory."""

    def __init__(self, model_path: str):
        self.model_path = model_path

    def _save(self, model, tokenizer, output_path: str) -> None:
        model.save_pretrained(output_path)
        tokenizer.save_pretrained(output_path)

    def quantize_int8(self, output_path: str) -> Dict[str, Any]:
        _require_cuda("int8")
        from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig

        model = AutoModelForCausalLM.from_pretrained(
            self.model_path,
            quantization_config=BitsAndBytesConfig(load_in_8bit=True),
            device_map="auto",
        )
        self._save(model, AutoTokenizer.from_pretrained(self.model_path), output_path)
        return {"status": "success", "output_path": output_path, "compression_type": "int8"}

    def quantize_int4(self, output_path: str, use_double_quant: bool = True) -> Dict[str, Any]:
        _require_cuda("int4")
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig

        config = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_compute_dtype=torch.float16,
            bnb_4bit_quant_type="nf4",
            bnb_4bit_use_double_quant=use_double_quant,
        )
        model = AutoModelForCausalLM.from_pretrained(self.model_path, quantization_config=config, device_map="auto")
        self._save(model, AutoTokenizer.from_pretrained(self.model_path), output_path)
        return {"status": "success", "output_path": output_path, "compression_type": "int4"}

    def quantize_gptq(self, output_path: str, bits: int = 4) -> Dict[str, Any]:
        _require_cuda("gptq")
        try:
            from auto_gptq import AutoGPTQForCausalLM, BaseQuantizeConfig
        except ImportError as exc:
            raise QuantizationError("GPTQ needs the auto-gptq package: pip install auto-gptq") from exc
        from transformers import AutoTokenizer

        tokenizer = AutoTokenizer.from_pretrained(self.model_path)
        examples = [tokenizer(text, return_tensors="pt") for text in SAMPLE_TEXTS]
        examples = [{"input_ids": e["input_ids"], "attention_mask": e["attention_mask"]} for e in examples]

        model = AutoGPTQForCausalLM.from_pretrained(
            self.model_path, BaseQuantizeConfig(bits=bits, group_size=128, desc_act=False)
        )
        model.quantize(examples)
        model.save_quantized(output_path, use_safetensors=True)
        tokenizer.save_pretrained(output_path)
        return {"status": "success", "output_path": output_path, "compression_type": f"gptq_{bits}bit"}

    def quantize_awq(self, output_path: str) -> Dict[str, Any]:
        _require_cuda("awq")
        try:
            from awq import AutoAWQForCausalLM
        except ImportError as exc:
            raise QuantizationError("AWQ needs the autoawq package: pip install autoawq") from exc
        from transformers import AutoTokenizer

        tokenizer = AutoTokenizer.from_pretrained(self.model_path, trust_remote_code=True)
        model = AutoAWQForCausalLM.from_pretrained(self.model_path)
        model.quantize(
            tokenizer,
            quant_config={"zero_point": True, "q_group_size": 128, "w_bit": 4, "version": "GEMM"},
            calib_data=SAMPLE_TEXTS * 8,
        )
        model.save_quantized(output_path)
        tokenizer.save_pretrained(output_path)
        return {"status": "success", "output_path": output_path, "compression_type": "awq_4bit"}


def quantize_model(model_path: str, output_path: str, method: str = "int4", **kwargs) -> Dict[str, Any]:
    """Quantize ``model_path`` with ``method`` (int8, int4, gptq, awq) into ``output_path``."""
    quantizer = ModelQuantizer(model_path)
    handlers = {
        "int8": quantizer.quantize_int8,
        "int4": quantizer.quantize_int4,
        "gptq": quantizer.quantize_gptq,
        "awq": quantizer.quantize_awq,
    }
    if method not in handlers:
        raise ValueError(f"Unknown quantization method: {method}")
    return handlers[method](output_path, **kwargs)
