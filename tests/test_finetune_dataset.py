"""Tests for fine-tuning dataset loading/inspection and the /api/dataset routes."""

import json
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
os.environ["CRAFTML_ENV"] = "prod"
os.environ["CRAFTML_USER_DATA_DIR"] = tempfile.mkdtemp(prefix="craftml-test-")
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "apps" / "backend"))

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api import dataset as dataset_api
from core.data.finetune_dataset import (
    DatasetFormatError,
    detect_format,
    inspect_dataset,
    load_raw,
    render_conversation,
    to_text_dataset,
)

ROWS = [{"instruction": f"Q{i}", "output": f"A{i}"} for i in range(12)]


def write_jsonl(path, rows):
    path.write_text("\n".join(json.dumps(r) for r in rows))
    return str(path)


def test_detect_format():
    assert detect_format(["instruction", "output"]) == "instruction"
    assert detect_format(["question", "answer"]) == "instruction"
    assert detect_format(["prompt", "completion"]) == "prompt_completion"
    assert detect_format(["messages"]) == "chat"
    assert detect_format(["text"]) == "text"
    assert detect_format(["foo", "bar"]) is None


def test_instruction_rows_render_as_user_assistant_turns(tmp_path):
    ds = to_text_dataset(load_raw(write_jsonl(tmp_path / "d.jsonl", ROWS)))
    assert ds["text"][0] == "User: Q0\nAssistant: A0"


def test_optional_input_column_is_appended_to_the_user_turn(tmp_path):
    rows = [{"instruction": "Translate", "input": "hello", "output": "hola"}]
    text = to_text_dataset(load_raw(write_jsonl(tmp_path / "d.jsonl", rows)))["text"][0]
    assert "Translate\n\nhello" in text and text.endswith("Assistant: hola")


def test_chat_template_is_used_when_the_tokenizer_has_one():
    class Tok:
        chat_template = "x"

        def apply_chat_template(self, messages, tokenize=False):
            return "|".join(f"{m['role']}:{m['content']}" for m in messages)

    assert render_conversation([{"role": "user", "content": "hi"}, {"role": "assistant", "content": "yo"}], Tok()) == "user:hi|assistant:yo"


def test_csv_parquet_and_txt_are_supported(tmp_path):
    import pandas as pd

    df = pd.DataFrame({"prompt": ["p1", "p2"], "completion": ["c1", "c2"]})
    df.to_csv(tmp_path / "d.csv", index=False)
    df.to_parquet(tmp_path / "d.parquet")
    (tmp_path / "d.txt").write_text("first paragraph\n\nsecond paragraph")

    assert len(to_text_dataset(load_raw(str(tmp_path / "d.csv")))) == 2
    assert to_text_dataset(load_raw(str(tmp_path / "d.parquet")))["text"][1] == "User: p2\nAssistant: c2"
    assert to_text_dataset(load_raw(str(tmp_path / "d.txt")))["text"] == ["first paragraph", "second paragraph"]


def test_chat_messages_format(tmp_path):
    rows = [{"messages": [{"role": "user", "content": "hi"}, {"role": "assistant", "content": "hello"}]}]
    assert to_text_dataset(load_raw(write_jsonl(tmp_path / "c.jsonl", rows)))["text"][0] == "User: hi\nAssistant: hello"


def test_unusable_files_raise_clear_errors(tmp_path):
    with pytest.raises(DatasetFormatError, match="Unsupported"):
        load_raw(str(tmp_path / "x.xlsx"))
    with pytest.raises(DatasetFormatError, match="Couldn't find training columns"):
        to_text_dataset(load_raw(write_jsonl(tmp_path / "bad.jsonl", [{"foo": 1}])))


def test_inspect_reports_preview_and_problems(tmp_path):
    good = inspect_dataset(write_jsonl(tmp_path / "g.jsonl", ROWS))
    assert good["valid"] and good["num_samples"] == 12 and len(good["preview"]) == 3 and not good["problems"]

    tiny = inspect_dataset(write_jsonl(tmp_path / "t.jsonl", ROWS[:2]))
    assert tiny["valid"] and "Very small" in tiny["problems"][0]

    bad = inspect_dataset(write_jsonl(tmp_path / "b.jsonl", [{"foo": 1}]))
    assert not bad["valid"] and bad["format"] is None


@pytest.fixture()
def client():
    app = FastAPI()
    app.include_router(dataset_api.router, prefix="/api/dataset")
    return TestClient(app)


def test_upload_list_info_delete(client):
    body = "\n".join(json.dumps(r) for r in ROWS).encode()
    up = client.post("/api/dataset/upload", files={"file": ("my data.jsonl", body, "application/json")})
    assert up.status_code == 200
    info = up.json()
    assert info["valid"] and info["num_samples"] == 12 and info["name"] == "my_data.jsonl"

    assert [d["id"] for d in client.get("/api/dataset/list").json()["datasets"]] == [info["id"]]
    assert client.get(f"/api/dataset/{info['id']}/info").json()["format"] == "instruction"
    assert client.delete(f"/api/dataset/{info['id']}").json()["deleted"]
    assert client.get("/api/dataset/list").json()["total"] == 0


def test_upload_rejects_bad_types_and_unreadable_files(client):
    assert client.post("/api/dataset/upload", files={"file": ("x.exe", b"x", "x/y")}).status_code == 400
    broken = client.post("/api/dataset/upload", files={"file": ("x.parquet", b"not parquet", "x/y")})
    assert broken.status_code == 400
    assert client.get("/api/dataset/list").json()["total"] == 0  # failed uploads are cleaned up


def test_dataset_ids_cannot_escape_the_datasets_directory(client):
    assert client.get("/api/dataset/..%2F..%2Fetc%2Fpasswd/info").status_code == 404
