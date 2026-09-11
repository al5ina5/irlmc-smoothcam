#!/bin/bash
export XDG_RUNTIME_DIR="/run/user/$(id -u)"
export WLR_BACKENDS=headless
export WLR_RENDER_DRM_DEVICE=/dev/dri/renderD128
export WLR_LIBINPUT_NO_DEVICES=1
export XDG_SESSION_TYPE=wayland
exec cage -- "$HOME/.local/share/irlmc-cam/gpu_session.sh"
