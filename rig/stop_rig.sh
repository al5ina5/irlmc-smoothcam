#!/bin/bash
BASE="$HOME/.local/share/irlmc-cam"
pkill -f "$BASE/gpu_session.sh" 2>/dev/null
pkill -f "$BASE/prism/squashfs-root" 2>/dev/null
pkill -f "$BASE/camfeed_server.py" 2>/dev/null
pkill -f "$BASE/obstserver.py" 2>/dev/null
pkill -f "cage -- $BASE/gpu_session.sh" 2>/dev/null
echo "camera rig stopped."
