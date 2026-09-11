package com.irlmc.smoothcam;

import net.neoforged.api.distmarker.Dist;
import net.neoforged.fml.common.Mod;

/**
 * Client-only camera interpolator.
 *
 * Minecraft's camera already lerps between an entity's previous (`xo..x`) and
 * current position, but a server teleport goes through {@code absMoveTo}, which
 * sets {@code xo = x} and discards the previous value. A camera account moved by
 * 20 Hz server teleports therefore snaps once per tick.
 *
 * This mod re-derives the missing "previous tick" sample inside the camera and
 * interpolates with {@code partialTicks}, restoring smooth motion. It only
 * touches the local camera and only matters for the headless director camera;
 * normal clients are unaffected beyond a tiny camera-side smoothing.
 */
@Mod(value = IrlmcSmoothCam.MOD_ID, dist = Dist.CLIENT)
public final class IrlmcSmoothCam {
    public static final String MOD_ID = "irlmc_smoothcam";

    public IrlmcSmoothCam() {
        // The mixin does the work; no init needed.
    }
}
