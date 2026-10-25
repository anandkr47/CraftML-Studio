"""
Chat Studio API: persisted sessions, model management, and streamed replies.
"""

import logging
import re
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import PlainTextResponse, StreamingResponse
from pydantic import BaseModel, Field

from api.openai_compat import chunk_payload, sse
from services import chat_store, inference, rag
from services.inference import GenerationParams, InferenceError, Usage

logger = logging.getLogger(__name__)
router = APIRouter()

KB_TOP_K = 4

# Rough budget for conversation history sent to the model (characters, ~4 chars/token).
HISTORY_CHAR_BUDGET = 12000


class SessionParams(BaseModel):
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    top_p: float = Field(default=0.9, ge=0.0, le=1.0)
    top_k: int = Field(default=50, ge=0, le=200)
    repetition_penalty: float = Field(default=1.1, ge=0.5, le=2.0)
    max_tokens: int = Field(default=512, ge=1, le=8192)


class SessionCreate(BaseModel):
    title: Optional[str] = None
    model_id: Optional[str] = None
    system_prompt: Optional[str] = None
    params: Optional[SessionParams] = None
    use_kb: Optional[bool] = None


class SessionUpdate(SessionCreate):
    pass


class SendMessage(BaseModel):
    content: str = Field(..., min_length=1)
    # Optional overrides; persisted on the session when provided.
    model_id: Optional[str] = None
    system_prompt: Optional[str] = None
    params: Optional[SessionParams] = None
    use_kb: Optional[bool] = None


def _dump(model: BaseModel) -> Dict[str, Any]:
    return model.model_dump(exclude_none=True)


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

@router.get("/models")
def list_models():
    loaded = set(inference.loaded_ids())
    return {
        "models": [
            {**m.__dict__, "is_loaded": m.id in loaded} for m in inference.discover_models()
        ]
    }


@router.post("/models/{model_id:path}/load")
def load_model(model_id: str):
    try:
        backend = inference.load_model(model_id)
    except InferenceError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"model_id": model_id, "device": backend.device, "loaded": True}


@router.post("/models/{model_id:path}/unload")
def unload_model(model_id: str):
    if not inference.unload_model(model_id):
        raise HTTPException(status_code=404, detail=f"Model {model_id} is not loaded")
    return {"model_id": model_id, "loaded": False}


# ---------------------------------------------------------------------------
# Sessions
# ---------------------------------------------------------------------------

@router.get("/sessions")
def list_sessions():
    return {"sessions": chat_store.list_sessions()}


@router.post("/sessions")
def create_session(body: SessionCreate):
    return chat_store.create_session(**_dump(body))


@router.get("/sessions/{session_id}")
def get_session(session_id: str):
    session = chat_store.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session


@router.patch("/sessions/{session_id}")
def update_session(session_id: str, body: SessionUpdate):
    session = chat_store.update_session(session_id, **_dump(body))
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session


@router.delete("/sessions/{session_id}")
def delete_session(session_id: str):
    if not chat_store.delete_session(session_id):
        raise HTTPException(status_code=404, detail="Session not found")
    return {"deleted": True, "id": session_id}


@router.get("/sessions/{session_id}/export")
def export_session(session_id: str, format: str = "json"):
    if format not in ("json", "markdown"):
        raise HTTPException(status_code=400, detail="format must be 'json' or 'markdown'")
    body = chat_store.export_session(session_id, format)
    if body is None:
        raise HTTPException(status_code=404, detail="Session not found")
    ext = "md" if format == "markdown" else "json"
    media = "text/markdown" if format == "markdown" else "application/json"
    return PlainTextResponse(
        body,
        media_type=media,
        headers={"Content-Disposition": f'attachment; filename="chat-{session_id[:8]}.{ext}"'},
    )


def _downloads_dir() -> Path:
    """The user's Downloads folder on macOS/Windows/Linux (XDG), falling back to home."""
    import os

    xdg = os.environ.get("XDG_DOWNLOAD_DIR")
    candidates = [Path(xdg)] if xdg else []
    candidates.append(Path.home() / "Downloads")
    return next((c for c in candidates if c.is_dir()), Path.home())


