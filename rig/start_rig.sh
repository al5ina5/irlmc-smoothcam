#!/bin/bash
BASE="$HOME/.local/share/irlmc-cam"
pkill -f "gpu_session.sh" 2>/dev/null
pkill -f "cage -- $BASE/gpu_session.sh" 2>/dev/null
sleep 1
setsid nohup "$BASE/run_gpu_camera.sh" > "$BASE/rig.log" 2>&1 < /dev/null &
echo "camera rig starting — it waits for the server (25565), then joins as directorcam."
