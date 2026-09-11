package com.irlmc.smoothcam.mixin;

import com.irlmc.smoothcam.SmoothCam;
import net.minecraft.client.Camera;
import net.minecraft.world.phys.Vec3;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.Shadow;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfo;

/**
 * Runs at the tail of {@link Camera#alignWithEntity(float)} — after vanilla has
 * set the camera position/rotation from the (teleport-snapped) entity — and
 * replaces them with an interpolation that keeps the previous tick's pose.
 */
@Mixin(Camera.class)
public abstract class CameraSmoothMixin {

    @Shadow private Vec3 position;
    @Shadow private float xRot;
    @Shadow private float yRot;

    @Inject(method = "alignWithEntity(F)V", at = @At("TAIL"))
    private void smoothcam$interpolate(float partialTicks, CallbackInfo ci) {
        float[] out = SmoothCam.tick(this.position, this.yRot, this.xRot, partialTicks);
        if (out == null) return;
        this.position = new Vec3(out[0], out[1], out[2]);
        this.yRot = out[3];
        this.xRot = out[4];
    }
}
