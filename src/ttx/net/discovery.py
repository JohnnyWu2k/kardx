"""Small UDP LAN discovery protocol. Replies never determine the host address."""
import json
import socket
import time
import uuid

DISCOVERY_PORT = 12346
MAGIC = "KARDX-LAN-1"


def advertise(stop, describe, ready=None):
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        try:
            sock.bind(("", DISCOVERY_PORT))
            sock.settimeout(0.2)
        except OSError:
            if ready:
                ready.set()
            return
        if ready:
            ready.set()
        while not stop.is_set():
            try:
                raw, address = sock.recvfrom(1024)
                query = json.loads(raw)
                if query.get("magic") == MAGIC and isinstance(query.get("nonce"), str):
                    response = {"magic": MAGIC, "nonce": query["nonce"][:32], **describe()}
                    sock.sendto(json.dumps(response).encode(), address)
            except (socket.timeout, ValueError, OSError, AttributeError):
                continue


def discover(timeout=1.0):
    nonce = uuid.uuid4().hex
    results = {}
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        sock.settimeout(0.1)
        query = json.dumps({"magic": MAGIC, "nonce": nonce}).encode()
        for target in ("255.255.255.255", "127.0.0.1"):
            try:
                sock.sendto(query, (target, DISCOVERY_PORT))
            except OSError:
                pass
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            try:
                raw, address = sock.recvfrom(2048)
                response = json.loads(raw)
                port, name = response.get("port"), response.get("name")
                if response.get("magic") == MAGIC and response.get("nonce") == nonce and type(port) is int and 0 < port < 65536 and isinstance(name, str):
                    results[(address[0], port)] = {"host": address[0], "port": port,
                                                  "name": "".join(c for c in name[:40] if c.isprintable())}
            except (socket.timeout, ValueError, OSError, AttributeError):
                continue
    return list(results.values())
