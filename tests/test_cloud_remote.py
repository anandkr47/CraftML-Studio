"""
Remote inference: SSE parsing, the OpenAI/Replicate backend, provider endpoints, engine integration,
and an end-to-end run through an SSH-style tunnel to a real local OpenAI-compatible HTTP server.
"""

import json
import os
import socket
import sys
import tempfile
import threading
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib import request as urlrequest
from urllib.error import HTTPError

ROOT = Path(__file__).resolve().parent.parent
os.environ["CRAFTML_ENV"] = "prod"
os.environ.setdefault("CRAFTML_USER_DATA_DIR", tempfile.mkdtemp(prefix="craftml-test-"))
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "apps" / "backend"))

import pytest

from core.cloud.errors import AuthError, ConfigError, QuotaError, RemoteExecutionError, TransientError
from core.cloud.http import HttpResponse
from core.cloud.providers.base import InferenceEndpoint
from core.cloud.providers.remote_inference import ReplicateProvider, TogetherProvider, raise_for_status
from core.cloud.providers.runpod_provider import RunPodProvider
from core.cloud.schemas import ProviderId, RemoteModel
from services import inference
from services.inference import GenerationParams, InferenceError, ModelInfo, Usage
from services.inference import remote_backend
from services.inference.remote_backend import RemoteBackend, parse_sse

KEY = "sk-THISMUSTNEVERLEAK-0123456789"


# --------------------------------------------------------------------------- fakes

class FakeStream:
    def __init__(self, status, lines, text=""):
        self.status, self.headers, self._lines, self._text = status, {}, lines, text

    def iter_lines(self):
        yield from self._lines

    def read_text(self):
        return self._text or "\n".join(self._lines)


class FakeHttp:
    def __init__(self, streams=None, responses=None):
        self.streams, self.responses, self.calls = list(streams or []), list(responses or []), []

    def request(self, method, url, headers=None, json=None, timeout=30.0):
        self.calls.append(("request", method, url, headers, json))
        return self.responses.pop(0)

    @contextmanager
    def stream(self, method, url, headers=None, json=None, timeout=120.0):
        self.calls.append(("stream", method, url, headers, json))
        yield self.streams.pop(0)


def chunk(content=None, finish=None, usage=None):
    body = {"choices": [{"delta": {"content": content} if content is not None else {}, "finish_reason": finish}]}
    if usage:
        body = {"choices": [], "usage": usage}
    return "data: " + json.dumps(body)


def sse(*items):
    out = []
    for item in items:
        out += [item, ""]
    return out


ENDPOINT = InferenceEndpoint(kind="openai", base_url="https://api.example.com/v1", headers={"Authorization": f"Bearer {KEY}"}, model="llama")
MESSAGES = [{"role": "system", "content": "Be brief"}, {"role": "user", "content": "Hi"}]


def run_backend(http, endpoint=ENDPOINT, params=None):
    usage = Usage()
    text = "".join(RemoteBackend(endpoint, http).stream(MESSAGES, params or GenerationParams(max_tokens=64, stop=["END"]), usage))
    return text, usage


# --------------------------------------------------------------------------- SSE + OpenAI streaming

def test_parse_sse_handles_events_multiline_data_comments_and_crlf():
    lines = [": keepalive", "event: output", "data: hello", "data: world", "", "data: solo\r", "", "event: done", "data: {}", ""]
    assert list(parse_sse(iter(lines))) == [("output", "hello\nworld"), ("message", "solo"), ("done", "{}")]
    assert list(parse_sse(iter(["data: tail-without-blank-line"]))) == [("message", "tail-without-blank-line")]


def test_openai_stream_yields_deltas_and_reports_usage_and_finish_reason():
    http = FakeHttp(streams=[FakeStream(200, sse(chunk("Hel"), chunk("lo"), chunk(None, finish="length"),
                                                  chunk(usage={"prompt_tokens": 11, "completion_tokens": 7}), "data: [DONE]"))])
    text, usage = run_backend(http)
    assert text == "Hello" and (usage.prompt_tokens, usage.completion_tokens, usage.finish_reason) == (11, 7, "length")

    kind, method, url, headers, body = http.calls[0]
    assert url == "https://api.example.com/v1/chat/completions" and headers["Authorization"] == f"Bearer {KEY}"
    assert body["stream"] is True and body["max_tokens"] == 64 and body["stop"] == ["END"] and body["model"] == "llama"
    assert body["stream_options"] == {"include_usage": True} and body["top_k"] == 50 and body["messages"] == MESSAGES


