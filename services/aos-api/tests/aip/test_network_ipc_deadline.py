"""Actual Unix timing, no mocked clocks or socket receive implementation."""
import socket
import struct
import threading
import time
import pytest
from aos_api.aip_network_issuer_ipc import read_issuer_frame, IssuerProtocolBlocked


def test_slow_fragments_share_header_and_body_deadline():
    left, right = socket.socketpair()
    left.settimeout(12)
    stop = threading.Event()
    data = struct.pack('>I', 3) + b'abc'
    def send():
        try:
            for byte in data:
                if stop.wait(1):
                    break
                right.sendall(bytes([byte]))
        except OSError:
            pass
    thread = threading.Thread(target=send)
    thread.start()
    started = time.monotonic()
    try:
        with pytest.raises(IssuerProtocolBlocked):
            read_issuer_frame(left)
        assert 4.5 <= time.monotonic() - started < 6.5
        assert left.gettimeout() == 12
    finally:
        stop.set()
        left.close()
        right.close()
        thread.join(timeout=2)
    assert not thread.is_alive()


def test_complete_fragmented_frame_restores_timeout():
    left, right = socket.socketpair()
    left.settimeout(None)
    try:
        right.sendall(struct.pack('>I', 3)[:2])
        right.sendall(struct.pack('>I', 3)[2:] + b'a')
        right.sendall(b'bc')
        assert read_issuer_frame(left) == b'abc'
        assert left.gettimeout() is None
    finally:
        left.close()
        right.close()


def test_truncated_frame_restores_timeout():
    left, right = socket.socketpair()
    left.settimeout(9)
    try:
        right.sendall(struct.pack('>I', 3) + b'a')
        right.close()
        with pytest.raises(IssuerProtocolBlocked):
            read_issuer_frame(left)
        assert left.gettimeout() == 9
    finally:
        left.close()
        right.close()