@router.post("/sessions/{session_id}/export/save")
def save_export(session_id: str, format: str = "markdown"):
    """Write the export to the Downloads folder (never overwriting) and return the path."""
    if format not in ("json", "markdown"):
        raise HTTPException(status_code=400, detail="format must be 'json' or 'markdown'")
    body = chat_store.export_session(session_id, format)
    if body is None:
        raise HTTPException(status_code=404, detail="Session not found")
    session = chat_store.get_session(session_id) or {}
    stem = re.sub(r"[^\w-]+", "_", session.get("title") or "chat").strip("_")[:60] or "chat"
    ext = "md" if format == "markdown" else "json"
    target = _downloads_dir() / f"{stem}.{ext}"
    counter = 1
    while target.exists():
        target = target.with_name(f"{stem} ({counter}).{ext}")
        counter += 1
    target.write_text(body, encoding="utf-8")
    return {"path": str(target)}


# ---------------------------------------------------------------------------
# Streaming reply
# ---------------------------------------------------------------------------

def build_prompt(system_prompt: str, history: List[Dict[str, Any]]) -> List[Dict[str, str]]:
    """System prompt plus as much recent history as fits the budget (always >= last message)."""
    kept: List[Dict[str, str]] = []
    used = 0
    for m in reversed(history):
        used += len(m["content"])
        if kept and used > HISTORY_CHAR_BUDGET:
            break
        kept.append({"role": m["role"], "content": m["content"]})
    kept.reverse()
    return ([{"role": "system", "content": system_prompt}] if system_prompt.strip() else []) + kept


@router.post("/sessions/{session_id}/messages/stream")
def send_message(session_id: str, body: SendMessage):
    """
    Persist the user message, stream the assistant reply as SSE, then persist it.

    Events are OpenAI-style ``chat.completion.chunk`` objects, followed by one
    ``craftml.done`` event carrying the saved message id, sources and usage.
    With ``use_kb`` the top matching knowledge-base chunks ground the reply and
    are returned (and saved) as ``sources``.
    """
    overrides = _dump(body)
    overrides.pop("content")
    if overrides:
        chat_store.update_session(session_id, **overrides)

    session = chat_store.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    model_id = session["model_id"]
    if not model_id:
        raise HTTPException(status_code=400, detail="Select a model first")
    try:
        inference.resolve_model(model_id)
    except InferenceError as exc:
        raise HTTPException(status_code=404, detail=str(exc))

    sources: List[Dict[str, Any]] = []
    if session["use_kb"]:
        try:
            sources = rag.search(body.content, KB_TOP_K)
        except Exception as exc:  # noqa: BLE001 - e.g. embedding model unavailable
            raise HTTPException(status_code=500, detail=f"Knowledge base search failed: {exc}")

    chat_store.add_message(session_id, "user", body.content)
    history = session["messages"] + [{"role": "user", "content": body.content}]
    system_prompt = rag.build_context_prompt(session["system_prompt"], sources)
    messages = build_prompt(system_prompt, history)
    params = GenerationParams(**session["params"])

    def events() -> Iterator[str]:
        usage = Usage()
        reply = ""
        saved = None
        try:
            for delta in inference.stream_chat(model_id, messages, params, usage):
                reply += delta
                yield sse(chunk_payload(session_id, model_id, 0, {"content": delta}))
            saved = chat_store.add_message(session_id, "assistant", reply, sources)
            yield sse({
                "object": "craftml.done",
                "message_id": saved["id"],
                "sources": sources,
                "finish_reason": usage.finish_reason,
                "usage": {"prompt_tokens": usage.prompt_tokens, "completion_tokens": usage.completion_tokens},
            })
        except InferenceError as exc:
            yield sse({"object": "craftml.error", "message": str(exc)})
        except Exception as exc:  # noqa: BLE001 - e.g. out of memory mid-generation; tell the client
            logger.exception("Generation failed for session %s", session_id)
            yield sse({"object": "craftml.error", "message": f"Generation failed: {exc}"})
        finally:
            if saved is None and reply.strip():  # client stopped early or an error mid-stream
                chat_store.add_message(session_id, "assistant", reply, sources)
        yield "data: [DONE]\n\n"

    return StreamingResponse(
        events(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}
    )
