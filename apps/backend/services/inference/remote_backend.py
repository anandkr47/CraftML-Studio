"""
Remote inference backend: streams chat completions from a provider endpoint.

* ``kind="openai"``: any OpenAI-compatible server (Together, RunPod serverless vLLM, an SSH-tunnelled
  vLLM/llama.cpp/Ollama).  Standard SSE chat-completion chunks.
* ``kind="replicate"``: Replicate's predictions API with its server-sent-event stream.  Language
  models there accept different inputs, so this adapter is best-effort.

Token counts come from the provider when it reports them (``stream_options.include_usage``),
otherwise they are estimates (about 4 characters per token), which is fine for display and budgeting.
"""

from __future__ import annotations

import json
from typing import Any, Dict, Iterator, List, Optional

from core.cloud.http import Http, StreamResponse, default_http
from core.cloud.providers.base import InferenceEndpoint
from core.cloud.secrets import redact, register_secret

from .types import GenerationParams, InferenceError, Message, Usage


def estimate_tokens(text: str) -> int:
    return max(1, len(text) // 4) if text else 0


def _check_status(response: StreamResponse, provider_name: str) -> None:
    if response.status < 400:
        return
    body = redact(response.read_text()[:300].replace("\n", " "))
    reasons = {
        401: "rejected the API key", 403: "rejected the API key", 402: "reports insufficient credit",
        404: "couldn't find that model", 429: "is rate limiting requests",
    }
    reason = reasons.get(response.status, f"returned HTTP {response.status}")
    raise InferenceError(f"{provider_name} {reason}. {body}".strip())


def parse_sse(lines: Iterator[str]) -> Iterator[tuple]:
    """Yield ``(event, data)`` per server-sent event; multi-line data is joined with newlines."""
    event, data = "message", []
    for raw in lines:
        line = raw.rstrip("\r\n")
        if not line:
            if data:
                yield event, "\n".join(data)
            event, data = "message", []
        elif line.startswith(":"):
            continue
        elif line.startswith("event:"):
            event = line[6:].strip()
        elif line.startswith("data:"):
            data.append(line[5:][1:] if line[5:].startswith(" ") else line[5:])
    if data:
        yield event, "\n".join(data)


class RemoteBackend:
    device = "remote"

    def __init__(self, endpoint: InferenceEndpoint, http: Optional[Http] = None):
        self.endpoint = endpoint
        self.http = http or default_http()
        for value in endpoint.headers.values():  # never echo a credential back in an error message
            register_secret(value.split(" ", 1)[-1] if value.lower().startswith("bearer ") else value)

    def count_tokens(self, text: str) -> int:
        return estimate_tokens(text)

    def close(self) -> None:  # nothing is held in memory locally
        pass

    def stream(self, messages: List[Message], params: GenerationParams, usage: Usage) -> Iterator[str]:
        usage.prompt_tokens = estimate_tokens("\n".join(m["content"] for m in messages))
        if self.endpoint.kind == "replicate":
            yield from self._stream_replicate(messages, params, usage)
        else:
            yield from self._stream_openai(messages, params, usage)

    # -- OpenAI-compatible --------------------------------------------------------

    def _stream_openai(self, messages: List[Message], params: GenerationParams, usage: Usage) -> Iterator[str]:
        body: Dict[str, Any] = {
            "model": self.endpoint.model, "messages": messages, "stream": True,
            "stream_options": {"include_usage": True}, "max_tokens": params.max_tokens,
            "temperature": params.temperature, "top_p": params.top_p,
        }
        if params.top_k:
            body["top_k"] = params.top_k
        if params.repetition_penalty and params.repetition_penalty != 1.0:
            body["repetition_penalty"] = params.repetition_penalty
        if params.stop:
            body["stop"] = params.stop

        url = f"{self.endpoint.base_url.rstrip('/')}/chat/completions"
        completion, finish = "", "stop"
        try:
            with self.http.stream("POST", url, headers=self.endpoint.headers, json=body) as response:
                _check_status(response, "The provider")
                for _, data in parse_sse(response.iter_lines()):
                    if data.strip() == "[DONE]":
                        break
                    try:
                        chunk = json.loads(data)
                    except ValueError:
                        continue
                    if chunk.get("error"):
                        raise InferenceError(f"The provider reported an error: {redact(str(chunk['error'])[:300])}")
                    if chunk.get("usage"):
                        usage.prompt_tokens = chunk["usage"].get("prompt_tokens", usage.prompt_tokens)
                        usage.completion_tokens = chunk["usage"].get("completion_tokens", usage.completion_tokens)
                    for choice in chunk.get("choices") or []:
                        delta = (choice.get("delta") or {}).get("content")
                        if delta:
                            completion += delta
                            yield delta
                        if choice.get("finish_reason"):
                            finish = choice["finish_reason"]
        except InferenceError:
            raise
        except Exception as exc:  # noqa: BLE001 - typed network errors from the HTTP layer
            raise InferenceError(f"Remote request failed: {redact(str(exc))}") from exc
        if not usage.completion_tokens:
            usage.completion_tokens = estimate_tokens(completion)
        usage.finish_reason = finish

    # -- Replicate ------------------------------------------------------------------

    @staticmethod
    def _replicate_input(messages: List[Message], params: GenerationParams) -> Dict[str, Any]:
        system = "\n".join(m["content"] for m in messages if m["role"] == "system")
        names = {"user": "User", "assistant": "Assistant"}
        turns = [f"{names.get(m['role'], m['role'])}: {m['content']}" for m in messages if m["role"] != "system"]
        body: Dict[str, Any] = {
            "prompt": "\n".join(turns + ["Assistant:"]), "max_tokens": params.max_tokens,
            "temperature": params.temperature, "top_p": params.top_p, "top_k": params.top_k,
            "repetition_penalty": params.repetition_penalty,
        }
        if system:
            body["system_prompt"] = system
        if params.stop:
            body["stop_sequences"] = ",".join(params.stop)
        return body

    def _stream_replicate(self, messages: List[Message], params: GenerationParams, usage: Usage) -> Iterator[str]:
        base = self.endpoint.base_url.rstrip("/")
        completion, finished, cancel_url = "", False, None
        try:
            created = self.http.request(
                "POST", f"{base}/models/{self.endpoint.model}/predictions", headers=self.endpoint.headers, timeout=60.0,
                json={"input": self._replicate_input(messages, params), "stream": True},
            )
            if created.status >= 400:
                reasons = {401: "rejected the API token", 404: "couldn't find that model", 402: "reports insufficient credit"}
                raise InferenceError(f"Replicate {reasons.get(created.status, f'returned HTTP {created.status}')}. {redact(created.text[:200])}")
            urls = created.json().get("urls", {})
            cancel_url, stream_url = urls.get("cancel"), urls.get("stream")
            if not stream_url:
                raise InferenceError("This Replicate model doesn't support streaming.")

            with self.http.stream("GET", stream_url, headers={**self.endpoint.headers, "Accept": "text/event-stream"}) as response:
                _check_status(response, "Replicate")
                for event, data in parse_sse(response.iter_lines()):
                    if event == "output":
                        completion += data
                        yield data
                    elif event == "error":
                        raise InferenceError(f"Replicate reported an error: {redact(data[:300])}")
                    elif event == "done":
                        finished = True
                        break
            usage.finish_reason = "stop"
        except InferenceError:
            raise
        except Exception as exc:  # noqa: BLE001
            raise InferenceError(f"Remote request failed: {redact(str(exc))}") from exc
        finally:
            if not finished and cancel_url:  # client stopped early: don't keep paying for the prediction
                try:
                    self.http.request("POST", cancel_url, headers=self.endpoint.headers, timeout=15.0)
                except Exception:  # noqa: BLE001
                    pass
        usage.completion_tokens = estimate_tokens(completion)
