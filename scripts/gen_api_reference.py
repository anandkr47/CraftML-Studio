"""
Generate docs/API_REFERENCE.md from the backend's real OpenAPI schema, so the reference can't drift.

    CRAFTML_ENV=prod CRAFTML_USER_DATA_DIR=$(mktemp -d) python scripts/gen_api_reference.py
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT), str(ROOT / "apps" / "backend")]

import main  # noqa: E402

schema = main.app.openapi()
groups = {}
for path, ops in schema["paths"].items():
    for method, op in ops.items():
        tag = (op.get("tags") or ["Other"])[0]
        summary = (op.get("description") or op.get("summary") or "").strip().splitlines()
        groups.setdefault(tag, []).append((path, method.upper(), summary[0] if summary else ""))

lines = [
    "# API reference",
    "",
    "Generated from the backend's OpenAPI schema by `scripts/gen_api_reference.py`; do not edit by hand.",
    "The interactive version is served at `http://127.0.0.1:17860/docs` while the app runs.",
    "",
    "* Base URL: `http://127.0.0.1:17860` (loopback only).",
    "* Browser callers must send an allowed `Origin` (the desktop app's); other web pages are rejected.",
    "* Errors: `{\"status\": \"error\", \"message\": <readable text>, \"detail\": ..., \"code\": ...}`.",
    "* `/v1/*` is OpenAI-compatible (chat completions with SSE streaming, embeddings, models).",
    "",
]
for tag in sorted(groups):
    lines += [f"## {tag}", "", "| Method | Path | Description |", "|---|---|---|"]
    for path, method, summary in sorted(groups[tag], key=lambda r: (r[0], r[1])):
        lines.append(f"| `{method}` | `{path}` | {summary.replace('|', '\\|')} |")
    lines.append("")
# WebSockets aren't part of OpenAPI
lines += ["## WebSockets", "", "| Path | Description |", "|---|---|",
          "| `/ws/monitor` | System telemetry (CPU, RAM, GPU) and memory alerts every 2 s |",
          "| `/ws/logs/{job_id}` | A job's log lines as they are written |",
          "| `/ws/metrics/{job_id}` | A job's status and progress whenever they change |", ""]
out = ROOT / "docs" / "API_REFERENCE.md"
out.write_text("\n".join(lines), encoding="utf-8")
print(f"wrote {out} ({sum(len(v) for v in groups.values())} operations)")
