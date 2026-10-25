"""Hugging Face transformers backend (full models and LoRA adapters)."""

import json
import threading
from pathlib import Path
from typing import Iterator, List, Optional

from core.utils import setup_logger
from core.utils.hub import cached_first
from core.config import settings

from .types import FALLBACK_STOP, GenerationParams, InferenceError, Message, StopTrimmer, Usage, format_messages_fallback

logger = setup_logger("inference_transformers", log_file=str(settings.logs_dir / "inference_service.log"))


def detect_device(requested: str = "auto") -> str:
    import torch

    if requested != "auto":
        return requested
    if torch.cuda.is_available():
        return "cuda"
    if getattr(torch.backends, "mps", None) and torch.backends.mps.is_available():
        return "mps"
    return "cpu"


class TransformersBackend:
    def __init__(self, path: str, device: str = "auto"):
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer

        self.path = path
        self.device = detect_device(device)
        self._torch = torch
        self._lock = threading.Lock()  # one generation at a time per model

        dtype = torch.float16 if self.device in ("cuda", "mps") else torch.float32
        adapter_cfg = Path(path) / "adapter_config.json"
        self.is_lora = adapter_cfg.exists()
        # bitsandbytes / GPTQ / AWQ checkpoints carry their own quantization config and
        # must be placed by accelerate (device_map) instead of .to(device).
        self.quantized = self._is_quantized(path)

        try:
            if self.is_lora:
                from peft import PeftModel

                base_name = json.loads(adapter_cfg.read_text()).get("base_model_name_or_path")
                logger.info(f"Loading base model {base_name} for adapter {path}")
                base = cached_first(AutoModelForCausalLM.from_pretrained, base_name, dtype=dtype, trust_remote_code=True)
                self.model = PeftModel.from_pretrained(base, path)
                try:
                    self.tokenizer = AutoTokenizer.from_pretrained(path, trust_remote_code=True)
                except Exception:
                    self.tokenizer = cached_first(AutoTokenizer.from_pretrained, base_name, trust_remote_code=True)
            else:
                logger.info(f"Loading model {path}")
                self.tokenizer = cached_first(AutoTokenizer.from_pretrained, path, trust_remote_code=True)
                if self.quantized:
                    self.model = cached_first(AutoModelForCausalLM.from_pretrained, path, device_map="auto", trust_remote_code=True)
                else:
                    self.model = cached_first(AutoModelForCausalLM.from_pretrained, path, dtype=dtype, trust_remote_code=True)
        except Exception as exc:
            raise InferenceError(f"Failed to load model '{path}': {exc}") from exc

        if not self.quantized:
            self.model.to(self.device)
        self.model.eval()
        if self.tokenizer.pad_token is None:
            self.tokenizer.pad_token = self.tokenizer.eos_token

    @staticmethod
    def _is_quantized(path: str) -> bool:
        try:
            return "quantization_config" in json.loads((Path(path) / "config.json").read_text())
        except (OSError, ValueError):
            return False

    def perplexity(self, texts: List[str], max_length: int = 512) -> Optional[float]:
        """Perplexity over ``texts`` (lower is better); None if nothing could be scored."""
        import math

        total_nll, total_tokens = 0.0, 0
        for text in texts:
            enc = self.tokenizer(text, return_tensors="pt", truncation=True, max_length=max_length)
            enc = {k: v.to(self.model.device) for k, v in enc.items()}
            n = enc["input_ids"].shape[1] - 1
            if n < 1:
                continue
            with self._torch.no_grad():
                loss = self.model(**enc, labels=enc["input_ids"]).loss.item()
            total_nll += loss * n
            total_tokens += n
        return math.exp(total_nll / total_tokens) if total_tokens else None

    # ------------------------------------------------------------------
    def _prompt(self, messages: List[Message]) -> str:
        if getattr(self.tokenizer, "chat_template", None):
            return self.tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        return format_messages_fallback(messages)

    def count_tokens(self, text: str) -> int:
        return len(self.tokenizer.encode(text, add_special_tokens=False))

    def stream(self, messages: List[Message], params: GenerationParams, usage: Usage) -> Iterator[str]:
        from transformers import StoppingCriteria, StoppingCriteriaList, TextIteratorStreamer

        prompt = self._prompt(messages)
        inputs = self.tokenizer(prompt, return_tensors="pt", add_special_tokens=False).to(self.device)
        usage.prompt_tokens = int(inputs["input_ids"].shape[1])

        cancel = threading.Event()

        class _Cancel(StoppingCriteria):
            def __call__(self, input_ids, scores, **kwargs):
                return cancel.is_set()

        streamer = TextIteratorStreamer(self.tokenizer, skip_prompt=True, skip_special_tokens=True)
        gen_kwargs = dict(
            **inputs,
            streamer=streamer,
            max_new_tokens=params.max_tokens,
            do_sample=params.temperature > 0,
            repetition_penalty=params.repetition_penalty,
            top_k=params.top_k,
            top_p=params.top_p,
            pad_token_id=self.tokenizer.pad_token_id,
            eos_token_id=self.tokenizer.eos_token_id,
            stopping_criteria=StoppingCriteriaList([_Cancel()]),
        )
        if params.temperature > 0:
            gen_kwargs["temperature"] = params.temperature
        stops = list(params.stop or [])
        if not getattr(self.tokenizer, "chat_template", None):
            stops.append(FALLBACK_STOP)  # end of the assistant turn in the plain-text prompt
        if stops:
            gen_kwargs.update(stop_strings=stops, tokenizer=self.tokenizer)
        trimmer = StopTrimmer(stops)  # generate() keeps the stop string in its output; the API must not

        errors: List[BaseException] = []

        def run():
            try:
                with self._torch.no_grad():
                    self.model.generate(**gen_kwargs)
            except BaseException as exc:  # noqa: BLE001 - must unblock the streamer
                errors.append(exc)
                streamer.on_finalized_text("", stream_end=True)

        with self._lock:
            thread = threading.Thread(target=run, daemon=True)
            thread.start()
            text = ""
            try:
                for delta in streamer:
                    piece = trimmer.feed(delta)
                    if piece:
                        text += piece
                        yield piece
                    if trimmer.done:
                        break
                tail = trimmer.flush()
                if tail:
                    text += tail
                    yield tail
            finally:
                cancel.set()  # also fires when the client disconnects mid-stream
                thread.join()

        if errors:
            raise InferenceError(f"Generation failed: {errors[0]}")

        usage.completion_tokens = self.count_tokens(text)
        usage.finish_reason = "length" if usage.completion_tokens >= params.max_tokens else "stop"

    def close(self) -> None:
        del self.model
        if self.device == "cuda":
            self._torch.cuda.empty_cache()
