package com.irlmc.smoothcam;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.nio.file.StandardOpenOption;
import java.util.ArrayDeque;
import java.util.Deque;
import net.minecraft.client.Minecraft;
import net.minecraft.util.Mth;
import net.minecraft.world.phys.Vec3;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

/**
 * Camera smoothing = snapshot interpolation + a critically-damped spring.
 *
 * Stage 1 (snapshot interpolation): every server-applied camera pose is pushed
 * into a timestamped buffer and rendered at {@code now - RENDER_DELAY}, linearly
 * interpolating between the two snapshots that bracket that instant. Handles
 * packet loss / large gaps and turns a 20 Hz pose stream into a continuous one.
 *
 * Stage 2 (SmoothDamp): the interpolated pose is then fed through a critically
 * damped spring (Unity's SmoothDamp formulation). This is the key part: the
 * server's pose *arrival* jitters by ~11 ms, so even a perfect interpolator
 * inherits that jitter as speed wobble. A spring low-passes it away with no
 * overshoot, giving the steady, "native" glide of a real follow camera.
 *
 * Total added latency is about RENDER_DELAY + SMOOTH_TIME (~130 ms), which is the
 * standard cost of jitter-free network interpolation.
 *
 * Toggle: create /tmp/opencode/smoothcam.off.
 */
public final class SmoothCam {
    private static final Logger LOG = LoggerFactory.getLogger("irlmc-smoothcam");

    private static final long RENDER_DELAY_NANOS = 80_000_000L; // 80 ms
    private static final double SMOOTH_TIME = 0.06;             // spring time constant (s)
    private static final double SNAP_DISTANCE_SQ = 24.0 * 24.0;
    private static final long MAX_AGE_NANOS = 1_000_000_000L;
    private static final int MAX_SNAPSHOTS = 64;

    private static final Path OFF_MARKER = Paths.get("/tmp/opencode/smoothcam.off");
    private static final Path LOG_MARKER = Paths.get("/tmp/opencode/smoothcam.log");
    private static final Path LOG_FILE = Paths.get("/tmp/opencode/smoothcam.csv");

    private record Snap(long t, Vec3 pos, float yaw, float pitch) {}

    private static final Deque<Snap> buffer = new ArrayDeque<>();
    private static Vec3 lastRawPos = null;
    private static float lastRawYaw;
    private static float lastRawPitch;

    // Spring state
    private static Vec3 outPos = null;
    private static float outYaw;
    private static float outPitch;
    private static Vec3 velPos = Vec3.ZERO;
    private static final float[] velYaw = new float[1];
    private static final float[] velPitch = new float[1];
    private static long lastNanos = 0L;

    private static long logFrames = 0;

    private SmoothCam() {}

    public static boolean enabled() {
        return !Files.exists(OFF_MARKER);
    }

    public static void reset() {
        synchronized (buffer) {
            buffer.clear();
        }
        lastRawPos = null;
        outPos = null;
        velPos = Vec3.ZERO;
        velYaw[0] = 0f;
        velPitch[0] = 0f;
        lastNanos = 0L;
    }

    public static float[] tick(Vec3 rawPos, float rawYaw, float rawPitch, float partialTicks) {
        Minecraft mc = Minecraft.getInstance();
        long now = System.nanoTime();
        boolean on = enabled();

        if (!on || rawPos == null) {
            reset();
            if (!on && rawPos != null) log(mc, rawPos, rawYaw, rawPitch, now, false);
            return null;
        }

        // ---- Stage 1: record snapshots on change ----
        boolean changed = lastRawPos == null
                || lastRawPos.distanceToSqr(rawPos) > 1.0e-8
                || rawYaw != lastRawYaw || rawPitch != lastRawPitch;
        if (changed) {
            boolean snap = lastRawPos != null && lastRawPos.distanceToSqr(rawPos) > SNAP_DISTANCE_SQ;
            synchronized (buffer) {
                if (snap) buffer.clear();
                buffer.addLast(new Snap(now, rawPos, rawYaw, rawPitch));
                long cutoff = now - MAX_AGE_NANOS;
                while (buffer.size() > MAX_SNAPSHOTS
                        || (buffer.size() > 2 && buffer.peekFirst().t() < cutoff)) {
                    buffer.removeFirst();
                }
            }
            lastRawPos = rawPos;
            lastRawYaw = rawYaw;
            lastRawPitch = rawPitch;
        }

        float[] target = sample(now - RENDER_DELAY_NANOS);
        if (target == null) return null;

        // ---- Stage 2: critically-damped spring toward the interpolated pose ----
        double dt = lastNanos == 0 ? 1.0 / 60.0 : (now - lastNanos) / 1e9;
        lastNanos = now;
        if (dt <= 0 || dt > 0.25) dt = 1.0 / 60.0;

        Vec3 targetPos = new Vec3(target[0], target[1], target[2]);
        if (outPos == null) {
            outPos = targetPos;
            outYaw = target[3];
            outPitch = target[4];
        } else {
            double[] p = smoothDamp(outPos, targetPos, velPos, SMOOTH_TIME, dt);
            outPos = new Vec3(p[0], p[1], p[2]);
            outYaw = smoothDampAngle(outYaw, target[3], velYaw, SMOOTH_TIME, dt, true);
            outPitch = smoothDampAngle(outPitch, target[4], velPitch, SMOOTH_TIME, dt, false);
        }

        log(mc, outPos, outYaw, outPitch, now, true);
        return new float[]{(float) outPos.x, (float) outPos.y, (float) outPos.z, outYaw, outPitch};
    }

