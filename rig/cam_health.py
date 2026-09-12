#!/usr/bin/env python3
"""Prints 'yes' if the camera account (directorcam) is online on the MC server,
'no' otherwise. Used by the rig supervisor to detect a client stuck on a menu
or a transient disconnect while the server is still up.

Reads the RCON port/password from the server's server.properties.
"""
import os
import socket
import struct
import sys

SERVER_DIR = os.environ.get(
    "IRLMC_SERVER_DIR", os.path.expanduser("~/Minecraft Servers/LocalAether2-SMP"))
NAME = os.environ.get("IRLMC_CAM_NAME", "directorcam")
HOST = "127.0.0.1"


def props():
    port, pw = 25575, ""
    try:
        with open(os.path.join(SERVER_DIR, "server.properties")) as f:
            for line in f:
                line = line.strip()
                if line.startswith("rcon.port="):
                    port = int(line.split("=", 1)[1])
                elif line.startswith("rcon.password="):
                    pw = line.split("=", 1)[1]
    except OSError:
        pass
    return port, pw


def pkt(rid, ptype, body):
    data = struct.pack("<ii", rid, ptype) + body.encode("utf-8") + b"\x00\x00"
    return struct.pack("<i", len(data)) + data


def recv(sock):
    hdr = b""
    while len(hdr) < 4:
        c = sock.recv(4 - len(hdr))
        if not c:
            raise OSError("eof")
        hdr += c
    ln = struct.unpack("<i", hdr)[0]
    buf = b""
    while len(buf) < ln:
        c = sock.recv(ln - len(buf))
        if not c:
            raise OSError("eof")
        buf += c
    return buf[8:-2].decode("utf-8", "replace")


def main():
    port, pw = props()
    try:
        s = socket.create_connection((HOST, port), timeout=5)
        s.sendall(pkt(1, 3, pw))
        recv(s)  # auth response
        s.sendall(pkt(2, 2, "list"))
        body = recv(s)
        s.close()
        print("yes" if NAME.lower() in body.lower() else "no")
    except Exception:
        print("no")


if __name__ == "__main__":
    sys.exit(main())
