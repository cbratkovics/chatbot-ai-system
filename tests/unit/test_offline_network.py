"""The default test workflow cannot spend money through real provider calls."""
import socket

import pytest


def test_offline_guard_blocks_dns_and_direct_connections():
    with pytest.raises(RuntimeError, match="Offline test blocked"):
        socket.getaddrinfo("api.openai.com", 443)
    with socket.socket() as sock:
        with pytest.raises(RuntimeError, match="Offline test blocked"):
            sock.connect(("1.1.1.1", 443))
        with pytest.raises(RuntimeError, match="Offline test blocked"):
            sock.connect_ex(("1.1.1.1", 443))
