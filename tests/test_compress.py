"""
Tests for compression presets, GGUF tooling discovery, the benchmark report maths
and the compression job flow (quantization, GGUF conversion and benchmarking are mocked).
"""

import os
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
os.environ["CRAFTML_ENV"] = "prod"
os.environ["CRAFTML_USER_DATA_DIR"] = tempfile.mkdtemp(prefix="craftml-test-")
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "apps" / "backend"))

import pytest

from core.config import settings
from core.ml.compression import presets
from core.ml.compression import gguf
from db.models import Base, engine, init_db
from services import benchmark, compression_service, inference, jobs
from services.inference import ModelInfo


# --- presets ---------------------------------------------------------------

def test_every_preset_uses_a_valid_method():
    for preset in presets.PRESETS:
        presets.validate_choice(preset["method"], preset["quantization"])


def test_validate_choice_rejects_unknown_values():
    with pytest.raises(ValueError, match="Unknown compression method"):
        presets.validate_choice("onnx", None)
    with pytest.raises(ValueError, match="Unknown GGUF quantization"):
        presets.validate_choice("gguf", "Q9_X")


def test_size_estimates_scale_with_bits():
    assert presets.estimate_size_mb(1600, "int8") == 800.0
    assert presets.estimate_size_mb(1600, "gguf", "Q4_K_M") < presets.estimate_size_mb(1600, "gguf", "Q8_0")
    assert presets.output_suffix("gguf", "Q4_K_M") == "q4_k_m" and presets.output_suffix("awq") == "awq"


def test_recommended_preset_follows_hardware():
    assert presets.recommended_preset("cuda", 8) == "fit_8gb"
    assert presets.recommended_preset("cuda", 24) == "quality"
    assert presets.recommended_preset("mps", 16) == "apple_cpu"
    assert presets.recommended_preset("cpu", 0) == "apple_cpu"


# --- benchmark report ------------------------------------------------------

def test_build_report_derives_comparison_numbers():
    report = benchmark.build_report(
        {"size_mb": 1000, "perplexity": 10.0, "tokens_per_second": 5.0},
        {"size_mb": 250, "perplexity": 10.5, "tokens_per_second": 15.0},
    )
    assert report["size_reduction_percent"] == 75.0
    assert report["compression_ratio"] == 4.0
    assert report["speedup"] == 3.0
    assert report["perplexity_increase_percent"] == 5.0


def test_build_report_tolerates_missing_benchmarks():
    report = benchmark.build_report({"size_mb": 100}, {"size_mb": 50})
    assert report["speedup"] is None and "perplexity_increase_percent" not in report


# --- gguf tooling ----------------------------------------------------------

def test_tooling_not_ready_without_llama_cpp(monkeypatch, tmp_path):
    monkeypatch.delenv("LLAMA_CPP_DIR", raising=False)
    monkeypatch.setattr(gguf, "_tools_dir", lambda: tmp_path / "missing")
    assert gguf.llama_cpp_dir() is None and gguf.tooling_status()["ready"] is False
    with pytest.raises(gguf.GgufError, match="not set up"):
        gguf.convert_to_gguf("/m", str(tmp_path / "out.gguf"))


def test_llama_cpp_dir_is_found_via_env(monkeypatch, tmp_path):
    (tmp_path / gguf.CONVERT_SCRIPT).write_text("")
    monkeypatch.setenv("LLAMA_CPP_DIR", str(tmp_path))
    assert gguf.llama_cpp_dir() == tmp_path and gguf.tooling_status()["ready"] is True


def test_q8_converts_directly_and_q4_goes_through_quantize(monkeypatch, tmp_path):
    (tmp_path / gguf.CONVERT_SCRIPT).write_text("")
    monkeypatch.setenv("LLAMA_CPP_DIR", str(tmp_path))
    commands = []

    def fake_run(cmd, log):
        commands.append(cmd)
        Path(cmd[cmd.index("--outfile") + 1] if "--outfile" in cmd else cmd[2]).write_bytes(b"x" * 2048)

    monkeypatch.setattr(gguf, "_run", fake_run)
    monkeypatch.setattr(gguf, "_quantize_binary", lambda d: "/bin/llama-quantize")

    gguf.convert_to_gguf("/model", str(tmp_path / "q8.gguf"), "Q8_0")
    assert len(commands) == 1 and commands[0][-1] == "q8_0"

    commands.clear()
    result = gguf.convert_to_gguf("/model", str(tmp_path / "q4.gguf"), "Q4_K_M")
    assert [c[0] == "/bin/llama-quantize" for c in commands] == [False, True]
    assert result["compression_type"] == "gguf_q4_k_m"
    assert not (tmp_path / "q4.f16.gguf").exists()  # intermediate is cleaned up


