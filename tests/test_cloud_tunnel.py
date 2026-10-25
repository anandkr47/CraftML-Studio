"""LocalForward relays real TCP connections through an injected channel opener."""

import socket
import sys
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.cloud.tunnel import LocalForward


def echo_server():
    server = socket.socket()
    server.bind(("127.0.0.1", 0))
    server.listen(4)

    def serve():
        while True:
            try:
                conn, _ = server.accept()
            except OSError:
                return
            def handle(c):
                while True:
                    data = c.recv(4096)
                    if not data:
                        break
                    c.sendall(data.upper())
                c.close()
            threading.Thread(target=handle, args=(conn,), daemon=True).start()

    threading.Thread(target=serve, daemon=True).start()
    return server


def test_forward_relays_bytes_both_ways_and_binds_loopback_only():
    remote = echo_server()
    port = remote.getsockname()[1]
    forward = LocalForward(lambda: socket.create_connection(("127.0.0.1", port)))
    local_port = forward.start()
    try:
        assert forward._server.getsockname()[0] == "127.0.0.1"  # never exposed to the LAN
        with socket.create_connection(("127.0.0.1", local_port), timeout=5) as client:
            client.sendall(b"hello tunnel")
            assert client.recv(64) == b"HELLO TUNNEL"
            client.sendall(b" again")
            assert client.recv(64) == b" AGAIN"
        # several concurrent connections
        results = []
        def one(i):
            with socket.create_connection(("127.0.0.1", local_port), timeout=5) as c:
                c.sendall(f"msg{i}".encode())
                results.append(c.recv(64))
        threads = [threading.Thread(target=one, args=(i,)) for i in range(5)]
        [t.start() for t in threads]; [t.join() for t in threads]
        assert sorted(results) == [f"MSG{i}".encode() for i in range(5)]
    finally:
        forward.close()
        remote.close()
    assert not forward.alive


def test_channel_open_failure_closes_the_client_cleanly():
    def refuse():
        raise OSError("administratively prohibited")

    forward = LocalForward(refuse)
    port = forward.start()
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=5) as client:
            assert client.recv(16) == b""  # connection closed, no hang
    finally:
        forward.close()
