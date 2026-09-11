# IRL-MC SmoothCam

Client-side camera smoothing for a **headless, server-directed camera account**
(the companion to [`irlmc-director-server`](https://github.com/al5ina5/irlmc-director-server)).

The server moves the camera by 20 Hz teleports. Minecraft's local-player camera
does not interpolate those (`absMoveTo` sets `xo = x`), so it steps. This mod
replaces that with a two-stage smoother:

1. **Snapshot interpolation** — every server-applied pose is buffered with a
   timestamp, and each frame is rendered at `now - 80 ms`, interpolating between
   the two bracketing snapshots. Handles jitter and late packets.
2. **Critically-damped spring (SmoothDamp)** — the interpolated pose is low-passed
   by a spring, removing the residual speed wobble from packet-timing jitter.

Cost: ~130 ms of latency. Result: smooth, native-feeling motion.

## Files

- `src/.../SmoothCam.java` — the two-stage smoother.
- `src/.../mixin/CameraSmoothMixin.java` — hooks `Camera.alignWithEntity` and
  applies the smoothed pose.
- `rig/` — the capture rig that runs the headless camera on a GPU:
  - `run_gpu_camera.sh` / `gpu_session.sh` — cage (wlroots) headless on the DRM
    render node + Xwayland, launching the camera client and the two feeds.
  - `camfeed_server.py` — MJPEG broadcaster for the browser (`:8080`).
  - `obstserver.py` — H.264/MPEG-TS broadcaster for OBS (`:8090/live.ts`) with
    real timestamps (OBS's mpjpeg path runs at 25 fps and judders).
  - `start_aether.sh` — starts the server.
  - `measure_motion.py` — smoothness measurement helper.

> Paths in `rig/` are machine-specific (`/tmp/opencode`, `/home/alsinas`);
> adjust before reusing.

## Build

```bash
./gradlew build   # -> build/libs/irlmc-smoothcam-<version>.jar
```

Drop the jar into the camera client's `mods/` folder. It only affects the local
camera; normal clients are unaffected.

## Notes

- Uses NeoForge `26.1.2.106`, Minecraft `26.1.2`, Java 25 toolchain.
- Mixin targets `net.minecraft.client.Camera#alignWithEntity(float)`.
- Toggle at runtime by creating `/tmp/opencode/smoothcam.off`.
- CSV diagnostics: create `/tmp/opencode/smoothcam.log`.

MIT licensed.