# --- compression job -------------------------------------------------------

@pytest.fixture()
def env(monkeypatch):
    Base.metadata.drop_all(bind=engine)
    init_db()
    model_dir = Path(settings.models_dir) / "train_abc12345" / "final"
    model_dir.mkdir(parents=True, exist_ok=True)
    (model_dir / "config.json").write_text("{}")
    (model_dir / "model.safetensors").write_bytes(b"x" * (2 * 1024 * 1024))
    info = ModelInfo(id="train_abc12345", name="train_abc12345", path=str(model_dir), kind="full", size_mb=2.0)
    monkeypatch.setattr(inference, "resolve_model", lambda m: info if m == info.id else (_ for _ in ()).throw(
        inference.InferenceError("not found")))
    yield info
    import shutil
    shutil.rmtree(Path(settings.models_dir) / "train_abc12345", ignore_errors=True)
    shutil.rmtree(Path(settings.models_dir) / "train_abc12345-q4_k_m", ignore_errors=True)
    shutil.rmtree(Path(settings.models_dir) / "train_abc12345-int4", ignore_errors=True)


def wait(job_id):
    for _ in range(200):
        if jobs.get(job_id)["status"] not in ("pending", "running"):
            return jobs.get(job_id)
        time.sleep(0.05)
    raise AssertionError("job did not finish")


def test_gguf_job_produces_report_and_model(env, monkeypatch):
    def fake_convert(model_dir, output_file, quantization, log=None):
        Path(output_file).parent.mkdir(parents=True, exist_ok=True)
        Path(output_file).write_bytes(b"x" * (512 * 1024))
        return {}

    monkeypatch.setattr(compression_service, "convert_to_gguf", fake_convert)
    monkeypatch.setattr(compression_service, "benchmark_model", lambda path, kind: {
        "perplexity": 9.0 if kind == "gguf" else 8.0, "tokens_per_second": 20.0 if kind == "gguf" else 5.0,
        "load_seconds": 1.0, "memory_mb": 100.0})

    job = wait(compression_service.start_compression({"model_id": env.id, "method": "gguf", "quantization": "Q4_K_M"}))
    assert job["status"] == "completed", job["error"]
    result = job["result"]
    assert result["output_id"] == "train_abc12345-q4_k_m"
    assert result["before"]["size_mb"] == 2.0 and result["after"]["size_mb"] == 0.5
    assert result["size_reduction_percent"] == 75.0 and result["speedup"] == 4.0
    assert Path(result["output_path"]).exists()
    assert not list(Path(settings.models_dir).glob(".tmp-*"))


def test_failed_job_leaves_no_partial_output(env, monkeypatch):
    def boom(model_dir, output_dir, method):
        Path(output_dir, "partial.bin").write_bytes(b"x")
        raise RuntimeError("CUDA required")

    monkeypatch.setattr(compression_service, "quantize_model", boom)
    job = wait(compression_service.start_compression({"model_id": env.id, "method": "int4", "benchmark": False}))
    assert job["status"] == "failed" and "CUDA required" in job["error"]
    assert not (Path(settings.models_dir) / "train_abc12345-int4").exists()


def test_benchmark_failure_does_not_fail_the_job(env, monkeypatch):
    monkeypatch.setattr(compression_service, "convert_to_gguf",
                        lambda d, o, q, log=None: Path(o).parent.mkdir(parents=True, exist_ok=True) or Path(o).write_bytes(b"x"))
    monkeypatch.setattr(compression_service, "benchmark_model", lambda p, k: (_ for _ in ()).throw(RuntimeError("OOM")))
    job = wait(compression_service.start_compression({"model_id": env.id, "method": "gguf"}))
    assert job["status"] == "completed"
    assert any("Benchmark skipped" in line for line in jobs.get_logs(job["job_id"])["logs"])


def test_start_validation(env):
    with pytest.raises(ValueError, match="model_id"):
        compression_service.start_compression({"method": "gguf"})
    with pytest.raises(ValueError, match="Unknown compression method"):
        compression_service.start_compression({"model_id": env.id, "method": "prune"})
    with pytest.raises(inference.InferenceError):
        compression_service.start_compression({"model_id": "missing", "method": "gguf"})
