#!/usr/bin/env python3
"""Robust, jitter-free MJPEG broadcast server for the LocalAether2 camera.

- One ffmpeg grabs Xvfb and emits concatenated JPEGs on stdout; a reader thread
  keeps only the newest frame, so a slow/uneven render never backs up.
- A broadcast thread emits at a FIXED cadence (target FPS). If the game produced
  no new frame in a tick it repeats the previous one, so viewers see a steady
  clock instead of gaps. If it produced several, only the newest is shown.
- Each HTTP client gets its own bounded queue; a stalled viewer drops frames
  instead of blocking everyone.
"""
import os
import subprocess
import threading
import time
from collections import deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

W = int(os.environ.get("CAM_OUT_W", "1280"))
H = int(os.environ.get("CAM_OUT_H", "720"))
FPS = int(os.environ.get("CAM_FPS", "60"))
QUALITY = int(os.environ.get("CAM_QUALITY", "8"))
IN_W = int(os.environ.get("CAM_IN_W", "1280"))
IN_H = int(os.environ.get("CAM_IN_H", "720"))
DISPLAY = os.environ.get("CAM_DISPLAY", ":95+0,0")
PORT = int(os.environ.get("CAM_PORT", "8080"))
WINDOW_ID = os.environ.get("CAM_WINDOW_ID", "")

PAGE = """<!doctype html>
<html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>LocalAether2 camera</title>
<style>
 html,body{margin:0;height:100%;background:#0d0d0d;color:#ddd;font-family:system-ui,sans-serif}
 .bar{padding:10px 14px;font-size:14px;opacity:.8}
 .wrap{display:flex;align-items:center;justify-content:center;height:calc(100% - 42px)}
 img{max-width:100%;max-height:100%;box-shadow:0 0 30px #000;background:#000}
</style></head><body>
<div class="bar">LocalAether2 &mdash; auto-director camera (following the player)</div>
<div class="wrap"><img src="stream.mjpg" alt="camera feed"></div>
</body></html>
"""

_latest = None
_has_frame = threading.Event()
_subscribers = []
_subs_lock = threading.Lock()


def reader():
    """Keep the newest decoded JPEG from ffmpeg; restart ffmpeg if it dies."""
    global _latest
    vf = (f"scale={W}:{H}:flags=bicubic" if (W, H) != (IN_W, IN_H) else "null")
    if WINDOW_ID:
        # Capture a specific X window's drawable (works even on rootless Xwayland,
        # where the screen root stays black). Size comes from the window itself.
        src = ["-f", "x11grab", "-framerate", "60",
               "-window_id", WINDOW_ID, "-i", DISPLAY.split("+")[0]]
    else:
        src = ["-f", "x11grab", "-framerate", "60",
               "-video_size", f"{IN_W}x{IN_H}", "-i", DISPLAY]
    cmd = [
        "ffmpeg", "-loglevel", "error",
        *src,
        "-vf", vf,
        "-f", "image2pipe", "-c:v", "mjpeg", "-q:v", str(QUALITY),
        "pipe:1",
    ]
    while True:
        p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        buf = bytearray()
        try:
            while True:
                chunk = p.stdout.read(65536)
                if not chunk:
                    break
                buf += chunk
                while True:
                    s = buf.find(b"\xff\xd8")
                    if s < 0:
                        if len(buf) > 4_000_000:
                            buf.clear()
                        break
                    e = buf.find(b"\xff\xd9", s + 2)
                    if e < 0:
                        if s > 0:
                            del buf[:s]
                        break
                    _latest = bytes(buf[s:e + 2])
                    del buf[:e + 2]
                    _has_frame.set()
        except Exception:
            pass
        finally:
            try:
                p.kill()
            except Exception:
                pass
        time.sleep(1)


def broadcaster():
    """Emit the newest frame to all subscribers on a fixed clock with repeats."""
    period = 1.0 / FPS
    next_at = time.monotonic()
    while True:
        frame = _latest
        if frame is not None:
            with _subs_lock:
                subs = list(_subscribers)
            for q in subs:
                try:
                    q.append(frame)          # deque(maxlen=2): drops stale frames
                except Exception:
                    pass
        next_at += period
        delay = next_at - time.monotonic()
        if delay > 0:
            time.sleep(delay)
        else:
            # Fell behind (shouldn't happen); resync to avoid a burst.
            next_at = time.monotonic()


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *a):
        pass

    def do_GET(self):
        if self.path in ("/", "/index.html"):
            body = PAGE.encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)
            return
        if self.path.startswith("/stream.mjpg"):
            self.send_response(200)
            self.send_header("Age", "0")
            self.send_header("Cache-Control", "no-cache, private")
            self.send_header("Content-Type",
                             "multipart/x-mixed-replace; boundary=frame")
            self.end_headers()
            q = deque(maxlen=2)
            with _subs_lock:
                _subscribers.append(q)
            try:
                while True:
                    if not q:
                        time.sleep(0.005)
                        continue
                    frame = q[-1]
                    q.clear()
                    self.wfile.write(
                        b"--frame\r\nContent-Type: image/jpeg\r\n"
                        + b"Content-Length: " + str(len(frame)).encode() + b"\r\n\r\n")
                    self.wfile.write(frame)
                    self.wfile.write(b"\r\n")
            except (BrokenPipeError, ConnectionResetError, TimeoutError, OSError):
                return
            finally:
                with _subs_lock:
                    if q in _subscribers:
                        _subscribers.remove(q)
        self.send_error(404)


if __name__ == "__main__":
    threading.Thread(target=reader, daemon=True).start()
    threading.Thread(target=broadcaster, daemon=True).start()
    srv = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    srv.daemon_threads = True
    print(f"camera feed on http://0.0.0.0:{PORT}/ ({W}x{H} @ {FPS} display {DISPLAY})",
          flush=True)
    srv.serve_forever()