def test_openai_stream_estimates_tokens_when_the_provider_reports_none():
    _, usage = run_backend(FakeHttp(streams=[FakeStream(200, sse(chunk("x" * 40), "data: [DONE]"))]))
    assert usage.completion_tokens == 10 and usage.prompt_tokens > 0 and usage.finish_reason == "stop"


@pytest.mark.parametrize("status,phrase", [(401, "rejected the API key"), (404, "couldn't find that model"),
                                           (429, "rate limiting"), (402, "insufficient credit"), (500, "HTTP 500")])
def test_http_errors_become_inference_errors_without_leaking_the_key(status, phrase):
    http = FakeHttp(streams=[FakeStream(status, [], text=f"denied for {KEY} bearer abcdefghijklmnopqrstuvwxyz")])
    with pytest.raises(InferenceError) as err:
        run_backend(http)
    assert phrase in str(err.value) and KEY not in str(err.value)


def test_a_mid_stream_error_chunk_is_surfaced():
    http = FakeHttp(streams=[FakeStream(200, sse(chunk("Hi"), 'data: {"error": {"message": "overloaded"}}'))])
    with pytest.raises(InferenceError, match="overloaded"):
        run_backend(http)


def test_malformed_chunks_are_skipped_and_network_errors_are_wrapped():
    http = FakeHttp(streams=[FakeStream(200, sse("data: {not json", chunk("ok"), "data: [DONE]"))])
    assert run_backend(http)[0] == "ok"

    class Down(FakeHttp):
        def stream(self, *a, **k):
            raise TransientError("Network error talking to api.example.com (ConnectError).")

    with pytest.raises(InferenceError, match="Remote request failed"):
        run_backend(Down())


# --------------------------------------------------------------------------- Replicate

REPLICATE = InferenceEndpoint(kind="replicate", base_url="https://api.replicate.com/v1", headers={"Authorization": f"Bearer {KEY}"}, model="meta/llama")


def replicate_http(events, status=200):
    created = HttpResponse(201, json.dumps({"urls": {"stream": "https://stream.example/s", "cancel": "https://api.replicate.com/v1/c"}}), {})
    return FakeHttp(streams=[FakeStream(status, sse(*events))], responses=[created, HttpResponse(200, "{}", {})])


def test_replicate_streams_output_events_and_maps_inputs():
    http = replicate_http(["event: output\ndata: Hello", "event: output\ndata:  world", "event: done\ndata: {}"])
    # the SSE helper splits on lines, so build real multi-line event text
    http.streams[0] = FakeStream(200, ["event: output", "data: Hello", "", "event: output", "data:  world", "", "event: done", "data: {}", ""])
    text, usage = run_backend(http, REPLICATE, GenerationParams(max_tokens=32, stop=["a", "b"]))
    assert text == "Hello world" and usage.completion_tokens > 0

    create = http.calls[0]
    assert create[2].endswith("/models/meta/llama/predictions") and create[4]["stream"] is True
    payload = create[4]["input"]
    assert payload["system_prompt"] == "Be brief" and payload["prompt"].endswith("User: Hi\nAssistant:")
    assert payload["max_tokens"] == 32 and payload["stop_sequences"] == "a,b"
    assert not any(c[0] == "request" and c[2].endswith("/c") for c in http.calls)  # finished normally: no cancel


def test_replicate_cancels_the_prediction_when_the_consumer_stops_early():
    http = replicate_http([])
    http.streams[0] = FakeStream(200, ["event: output", "data: one", "", "event: output", "data: two", "", "event: done", "data: {}", ""])
    stream = RemoteBackend(REPLICATE, http).stream(MESSAGES, GenerationParams(), Usage())
    assert next(stream) == "one"
    stream.close()  # user pressed Stop
    assert any(c[0] == "request" and c[2] == "https://api.replicate.com/v1/c" for c in http.calls)


def test_replicate_errors():
    bad = FakeHttp(responses=[HttpResponse(401, f"bad token {KEY}", {})])
    with pytest.raises(InferenceError) as err:
        run_backend(bad, REPLICATE)
    assert "rejected the API token" in str(err.value) and KEY not in str(err.value)

    no_stream = FakeHttp(responses=[HttpResponse(201, json.dumps({"urls": {}}), {}), HttpResponse(200, "{}", {})])
    with pytest.raises(InferenceError, match="doesn't support streaming"):
        run_backend(no_stream, REPLICATE)

    boom = replicate_http([])
    boom.streams[0] = FakeStream(200, ["event: error", "data: model crashed", ""])
    with pytest.raises(InferenceError, match="model crashed"):
        run_backend(boom, REPLICATE)


# --------------------------------------------------------------------------- providers

class FakeSecrets:
    def __init__(self, data): self.data, self.directory = data, Path(".")
    def get(self, n): return self.data.get(n)
    def exists(self, n): return n in self.data


