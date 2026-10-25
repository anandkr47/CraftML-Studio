"""
Fine-tuning dataset loading and formatting.

Supports JSONL / JSON / CSV / Parquet / TXT files in these layouts:

  instruction        instruction (+ optional input) and output/response/answer
  prompt_completion  prompt and completion/response
  chat               messages: [{"role": ..., "content": ...}, ...]
  text               a single "text" column (raw text)

Rows are rendered to one training string per example, using the tokenizer's
chat template when it has one so the tuned model matches how Chat prompts it.
"""

from pathlib import Path
from typing import Any, Dict, List, Optional

from datasets import Dataset, load_dataset

SUPPORTED_EXTENSIONS = {".jsonl", ".json", ".csv", ".parquet", ".txt"}

INSTRUCTION_COLUMNS = ("instruction", "question")
RESPONSE_COLUMNS = ("output", "response", "answer", "completion")
PROMPT_COLUMNS = ("prompt",)


class DatasetFormatError(ValueError):
    """The file can't be used for fine-tuning (with a user-facing reason)."""


def load_raw(path: str) -> Dataset:
    file = Path(path)
    ext = file.suffix.lower()
    if ext not in SUPPORTED_EXTENSIONS:
        raise DatasetFormatError(
            f"Unsupported file type '{ext}'. Use JSONL, JSON, CSV, Parquet or TXT."
        )
    if not file.exists():
        raise DatasetFormatError(f"Dataset not found: {path}")

    try:
        if ext in (".jsonl", ".json"):
            return load_dataset("json", data_files=str(file), split="train")
        if ext == ".csv":
            return load_dataset("csv", data_files=str(file), split="train")
        if ext == ".parquet":
            return load_dataset("parquet", data_files=str(file), split="train")
        paragraphs = [p.strip() for p in file.read_text(encoding="utf-8", errors="replace").split("\n\n")]
        return Dataset.from_dict({"text": [p for p in paragraphs if p]})
    except DatasetFormatError:
        raise
    except Exception as exc:  # malformed JSON/CSV/Parquet
        raise DatasetFormatError(f"Could not read {file.name}: {exc}") from exc


def _first(columns: List[str], candidates) -> Optional[str]:
    return next((c for c in candidates if c in columns), None)


def detect_format(columns: List[str]) -> Optional[str]:
    if "messages" in columns:
        return "chat"
    if _first(columns, RESPONSE_COLUMNS):
        if _first(columns, INSTRUCTION_COLUMNS):
            return "instruction"
        if _first(columns, PROMPT_COLUMNS):
            return "prompt_completion"
    if "text" in columns:
        return "text"
    return None


def row_to_messages(row: Dict[str, Any], fmt: str) -> List[Dict[str, str]]:
    cols = list(row)
    if fmt == "chat":
        return [{"role": m["role"], "content": str(m["content"])} for m in row["messages"]]

    answer = str(row[_first(cols, RESPONSE_COLUMNS)])
    if fmt == "instruction":
        user = str(row[_first(cols, INSTRUCTION_COLUMNS)])
        extra = row.get("input")
        if extra not in (None, ""):
            user = f"{user}\n\n{extra}"
    else:
        user = str(row[_first(cols, PROMPT_COLUMNS)])
    return [{"role": "user", "content": user}, {"role": "assistant", "content": answer}]


def render_conversation(messages: List[Dict[str, str]], tokenizer=None) -> str:
    """Training text for one conversation (chat template if the tokenizer has one)."""
    if tokenizer is not None and getattr(tokenizer, "chat_template", None):
        return tokenizer.apply_chat_template(messages, tokenize=False)
    names = {"system": "System", "user": "User", "assistant": "Assistant"}
    return "\n".join(f"{names.get(m['role'], m['role'])}: {m['content']}" for m in messages)


def to_text_dataset(dataset: Dataset, tokenizer=None) -> Dataset:
    """Return a dataset with a single ``text`` column ready for tokenisation."""
    columns = dataset.column_names
    fmt = detect_format(columns)
    if fmt is None:
        raise DatasetFormatError(
            "Couldn't find training columns. Provide 'instruction' + 'output', 'prompt' + 'completion', "
            f"'messages', or 'text'. Found: {', '.join(columns) or 'none'}"
        )
    if len(dataset) == 0:
        raise DatasetFormatError("The dataset is empty")

    if fmt == "text":
        texts = [str(t) for t in list(dataset["text"]) if t not in (None, "")]
    else:
        texts = [render_conversation(row_to_messages(row, fmt), tokenizer) for row in dataset]
    return Dataset.from_dict({"text": texts})


def inspect_dataset(path: str, preview_rows: int = 3) -> Dict[str, Any]:
    """Summary for the wizard: format, columns, size, preview and any problems."""
    dataset = load_raw(path)
    columns = dataset.column_names
    fmt = detect_format(columns)

    problems: List[str] = []
    preview: List[str] = []
    if fmt is None:
        problems.append(
            "Missing training columns: use 'instruction' + 'output', 'prompt' + 'completion', 'messages' or 'text'."
        )
    elif len(dataset) == 0:
        problems.append("The dataset is empty.")
    else:
        try:
            preview = [str(t) for t in to_text_dataset(dataset.select(range(min(preview_rows, len(dataset)))))["text"]]
        except (KeyError, TypeError) as exc:
            problems.append(f"Some rows are malformed: {exc}")
        if len(dataset) < 10:
            problems.append("Very small dataset (under 10 examples); results will be poor.")

    return {
        "format": fmt,
        "columns": [str(c) for c in columns],
        "num_samples": len(dataset),
        "preview": preview,
        "problems": problems,
        "valid": fmt is not None and len(dataset) > 0 and not any("malformed" in p for p in problems),
    }
