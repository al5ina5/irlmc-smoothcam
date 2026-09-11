#!/usr/bin/env python3
"""Persistent H.264/MPEG-TS broadcaster for OBS (port 8090).

One ffmpeg encodes the GPU camera window to MPEG-TS on stdout; this server fans
the byte stream out to any number of clients and survives client disconnects
(unlike ffmpeg's -listen, which exits and can't rebind while the port is in
TIME_WAIT). MPEG-TS carries PTS, so OBS paces frames correctly at 60 fps.

OBS: Media Source, uncheck Local File, Input: http://127.0.0.1:8090/live.ts
"""
import os
import subprocess
import threading
import time
from collections import deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PORT = int(os.environ.get("OBS_PORT", "8090"))
DISPLAY = os.environ.get("OBS_DISPLAY", ":1")
WINDOW_ID = os.environ.get("OBS_WINDOW_ID", "")
BITRATE = os.environ.get("OBS_BITRATE", "8M")

_clients = []          # list of deque(maxlen=N)
_lock = threading.Lock()


def reader():
    cmd = [
        "ffmpeg", "-loglevel", "error",
        "-f", "x11grab", "-framerate", "60", "-window_id", WINDOW_ID, "-i", DISPLAY,
        "-c:v", "libx264", "-preset", "ultrafast", "-tune", "zerolatency",
        "-pix_fmt", "yuv420p", "-g", "60", "-b:v", BITRATE,
        "-maxrate", "12M", "-bufsize", "12M",
        "-muxdelay", "0", "-muxpreload", "0", "-flush_packets", "1",
        "-f", "mpegts", "pipe:1",
    ]
    while True:
        p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        try:
            while True:
                data = p.stdout.read(8192)
                if not data:
                    break
                with _lock:
                    subs = list(_clients)
                for q in subs:
                    q.append(data)
        except Exception:
            pass
        finally:
            try:
                p.kill()
            except Exception:
                pass
        time.sleep(1)


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *a):
        pass

    def do_GET(self):
        q = deque(maxlen=200)
        with _lock:
            _clients.append(q)
        self.send_response(200)
        self.send_header("Content-Type", "video/mp2t")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "close")
        self.end_headers()
        try:
            while True:
                if not q:
                    time.sleep(0.005)
                    continue
                while q:
                    self.wfile.write(q.popleft())
        except (BrokenPipeError, ConnectionResetError, TimeoutError, OSError):
            return
        finally:
            with _lock:
                if q in _clients:
                    _clients.remove(q)


if __name__ == "__main__":
    assert WINDOW_ID, "OBS_WINDOW_ID required"
    threading.Thread(target=reader, daemon=True).start()
    srv = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    srv.daemon_threads = True
    print(f"OBS MPEG-TS feed on http://0.0.0.0:{PORT}/live.ts (window {WINDOW_ID})", flush=True)
    srv.serve_forever()
