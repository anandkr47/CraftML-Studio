"""
Inference-only providers: Together AI (OpenAI-compatible) and Replicate (predictions API).

RunPod serverless endpoints and SSH-hosted servers are described by their own providers
(``runpod_provider`` / ``ssh_provider``); all of them yield an ``InferenceEndpoint`` that the
backend in ``services/inference/remote_backend.py`` knows how to stream from.
"""

from __future__ import annotations

from typing import Any, ClassVar, Dict, List, Optional

from core.cloud.errors import AuthError, CloudError, QuotaError, RemoteExecutionError, TransientError
from core.cloud.http import Http, HttpResponse, default_http
from core.cloud.providers.base import CloudProvider, InferenceEndpoint
from core.cloud.schemas import AccountInfo, Capabilities, FieldSpec, ProviderId, RemoteModel
from core.cloud.secrets import SecretStore, redact

TOGETHER_BASE = "https://api.together.xyz/v1"
REPLICATE_BASE = "https://api.replicate.com/v1"


def raise_for_status(response: HttpResponse, provider: str) -> None:
    """Map an HTTP failure to a typed error with a helpful message (never including the credential)."""
    status = response.status
    if status < 400:
        return
    detail = redact(response.text[:200].replace("\n", " "))
    if status in (401, 403):
        raise AuthError(f"{provider} rejected the API key.", hint=f"Create a new key in your {provider} account.")
    if status == 402:
        raise QuotaError(f"{provider} reports insufficient credit.", hint=f"Add credit in your {provider} account.")
    if status == 404:
        raise RemoteExecutionError(f"{provider} couldn't find that model or endpoint.")
    if status in (408, 429, 500, 502, 503, 504):
        raise TransientError(f"{provider} is busy or unavailable ({status}).", retry_after=response.retry_after())
    raise RemoteExecutionError(f"{provider} error {status}: {detail}")


class _InferenceOnly(CloudProvider):
    capabilities: ClassVar[Capabilities] = Capabilities(training=False, inference=True)

    def __init__(self, secrets: SecretStore, http: Optional[Http] = None):
        super().__init__(secrets)
        self.http = http or default_http()

    def _bearer(self, field: str) -> Dict[str, str]:
        return {"Authorization": f"Bearer {self.credential(field)}"}


class TogetherProvider(_InferenceOnly):
    id: ClassVar[ProviderId] = ProviderId.TOGETHER
    label: ClassVar[str] = "Together AI"
    description: ClassVar[str] = "Hosted open models behind an OpenAI-compatible API. Pay per token."
    fields: ClassVar[List[FieldSpec]] = [FieldSpec(name="api_key", label="API key", placeholder="From api.together.xyz/settings/api-keys")]

    def validate_credentials(self) -> AccountInfo:
        response = self.http.request("GET", f"{TOGETHER_BASE}/models", headers=self._bearer("api_key"))
        raise_for_status(response, "Together AI")
        return AccountInfo(name="Together AI account")

    def catalog(self) -> List[Dict[str, Any]]:
        """Chat models Together hosts (id, name, context length) for the model picker."""
        response = self.http.request("GET", f"{TOGETHER_BASE}/models", headers=self._bearer("api_key"))
        raise_for_status(response, "Together AI")
        raw = response.json()
        items = raw if isinstance(raw, list) else raw.get("data", [])
        return sorted(
            ({"id": m["id"], "name": m.get("display_name") or m["id"], "context_length": m.get("context_length")}
             for m in items if m.get("type") in ("chat", "language", None) and m.get("id")),
            key=lambda m: m["id"].lower(),
        )

    def inference_endpoint(self, model: RemoteModel) -> InferenceEndpoint:
        return InferenceEndpoint(kind="openai", base_url=TOGETHER_BASE, headers=self._bearer("api_key"), model=model.remote_model)

    def test_model(self, model: RemoteModel) -> str:
        return _probe_openai(self.http, self.inference_endpoint(model), "Together AI")


class ReplicateProvider(_InferenceOnly):
    id: ClassVar[ProviderId] = ProviderId.REPLICATE
    label: ClassVar[str] = "Replicate"
    description: ClassVar[str] = (
        "Run hosted models via Replicate. Language models differ in their inputs, so results are best-effort."
    )
    fields: ClassVar[List[FieldSpec]] = [FieldSpec(name="api_token", label="API token", placeholder="r8_…")]

    def validate_credentials(self) -> AccountInfo:
        response = self.http.request("GET", f"{REPLICATE_BASE}/account", headers=self._bearer("api_token"))
        raise_for_status(response, "Replicate")
        data = response.json()
        return AccountInfo(name=data.get("username") or "Replicate account")

    def catalog(self) -> List[Dict[str, Any]]:
        try:
            response = self.http.request("GET", f"{REPLICATE_BASE}/collections/language-models", headers=self._bearer("api_token"))
            raise_for_status(response, "Replicate")
            return [{"id": f"{m['owner']}/{m['name']}", "name": f"{m['owner']}/{m['name']}", "context_length": None}
                    for m in response.json().get("models", []) if m.get("owner") and m.get("name")]
        except (CloudError, ValueError, KeyError):
            return []  # the picker falls back to typing owner/name

    def inference_endpoint(self, model: RemoteModel) -> InferenceEndpoint:
        return InferenceEndpoint(kind="replicate", base_url=REPLICATE_BASE, headers=self._bearer("api_token"), model=model.remote_model)

    def test_model(self, model: RemoteModel) -> str:
        response = self.http.request("GET", f"{REPLICATE_BASE}/models/{model.remote_model}", headers=self._bearer("api_token"))
        raise_for_status(response, "Replicate")
        return f"Found {model.remote_model}"


def _probe_openai(http: Http, endpoint: InferenceEndpoint, provider: str) -> str:
    """One-token chat completion to prove the key, model and endpoint work together."""
    response = http.request(
        "POST", f"{endpoint.base_url.rstrip('/')}/chat/completions", headers=endpoint.headers, timeout=60.0,
        json={"model": endpoint.model, "messages": [{"role": "user", "content": "Hi"}], "max_tokens": 1},
    )
    raise_for_status(response, provider)
    return f"{endpoint.model} responded"
