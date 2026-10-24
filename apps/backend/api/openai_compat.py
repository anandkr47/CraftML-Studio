"""
OpenAI-compatible API: /v1/models, /v1/chat/completions, /v1/embeddings.

``create_router`` is a factory so the same routes can be mounted in the main
app (no auth) and in the dedicated Deploy server (optional API key).
"""

import json
import time
import uuid
from typing import Any, Iterator, List, Optional, Union

from fastapi import APIRouter, Depends, Header, HTTPException
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, ConfigDict, Field

from services import embeddings, inference
from services.inference import GenerationParams, InferenceError, Usage


class ChatMessage(BaseModel):
    role: str
    content: Union[str, List[dict], None] = ""

    def text(self) -> str:
        if isinstance(self.content, list):  # content parts: keep text parts only
            return "".join(p.get("text", "") for p in self.content if p.get("type") == "text")
        return self.content or ""


class ChatCompletionRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    model: str
    messages: List[ChatMessage]
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    top_p: float = Field(default=0.9, ge=0.0, le=1.0)
    top_k: int = Field(default=50, ge=0)  # extension
    repetition_penalty: float = Field(default=1.1, ge=0.5, le=2.0)  # extension
    max_tokens: Optional[int] = Field(default=None, ge=1)
    max_completion_tokens: Optional[int] = Field(default=None, ge=1)
    stream: bool = False
    stop: Union[str, List[str], None] = None

    def to_params(self) -> GenerationParams:
        stop = [self.stop] if isinstance(self.stop, str) else list(self.stop or [])
        return GenerationParams(
            max_tokens=self.max_tokens or self.max_completion_tokens or 512,
            temperature=self.temperature,
            top_p=self.top_p,
            top_k=self.top_k,
            repetition_penalty=self.repetition_penalty,
            stop=stop,
        )

    def to_messages(self) -> List[dict]:
        return [{"role": m.role, "content": m.text()} for m in self.messages]


class EmbeddingRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    model: str = embeddings.DEFAULT_EMBEDDING_MODEL
    input: Union[str, List[str]]


def error_response(message: str, status: int, code: str) -> JSONResponse:
    return JSONResponse(
        {"error": {"message": message, "type": "invalid_request_error", "code": code}},
        status_code=status,
    )


def sse(payload: Any) -> str:
    return f"data: {json.dumps(payload)}\n\n"


def chunk_payload(completion_id: str, model: str, created: int, delta: dict, finish: Optional[str] = None) -> dict:
    return {
        "id": completion_id,
        "object": "chat.completion.chunk",
        "created": created,
        "model": model,
        "choices": [{"index": 0, "delta": delta, "finish_reason": finish}],
    }


def stream_completion(
    model: str, messages: List[dict], params: GenerationParams, completion_id: str, created: int
) -> Iterator[str]:
    usage = Usage()
    yield sse(chunk_payload(completion_id, model, created, {"role": "assistant", "content": ""}))
    try:
        for delta in inference.stream_chat(model, messages, params, usage):
            yield sse(chunk_payload(completion_id, model, created, {"content": delta}))
    except InferenceError as exc:
        yield sse({"error": {"message": str(exc), "type": "server_error"}})
        yield "data: [DONE]\n\n"
        return
    yield sse(chunk_payload(completion_id, model, created, {}, usage.finish_reason))
    yield "data: [DONE]\n\n"


def create_router(api_key: Optional[str] = None) -> APIRouter:
    def check_key(authorization: Optional[str] = Header(default=None)) -> None:
        if api_key and authorization != f"Bearer {api_key}":
            raise HTTPException(status_code=401, detail="Invalid API key")

    router = APIRouter(dependencies=[Depends(check_key)])

    @router.get("/models")
    def list_models():
        loaded = set(inference.loaded_ids())
        now = int(time.time())
        return {
            "object": "list",
            "data": [
                {
                    "id": m.id,
                    "object": "model",
                    "created": now,
                    "owned_by": "local",
                    "kind": m.kind,
                    "loaded": m.id in loaded,
                }
                for m in inference.discover_models()
            ],
        }

    @router.post("/chat/completions")
    def chat_completions(request: ChatCompletionRequest):
        try:
            inference.resolve_model(request.model)
        except InferenceError as exc:
            return error_response(str(exc), 404, "model_not_found")
        if not request.messages:
            return error_response("messages must not be empty", 400, "invalid_messages")

        params = request.to_params()
        messages = request.to_messages()
        completion_id = f"chatcmpl-{uuid.uuid4().hex[:24]}"
        created = int(time.time())

        if request.stream:
            return StreamingResponse(
                stream_completion(request.model, messages, params, completion_id, created),
                media_type="text/event-stream",
                headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
            )

        try:
            text, usage = inference.chat(request.model, messages, params)
        except InferenceError as exc:
            return error_response(str(exc), 500, "inference_error")

        return {
            "id": completion_id,
            "object": "chat.completion",
            "created": created,
            "model": request.model,
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": text},
                    "finish_reason": usage.finish_reason,
                }
            ],
            "usage": {
                "prompt_tokens": usage.prompt_tokens,
                "completion_tokens": usage.completion_tokens,
                "total_tokens": usage.prompt_tokens + usage.completion_tokens,
            },
        }

    @router.post("/embeddings")
    def create_embeddings(request: EmbeddingRequest):
        texts = [request.input] if isinstance(request.input, str) else request.input
        if not texts:
            return error_response("input must not be empty", 400, "invalid_input")
        try:
            vectors = embeddings.embed(texts, request.model)
        except Exception as exc:  # noqa: BLE001 - e.g. unknown embedding model
            return error_response(f"Embedding failed: {exc}", 500, "embedding_error")
        return {
            "object": "list",
            "model": request.model,
            "data": [{"object": "embedding", "index": i, "embedding": v} for i, v in enumerate(vectors)],
            "usage": {"prompt_tokens": 0, "total_tokens": 0},
        }

    return router
