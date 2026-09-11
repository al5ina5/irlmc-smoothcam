#!/bin/bash
# Runs INSIDE cage (GPU/Xwayland). Supervises the headless camera + both feeds.
#
# Auto-reconnect: if the server goes down (or the camera client exits), it kills
# the camera + feeds, waits for the server to come back, and relaunches. So a
# server restart no longer leaves the camera stuck on the disconnect screen.
unset WAYLAND_DISPLAY
export DISPLAY="${DISPLAY:-:1}"
BASE="$HOME/.local/share/irlmc-cam"
LOG="$BASE/gpu-camera.log"

server_up() {
    (exec 3<>/dev/tcp/127.0.0.1/25565) 2>/dev/null && { exec 3>&-; return 0; }
    return 1
}

stop_feeds() {
    pkill -f "$BASE/camfeed_server.py" 2>/dev/null
    pkill -f "$BASE/obstserver.py" 2>/dev/null
}

echo "[rig] supervisor started $(date)"

while true; do
    # Wait until the server is accepting connections, then let it finish loading.
    until server_up; do sleep 2; done
    echo "[rig] server up; waiting to settle"
    sleep 20

    echo "[rig] launching camera client"
    "$BASE/prism/squashfs-root/AppRun" --dir "$BASE/prismdata" \
        -l LocalAether2Cam -a directorcam -s localhost > "$LOG" 2>&1 &
    CAMPID=$!

    # Wait for the game window.
    W=""
    for i in $(seq 1 180); do
        W=$(xdotool search --name "Minecraft" 2>/dev/null | head -n1)
        [ -n "$W" ] && break
        sleep 2
    done
    sleep 10
    [ -n "$W" ] && { xdotool windowfocus "$W" 2>/dev/null; xdotool key --clearmodifiers F1; }

    # (Re)start feeds bound to this window.
    stop_feeds
    sleep 1
    CAM_DISPLAY="${DISPLAY}+0,0" CAM_WINDOW_ID="$W" \
    CAM_IN_W=1280 CAM_IN_H=720 CAM_OUT_W=1280 CAM_OUT_H=720 CAM_FPS=60 CAM_QUALITY=8 \
        python3 "$BASE/camfeed_server.py" > "$BASE/feed.log" 2>&1 &
    DISPLAY="$DISPLAY" OBS_DISPLAY="$DISPLAY" OBS_WINDOW_ID="$W" OBS_PORT=8090 \
        python3 "$BASE/obstserver.py" > "$BASE/obs-feed.log" 2>&1 &
    echo "[rig] feeds started for window $W"

    # Monitor: keep running while the camera process is alive and the server is up.
    while kill -0 "$CAMPID" 2>/dev/null; do
        sleep 5
        if ! server_up; then
            sleep 5
            server_up || { echo "[rig] server went down -> reconnecting"; break; }
        fi
    done

    # Teardown and loop to wait for the server again.
    kill "$CAMPID" 2>/dev/null
    pkill -f "$BASE/prism/squashfs-root" 2>/dev/null
    stop_feeds
    sleep 3
done