def together(http):
    return TogetherProvider(FakeSecrets({"cloud/together/api_key": KEY}), http=http)


def test_together_validates_lists_chat_models_and_describes_the_endpoint():
    models = [{"id": "meta/llama-3", "type": "chat", "display_name": "Llama 3", "context_length": 8192},
              {"id": "img/sdxl", "type": "image"}, {"id": "a/embed", "type": "embedding"}, {"id": "z/lm", "type": "language"}]
    http = FakeHttp(responses=[HttpResponse(200, json.dumps(models), {}), HttpResponse(200, json.dumps(models), {})])
    provider = together(http)
    assert provider.validate_credentials().name == "Together AI account"
    catalog = provider.catalog()
    assert [m["id"] for m in catalog] == ["meta/llama-3", "z/lm"] and catalog[0]["context_length"] == 8192

    endpoint = provider.inference_endpoint(RemoteModel(id="cloud:together:l", provider=ProviderId.TOGETHER, name="l", remote_model="meta/llama-3"))
    assert endpoint.kind == "openai" and endpoint.base_url == "https://api.together.xyz/v1" and endpoint.model == "meta/llama-3"
    assert endpoint.headers["Authorization"] == f"Bearer {KEY}"
    assert http.calls[0][3]["Authorization"] == f"Bearer {KEY}"


@pytest.mark.parametrize("status,expected", [(401, AuthError), (402, QuotaError), (429, TransientError), (404, RemoteExecutionError)])
def test_http_status_mapping(status, expected):
    with pytest.raises(expected):
        raise_for_status(HttpResponse(status, "x", {"Retry-After": "3"}), "Together AI")
    try:
        raise_for_status(HttpResponse(429, "x", {"Retry-After": "3"}), "Together AI")
    except TransientError as exc:
        assert exc.retry_after == 3.0


def test_together_probe_sends_a_one_token_request():
    http = FakeHttp(responses=[HttpResponse(200, "{}", {})])
    model = RemoteModel(id="c", provider=ProviderId.TOGETHER, name="n", remote_model="meta/llama-3")
    assert together(http).test_model(model) == "meta/llama-3 responded"
    assert http.calls[0][4]["max_tokens"] == 1 and http.calls[0][2].endswith("/chat/completions")


def test_replicate_provider_validates_and_tolerates_odd_catalogs():
    secrets = FakeSecrets({"cloud/replicate/api_token": KEY})
    http = FakeHttp(responses=[HttpResponse(200, json.dumps({"username": "ann"}), {}),
                               HttpResponse(200, json.dumps({"models": [{"owner": "meta", "name": "llama"}, {"bad": 1}]}), {}),
                               HttpResponse(500, "oops", {})])
    provider = ReplicateProvider(secrets, http=http)
    assert provider.validate_credentials().name == "ann"
    assert provider.catalog() == [{"id": "meta/llama", "name": "meta/llama", "context_length": None}]
    assert provider.catalog() == []  # an API hiccup never breaks the picker


def test_runpod_serverless_endpoint_needs_an_endpoint_id():
    provider = RunPodProvider(FakeSecrets({"cloud/runpod/api_key": "rpa_key_0123456789abcdefgh"}))
    model = RemoteModel(id="c", provider=ProviderId.RUNPOD, name="n", remote_model="org/m", endpoint_id="abc123")
    endpoint = provider.inference_endpoint(model)
    assert endpoint.base_url == "https://api.runpod.ai/v2/abc123/openai/v1" and endpoint.headers["Authorization"].startswith("Bearer rpa_")
    with pytest.raises(ConfigError, match="endpoint id"):
        provider.inference_endpoint(model.model_copy(update={"endpoint_id": None}))


# --------------------------------------------------------------------------- engine integration

@pytest.fixture()
def engine_with_remote(monkeypatch):
    info = ModelInfo(id="cloud:together:llama", name="llama (cloud)", path="cloud:together:llama", kind="remote")
    inference.configure_remote(lambda: [info], lambda model_id: ENDPOINT)
    http = FakeHttp(streams=[FakeStream(200, sse(chunk("remote "), chunk("hello"), chunk(None, finish="stop"), "data: [DONE]"))])
    monkeypatch.setattr(remote_backend, "default_http", lambda: http)
    yield http
    inference.unload_model("cloud:together:llama")
    inference.configure_remote(lambda: [], lambda m: None)


