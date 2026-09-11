#!/bin/bash
# Runs INSIDE cage (GPU/Xwayland). Launches the headless camera + both feeds.
unset WAYLAND_DISPLAY
export DISPLAY="${DISPLAY:-:1}"
BASE="$HOME/.local/share/irlmc-cam"

# Wait for the Minecraft server to accept connections, then let it finish loading.
for i in $(seq 1 180); do
    (exec 3<>/dev/tcp/127.0.0.1/25565) 2>/dev/null && { exec 3>&-; break; }
    sleep 2
done
sleep 20

"$BASE/prism/squashfs-root/AppRun" --dir "$BASE/prismdata" \
    -l LocalAether2Cam -a directorcam -s localhost > "$BASE/gpu-camera.log" 2>&1 &
CAMPID=$!

for i in $(seq 1 180); do
    xdotool search --name "Minecraft" >/dev/null 2>&1 && break
    sleep 2
done
sleep 10
W=$(xdotool search --name "Minecraft" | head -n1)
[ -n "$W" ] && { xdotool windowfocus "$W" 2>/dev/null; xdotool key --clearmodifiers F1; }

CAM_DISPLAY="${DISPLAY}+0,0" CAM_WINDOW_ID="$W" \
CAM_IN_W=1280 CAM_IN_H=720 CAM_OUT_W=1280 CAM_OUT_H=720 CAM_FPS=60 CAM_QUALITY=8 \
    python3 "$BASE/camfeed_server.py" > "$BASE/feed.log" 2>&1 &
DISPLAY="$DISPLAY" OBS_DISPLAY="$DISPLAY" OBS_WINDOW_ID="$W" OBS_PORT=8090 \
    python3 "$BASE/obstserver.py" > "$BASE/obs-feed.log" 2>&1 &

wait $CAMPID
