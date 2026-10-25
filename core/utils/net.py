"""
Work around networks whose IPv6 is advertised but broken.

Python's ``socket.create_connection`` (used by httpx/huggingface_hub) tries addresses in
the order ``getaddrinfo`` returns them, IPv6 first, waiting the full timeout on each.
Browsers and curl race both families ("Happy Eyeballs", RFC 8305), so such networks look
fine to the user while every Hub request from the app stalls for minutes.

``start_ipv6_probe()`` checks once, in the background, whether IPv6 can reach the Hub.
Only if IPv6 fails *and* IPv4 works does it reorder ``getaddrinfo`` results to put IPv4
first (a stable sort, so nothing else changes). Healthy, IPv4-only, IPv6-only and offline
networks are left untouched.
"""

import logging
import socket
import threading
from typing import Callable, List, Tuple

logger = logging.getLogger(__name__)

PROBE_HOST = "huggingface.co"
PROBE_PORT = 443

_installed = False
_lock = threading.Lock()


def _can_connect(family: int, host: str, port: int, timeout: float) -> bool:
    try:
        infos = socket.getaddrinfo(host, port, family, socket.SOCK_STREAM)
    except OSError:
        return False
    for fam, kind, proto, _, addr in infos[:2]:
        try:
            with socket.socket(fam, kind, proto) as sock:
                sock.settimeout(timeout)
                sock.connect(addr)
                return True
        except OSError:
            continue
    return False


def prefer_ipv4() -> None:
    """Return IPv4 addresses before IPv6 ones from ``socket.getaddrinfo`` (idempotent)."""
    global _installed
    with _lock:
        if _installed:
            return
        original: Callable[..., List[Tuple]] = socket.getaddrinfo

        def getaddrinfo(*args, **kwargs):
            return sorted(original(*args, **kwargs), key=lambda info: info[0] != socket.AF_INET)

        getaddrinfo.__wrapped__ = original  # type: ignore[attr-defined]
        socket.getaddrinfo = getaddrinfo
        _installed = True


def ipv6_broken(host: str = PROBE_HOST, port: int = PROBE_PORT, timeout: float = 3.0) -> bool:
    """True when ``host`` has working IPv4 but unreachable IPv6."""
    if not socket.has_ipv6:
        return False
    try:
        families = {info[0] for info in socket.getaddrinfo(host, port, 0, socket.SOCK_STREAM)}
    except OSError:
        return False  # offline or DNS failure: nothing to decide
    if socket.AF_INET6 not in families or socket.AF_INET not in families:
        return False
    if _can_connect(socket.AF_INET6, host, port, timeout):
        return False
    return _can_connect(socket.AF_INET, host, port, timeout)


def start_ipv6_probe() -> None:
    """Run the check in a daemon thread so startup never waits on the network."""

    def run() -> None:
        try:
            if ipv6_broken():
                prefer_ipv4()
                logger.warning("IPv6 is unreachable on this network; preferring IPv4 for outgoing connections")
        except Exception as exc:  # noqa: BLE001 - a probe must never take the app down
            logger.debug("IPv6 probe failed: %s", exc)

    threading.Thread(target=run, name="ipv6-probe", daemon=True).start()
