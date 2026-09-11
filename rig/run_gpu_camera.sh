#!/bin/bash
# Launch the headless GPU camera: cage (wlroots) on the AMD render node,
# headless output 1280x720, running gpu_session.sh inside.
export XDG_RUNTIME_DIR="/run/user/$(id -u)"
export WLR_BACKENDS=headless
export WLR_RENDER_DRM_DEVICE=/dev/dri/renderD128
export WLR_LIBINPUT_NO_DEVICES=1
export XDG_SESSION_TYPE=wayland
exec cage -- /tmp/opencode/gpu_session.sh
