"""
Minimal HTTP abstraction for the cloud layer (httpx under the hood, imported lazily).

Having our own tiny interface keeps providers and the remote inference backend testable with a
fake and maps transport failures to typed errors in one place.  TLS verification is always on;
proxies are honoured via the standard ``HTTPS_PROXY`` / ``NO_PROXY`` environment variables.
"""

from __future__ import annotations

import json as jsonlib
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any, Dict, Iterator, Optional, Protocol

from core.cloud.errors import TransientError
from core.cloud.retry import retry_after_seconds

CONNECT_TIMEOUT = 10.0
READ_TIMEOUT = 120.0  # LLM streams can pause between tokens


@dataclass
class HttpResponse:
    status: int
    text: str
    headers: Dict[str, str]

    def json(self) -> Any:
        return jsonlib.loads(self.text)

    def retry_after(self) -> Optional[float]:
        return retry_after_seconds(self.headers)


class StreamResponse(Protocol):
    status: int
    headers: Dict[str, str]

    def iter_lines(self) -> Iterator[str]: ...
    def read_text(self) -> str: ...


class Http(Protocol):
    def request(self, method: str, url: str, headers: Optional[Dict[str, str]] = None, json: Any = None,
                timeout: float = 30.0) -> HttpResponse: ...

    def stream(self, method: str, url: str, headers: Optional[Dict[str, str]] = None, json: Any = None,
               timeout: float = READ_TIMEOUT): ...  # context manager yielding StreamResponse


class HttpxHttp:
    def _client(self, timeout: float):
        import httpx

        return httpx.Client(timeout=httpx.Timeout(timeout, connect=CONNECT_TIMEOUT), follow_redirects=False)

    def request(self, method, url, headers=None, json=None, timeout=30.0) -> HttpResponse:
        import httpx

        try:
            with self._client(timeout) as client:
                r = client.request(method, url, headers=headers, json=json)
            return HttpResponse(r.status_code, r.text, dict(r.headers))
        except httpx.HTTPError as exc:
            raise TransientError(f"Network error talking to {url.split('/')[2]} ({type(exc).__name__}).") from exc

    @contextmanager
    def stream(self, method, url, headers=None, json=None, timeout=READ_TIMEOUT):
        import httpx

        try:
            with self._client(timeout) as client:
                with client.stream(method, url, headers=headers, json=json) as r:
                    yield _Stream(r)
        except httpx.HTTPError as exc:
            raise TransientError(f"Network error talking to {url.split('/')[2]} ({type(exc).__name__}).") from exc


class _Stream:
    def __init__(self, response):
        self._r = response
        self.status = response.status_code
        self.headers = dict(response.headers)

    def iter_lines(self) -> Iterator[str]:
        return self._r.iter_lines()

    def read_text(self) -> str:
        self._r.read()
        return self._r.text


def default_http() -> Http:
    return HttpxHttp()