def test_remote_models_appear_in_discovery_and_chat_through_the_normal_engine_path(engine_with_remote):
    assert "cloud:together:llama" in [m.id for m in inference.discover_models()]
    assert inference.resolve_model("cloud:together:llama").kind == "remote"
    text, usage = inference.chat("cloud:together:llama", MESSAGES, GenerationParams())
    assert text == "remote hello" and usage.finish_reason == "stop"
    assert inference.is_loaded("cloud:together:llama") and inference.unload_model("cloud:together:llama")


def test_a_broken_remote_registry_does_not_hide_local_models(monkeypatch):
    def boom():
        raise RuntimeError("db locked")

    inference.configure_remote(boom, lambda m: None)
    try:
        assert isinstance(inference.discover_models(), list)  # no exception
    finally:
        inference.configure_remote(lambda: [], lambda m: None)


def test_memory_checks_skip_remote_models(engine_with_remote):
    pytest.importorskip("sqlalchemy")  # the alerts module imports the job store
    from services.monitoring import alerts

    reading = {"memory": {"total_mb": 1000, "used_mb": 0, "percent": 0}, "gpu": None}
    result = alerts.check_context_fit("cloud:together:llama", 4096, reading)
    assert result["known"] is False and "provider's hardware" in result["message"]


# --------------------------------------------------------------------------- end to end through a tunnel

class OpenAIHandler(BaseHTTPRequestHandler):
    def log_message(self, *a): pass

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        self.server.seen.append((self.path, body))
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.end_headers()
        for piece in ("tunnel", " works"):
            self.wfile.write(f"data: {json.dumps({'choices': [{'delta': {'content': piece}}]})}\n\n".encode())
        self.wfile.write(b"data: [DONE]\n\n")


class UrllibHttp:
    """Tiny real-network Http (httpx isn't needed to test the tunnel path)."""

    def request(self, method, url, headers=None, json=None, timeout=30.0):
        raise NotImplementedError

    @contextmanager
    def stream(self, method, url, headers=None, json=None, timeout=120.0):
        import json as j

        req = urlrequest.Request(url, data=j.dumps(json).encode(), headers={"Content-Type": "application/json", **(headers or {})}, method=method)
        try:
            response = urlrequest.urlopen(req, timeout=timeout)
            status = response.status
        except HTTPError as exc:
            response, status = exc, exc.code

        class S:
            def __init__(self): self.status, self.headers = status, {}
            def iter_lines(self): return (l.decode().rstrip("\n") for l in response)
            def read_text(self): return response.read().decode()

        yield S()


def test_ssh_tunnel_to_an_openai_compatible_server_end_to_end(tmp_path):
    from core.cloud.providers.ssh_provider import SshProvider
    from core.cloud.schemas import SshProfile
    from core.cloud.ssh_profiles import SshProfileStore

    server = ThreadingHTTPServer(("127.0.0.1", 0), OpenAIHandler)
    server.seen = []
    threading.Thread(target=server.serve_forever, daemon=True).start()
    remote_port = server.server_address[1]

    class Session:
        def open_forward_channel(self, host, port):
            assert (host, port) == ("127.0.0.1", remote_port)  # the *remote* side of the forward
            return socket.create_connection(("127.0.0.1", remote_port))

        def close(self): pass

    secrets = FakeSecrets({})
    secrets.set = lambda n, v: secrets.data.__setitem__(n, v)
    secrets.delete = lambda n: secrets.data.pop(n, None)
    profiles = SshProfileStore(tmp_path / "p.json", secrets)
    profiles.save(SshProfile(name="box", host="h", username="u", inference_port=remote_port), "-----BEGIN KEY PRIVATE KEY-----\nx\n-----END KEY PRIVATE KEY-----", None)
    provider = SshProvider(secrets, profiles=profiles, session_factory=lambda p, s, h: Session())
    try:
        model = RemoteModel(id="cloud:ssh:box", provider=ProviderId.SSH, name="box", remote_model="my-model", endpoint_id="box")
        endpoint = provider.inference_endpoint(model)
        assert endpoint.base_url.startswith("http://127.0.0.1:") and endpoint.base_url != f"http://127.0.0.1:{remote_port}/v1"

        text = "".join(RemoteBackend(endpoint, UrllibHttp()).stream(MESSAGES, GenerationParams(), Usage()))
        assert text == "tunnel works"
        assert server.seen[0][0] == "/v1/chat/completions" and server.seen[0][1]["model"] == "my-model"

        assert provider.inference_endpoint(model).base_url == endpoint.base_url  # tunnel is reused
        no_port = SshProfile(name="box", host="h", username="u")
        profiles.save(no_port, None, None)
        provider.close_tunnels()
        with pytest.raises(ConfigError, match="no inference port"):
            provider.inference_endpoint(model)
    finally:
        provider.close_tunnels()
        server.shutdown()
