#!/bin/bash
# GPU session: runs INSIDE cage (Wayland compositor on the AMD render node).
# Forces X11 (Xwayland) so ffmpeg's x11grab can capture the GPU-rendered frame.
unset WAYLAND_DISPLAY
export DISPLAY="${DISPLAY:-:1}"

# Wait for the Minecraft server to accept connections, else the client gets
# "connection refused" and sits on the disconnect screen.
for i in $(seq 1 150); do
    (exec 3<>/dev/tcp/127.0.0.1/25565) 2>/dev/null && { exec 3>&-; break; }
    sleep 2
done
# Also wait until the server has finished loading (port opens before "Done"),
# otherwise the client joins and gets dropped mid-boot.
for i in $(seq 1 120); do
    grep -aq "Done (" /tmp/opencode/aether-server.log 2>/dev/null && break
    sleep 2
done
sleep 5

# Headless camera client (GPU via Xwayland)
/tmp/opencode/prism/squashfs-root/AppRun \
    --dir /tmp/opencode/prismdata \
    -l LocalAether2Cam -a directorcam -s localhost \
    > /tmp/opencode/gpu-camera.log 2>&1 &
CAMPID=$!

# Wait for the game window, then let it reach the world
for i in $(seq 1 150); do
    xdotool search --name "Minecraft" >/dev/null 2>&1 && break
    sleep 2
done
sleep 10

# Clean feed: hide the HUD (F1)
W=$(xdotool search --name "Minecraft" | head -n1)
[ -n "$W" ] && { xdotool windowfocus "$W" 2>/dev/null; xdotool key --clearmodifiers F1; }

# MJPEG feed straight off the GPU display
CAM_DISPLAY="$DISPLAY+0,0" CAM_WINDOW_ID="$W" \
CAM_IN_W=1280 CAM_IN_H=720 CAM_OUT_W=1280 CAM_OUT_H=720 CAM_FPS=60 CAM_QUALITY=8 \
    python3 /tmp/opencode/camfeed_server.py > /tmp/opencode/gpu-feed.log 2>&1 &

# H.264 MPEG-TS feed for OBS (survives reconnects)
DISPLAY="$DISPLAY" OBS_DISPLAY="$DISPLAY" OBS_WINDOW_ID="$W" OBS_PORT=8090 \
    python3 /tmp/opencode/obstserver.py > /tmp/opencode/obs-feed.log 2>&1 &

wait $CAMPID