    /** Unity-style critically damped spring; returns {x,y,z} and updates velocity in-place. */
    private static double[] smoothDamp(Vec3 cur, Vec3 target, Vec3 vel, double smoothTime, double dt) {
        double omega = 2.0 / Math.max(0.0001, smoothTime);
        double x = omega * dt;
        double exp = 1.0 / (1.0 + x + 0.48 * x * x + 0.235 * x * x * x);
        double cx = cur.x - target.x, cy = cur.y - target.y, cz = cur.z - target.z;
        double tempx = (vel.x + omega * cx) * dt;
        double tempy = (vel.y + omega * cy) * dt;
        double tempz = (vel.z + omega * cz) * dt;
        velPos = new Vec3(
                (vel.x - omega * tempx) * exp,
                (vel.y - omega * tempy) * exp,
                (vel.z - omega * tempz) * exp);
        return new double[]{
                target.x + (cx + tempx) * exp,
                target.y + (cy + tempy) * exp,
                target.z + (cz + tempz) * exp};
    }

    private static float smoothDampAngle(float cur, float target, float[] vel,
                                         double smoothTime, double dt, boolean wrap) {
        if (wrap) cur = target + Mth.wrapDegrees(cur - target);
        double omega = 2.0 / Math.max(0.0001, smoothTime);
        double x = omega * dt;
        double exp = 1.0 / (1.0 + x + 0.48 * x * x + 0.235 * x * x * x);
        double change = cur - target;
        double temp = (vel[0] + omega * change) * dt;
        vel[0] = (float) ((vel[0] - omega * temp) * exp);
        return (float) (target + (change + temp) * exp);
    }

    private static float[] sample(long target) {
        synchronized (buffer) {
            if (buffer.isEmpty()) return null;
            Snap prev = null;
            for (Snap s : buffer) {
                if (s.t() >= target) {
                    if (prev == null) return toArray(s);
                    double span = (double) (s.t() - prev.t());
                    double a = span <= 0 ? 1.0 : (double) (target - prev.t()) / span;
                    return lerp(prev, s, a);
                }
                prev = s;
            }
            return toArray(prev);
        }
    }

    private static float[] lerp(Snap a, Snap b, double t) {
        Vec3 p = a.pos().lerp(b.pos(), t);
        float y = a.yaw() + Mth.wrapDegrees(b.yaw() - a.yaw()) * (float) t;
        float x = a.pitch() + (b.pitch() - a.pitch()) * (float) t;
        return new float[]{(float) p.x, (float) p.y, (float) p.z, y, x};
    }

    private static float[] toArray(Snap s) {
        return new float[]{(float) s.pos().x, (float) s.pos().y, (float) s.pos().z,
                s.yaw(), s.pitch()};
    }

    private static void log(Minecraft mc, Vec3 p, float yaw, float pitch, long nanos, boolean smoothed) {
        if (p == null || mc.level == null || !Files.exists(LOG_MARKER)) return;
        if (logFrames++ > 500_000) return;
        String line = nanos + "," + p.x + "," + p.y + "," + p.z + "," + yaw + "," + pitch
                + "," + (smoothed ? 1 : 0) + "\n";
        try {
            Files.writeString(LOG_FILE, line,
                    StandardOpenOption.CREATE, StandardOpenOption.APPEND);
        } catch (IOException e) {
            LOG.debug("smoothcam log failed", e);
        }
    }
}
