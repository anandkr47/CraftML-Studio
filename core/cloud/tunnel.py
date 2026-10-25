"""
Local TCP port forward (ssh -L equivalent) over an existing SSH transport.

Binds ``127.0.0.1`` on an ephemeral port only (never a LAN interface, no firewall prompts on
any OS) and relays each connection through a ``direct-tcpip`` channel opened by ``open_channel``.
The channel opener is injected, so this module needs no SSH library and is tested with plain sockets.
"""

from __future__ import annotations

import logging
import socket
import threading
from typing import Callable, Optional, Protocol

logger = logging.getLogger(__name__)

BUFFER = 65536


class Channel(Protocol):
    def recv(self, n: int) -> bytes: ...
    def sendall(self, data: bytes) -> None: ...
    def close(self) -> None: ...


class LocalForward:
    def __init__(self, open_channel: Callable[[], Channel]):
        self._open_channel = open_channel
        self._server: Optional[socket.socket] = None
        self._closed = threading.Event()
        self.port = 0

    def start(self) -> int:
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.bind(("127.0.0.1", 0))
        server.listen(16)
        server.settimeout(0.5)
        self._server, self.port = server, server.getsockname()[1]
        threading.Thread(target=self._accept_loop, name="ssh-forward", daemon=True).start()
        return self.port

    @property
    def alive(self) -> bool:
        return self._server is not None and not self._closed.is_set()

    def _accept_loop(self) -> None:
        assert self._server is not None
        while not self._closed.is_set():
            try:
                client, _ = self._server.accept()
            except socket.timeout:
                continue
            except OSError:
                return
            threading.Thread(target=self._relay, args=(client,), daemon=True).start()

    def _relay(self, client: socket.socket) -> None:
        try:
            channel = self._open_channel()
        except Exception as exc:  # noqa: BLE001 - remote refused / transport gone
            logger.warning("SSH forward: could not open channel: %s", exc)
            client.close()
            return

        def pump(read: Callable[[int], bytes], write: Callable[[bytes], None]) -> None:
            try:
                while True:
                    data = read(BUFFER)
                    if not data:
                        break
                    write(data)
            except OSError:
                pass
            finally:
                for closer in (client.close, channel.close):
                    try:
                        closer()
                    except Exception:  # noqa: BLE001
                        pass

        threading.Thread(target=pump, args=(client.recv, channel.sendall), daemon=True).start()
        pump(channel.recv, client.sendall)

    def close(self) -> None:
        self._closed.set()
        if self._server is not None:
            try:
                self._server.close()
            except OSError:
                pass
