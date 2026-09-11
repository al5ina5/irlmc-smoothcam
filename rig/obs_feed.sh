#!/bin/bash
# H.264 MPEG-TS feed for OBS (port 8090).
#
# Why: OBS Media Source decodes the MJPEG stream through ffmpeg's mpjpeg
# demuxer, which has no timestamps and defaults to 25 fps -> judder. MPEG-TS
# carries PTS, so OBS presents every frame at the right time.
#
# OBS: Media Source -> uncheck "Local File" -> Input:
#   http://127.0.0.1:8090
#   Input Format: mpegts   (or leave blank; it auto-detects)
WID="$1"
export DISPLAY="${DISPLAY:-:1}"
while true; do
    ffmpeg -loglevel error \
        -f x11grab -window_id "$WID" -framerate 60 -i "$DISPLAY" \
        -c:v libx264 -preset ultrafast -tune zerolatency \
        -pix_fmt yuv420p -g 60 -b:v 8M -maxrate 12M -bufsize 12M \
        -f mpegts -listen 1 http://0.0.0.0:8090
    sleep 1
done
