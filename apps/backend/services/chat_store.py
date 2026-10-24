"""Chat session persistence (SQLite) and export."""

import json
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from db.models import ChatMessage, ChatSession, SessionLocal

DEFAULT_PARAMS = {
    "temperature": 0.7,
    "top_p": 0.9,
    "top_k": 50,
    "repetition_penalty": 1.1,
    "max_tokens": 512,
}
SESSION_FIELDS = ("title", "model_id", "system_prompt", "params", "use_kb")


def _loads(value: Optional[str]) -> Any:
    try:
        return json.loads(value) if value else None
    except ValueError:
        return None


def _iso(value: Optional[datetime]) -> Optional[str]:
    return value.isoformat() if value else None


def _session_dict(row: ChatSession) -> Dict[str, Any]:
    return {
        "id": row.id,
        "title": row.title,
        "model_id": row.model_id,
        "system_prompt": row.system_prompt or "",
        "params": {**DEFAULT_PARAMS, **(_loads(row.params) or {})},
        "use_kb": bool(row.use_kb),
        "created_at": _iso(row.created_at),
        "updated_at": _iso(row.updated_at),
    }


def _message_dict(row: ChatMessage) -> Dict[str, Any]:
    return {
        "id": row.id,
        "role": row.role,
        "content": row.content,
        "sources": _loads(row.sources) or [],
        "created_at": _iso(row.created_at),
    }


def create_session(**fields: Any) -> Dict[str, Any]:
    with SessionLocal() as db:
        row = ChatSession(id=uuid.uuid4().hex, title=fields.get("title") or "New chat")
        _apply(row, fields)
        db.add(row)
        db.commit()
        return _session_dict(row)


def _apply(row: ChatSession, fields: Dict[str, Any]) -> None:
    for key in SESSION_FIELDS:
        if key in fields and fields[key] is not None:
            value = fields[key]
            setattr(row, key, json.dumps(value) if key == "params" else value)


def update_session(session_id: str, **fields: Any) -> Optional[Dict[str, Any]]:
    with SessionLocal() as db:
        row = db.get(ChatSession, session_id)
        if not row:
            return None
        _apply(row, fields)
        row.updated_at = datetime.utcnow()
        db.commit()
        return _session_dict(row)


def list_sessions() -> List[Dict[str, Any]]:
    with SessionLocal() as db:
        rows = db.query(ChatSession).order_by(ChatSession.updated_at.desc()).all()
        return [_session_dict(r) for r in rows]


def get_session(session_id: str) -> Optional[Dict[str, Any]]:
    """Session with its messages, or None."""
    with SessionLocal() as db:
        row = db.get(ChatSession, session_id)
        if not row:
            return None
        messages = (
            db.query(ChatMessage).filter(ChatMessage.session_id == session_id).order_by(ChatMessage.id).all()
        )
        return {**_session_dict(row), "messages": [_message_dict(m) for m in messages]}


def delete_session(session_id: str) -> bool:
    with SessionLocal() as db:
        row = db.get(ChatSession, session_id)
        if not row:
            return False
        db.query(ChatMessage).filter(ChatMessage.session_id == session_id).delete()
        db.delete(row)
        db.commit()
        return True


def add_message(
    session_id: str, role: str, content: str, sources: Optional[List[Dict[str, Any]]] = None
) -> Dict[str, Any]:
    with SessionLocal() as db:
        msg = ChatMessage(
            session_id=session_id,
            role=role,
            content=content,
            sources=json.dumps(sources) if sources else None,
        )
        db.add(msg)
        session = db.get(ChatSession, session_id)
        if session:
            session.updated_at = datetime.utcnow()
            if role == "user" and session.title == "New chat":
                session.title = content.strip().replace("\n", " ")[:60] or "New chat"
        db.commit()
        return _message_dict(msg)


def export_session(session_id: str, fmt: str = "json") -> Optional[str]:
    data = get_session(session_id)
    if not data:
        return None
    if fmt == "markdown":
        lines = [f"# {data['title']}", ""]
        if data["system_prompt"]:
            lines += [f"> **System:** {data['system_prompt']}", ""]
        for m in data["messages"]:
            lines += [f"### {m['role'].capitalize()}", "", m["content"], ""]
            for s in m["sources"]:
                lines.append(f"- source: {s.get('document', '?')} (chunk {s.get('chunk_index', '?')})")
            if m["sources"]:
                lines.append("")
        return "\n".join(lines)
    return json.dumps(data, indent=2)
