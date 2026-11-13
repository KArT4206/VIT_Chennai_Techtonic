"""Deterministic natural eye-expression motion model. Pure Python, no Blender dependency.

A sequence is a list of timed events (saccades, smooth pursuits, blinks, brow gestures). It is
sampled at a fixed frame rate into per-frame channels:

    yaw_deg    cyclopean gaze azimuth; + is towards the SUBJECT'S LEFT (image right, world +X)
    pitch_deg  cyclopean gaze elevation; + is up
    blink      0 = lids follow gaze only, 1 = fully closed
    brow_L_mm, brow_R_mm   vertical brow offset (+ raises), subject's left/right
    dist_m     fixation distance from the eye midpoint

Kinematics follow published human data rather than linear tweens:
- Saccades: duration from the main sequence (D ms = 2.2 * A deg + 21, Carpenter 1988) with a
  skewed minimum-jerk profile (peak velocity early, as in real saccades) and a small glissade.
- Fixations: slow drift from seeded, smoothed noise (about 0.1 deg), so the eye never freezes.
- Blinks: fast closing (~75 ms), short closed phase, slower exponential-like opening (~170 ms);
  during a blink the eyes dip slightly down (Bell's phenomenon, ~2 deg).
- Brows: rise a little with upward gaze and on deliberate "brow flashes"; dip slightly in a
  full blink. Left and right differ by a small fixed amount (faces are not symmetric).

Everything is seeded, so the same input always gives the same frames.
"""

import math
import random

FPS = 24
NEUTRAL_DIST_M = 0.40          # neutral fixation = the camera, i.e. eye contact with the viewer

# Rig limits (deg). The MakeHuman lids have no corrective shapes, so a rotated cornea starts to
# meet lid skin. These limits keep that contact no deeper than in eyes.py's own validated +-8 deg
# evaluator poses (0.45 mm): measured 0.45 mm at 19 deg sideways, 0.45 mm at -8 deg down, and only
# 0.23 mm at +15 deg up. Combined down+side is worse than either alone, so paths avoid it.
YAW_LIMIT = 19.0
PITCH_UP_LIMIT = 15.0
PITCH_DOWN_LIMIT = -8.0

BELL_DEG = 2.0
BROW_PER_UP_DEG = 0.11         # mm of brow lift per degree of upward gaze
BROW_ASYM = (1.0, 0.86)        # L, R gain: small natural asymmetry


def _clampgaze(yaw, pitch):
    return (max(-YAW_LIMIT, min(YAW_LIMIT, yaw)),
            max(PITCH_DOWN_LIMIT, min(PITCH_UP_LIMIT, pitch)))


def saccade_duration_s(amplitude_deg):
    return (2.2 * amplitude_deg + 21.0) / 1000.0


def _min_jerk(t):
    return t * t * t * (10.0 - 15.0 * t + 6.0 * t * t)


def saccade_profile(t):
    """0..1 progress of a saccade at normalised time t in [0, 1]. Skewed: faster early."""
    if t <= 0.0:
        return 0.0
    if t >= 1.0:
        return 1.0
    return _min_jerk(t ** 0.78)


def blink_profile(t, close_s=0.075, hold_s=0.03, open_s=0.17):
    """Lid closure 0..1 at time t (s) since blink onset."""
    if t < 0.0:
        return 0.0
    if t < close_s:
        x = t / close_s
        return x * x * (3.0 - 2.0 * x)          # accelerating then braking closure
    t -= close_s
    if t < hold_s:
        return 1.0
    t -= hold_s
    if t < open_s:
        x = t / open_s
        return (1.0 - x) ** 1.6                  # fast initial lift, slow final opening
    return 0.0


def _smooth(t):
    t = max(0.0, min(1.0, t))
    return t * t * (3.0 - 2.0 * t)


class Sequence:
    """Builds a gaze/lid/brow timeline from events and samples it per frame."""

    def __init__(self, duration_s, seed, fps=FPS):
        self.duration = duration_s
        self.fps = fps
        self.rng = random.Random(seed)
        self.gaze_keys = [(0.0, 0.0, 0.0, "hold", 0.0)]    # (t_start, yaw, pitch, kind, dur)
        self.blinks = []                                   # (t, amount, speed)
        self.brow_gestures = []                            # (t, peak_mm, rise_s, hold_s, fall_s)
        self._drift = self._make_drift()

    # ---------------------------------------------------------------- authoring
    def saccade(self, t, yaw, pitch):
        yaw, pitch = _clampgaze(yaw, pitch)
        y0, p0 = self._gaze_at_end()
        amp = math.hypot(yaw - y0, pitch - p0)
        self.gaze_keys.append((t, yaw, pitch, "saccade", saccade_duration_s(amp)))

    def pursuit(self, t, path, duration_s):
        """Smooth eye movement through a list of (yaw, pitch) waypoints (e.g. an eye roll)."""
        self.gaze_keys.append((t, [_clampgaze(*p) for p in path], None, "pursuit", duration_s))

    def blink(self, t, amount=1.0, speed=1.0):
        self.blinks.append((t, amount, speed))

    def brow(self, t, peak_mm, rise_s=0.25, hold_s=0.5, fall_s=0.5):
        self.brow_gestures.append((t, peak_mm, rise_s, hold_s, fall_s))

    # ---------------------------------------------------------------- sampling
    def _gaze_at_end(self):
        k = self.gaze_keys[-1]
        if k[3] == "pursuit":
            return k[1][-1]
        return k[1], k[2]

    def _make_drift(self):
        """Fixational drift: sum of a few seeded low-frequency sinusoids, ~0.1 deg."""
        comps = []
        for _ in range(4):
            comps.append((self.rng.uniform(0.25, 1.1), self.rng.uniform(0, 2 * math.pi),
                          self.rng.uniform(0.25, 1.1), self.rng.uniform(0, 2 * math.pi)))
        def drift(t):
            dy = sum(math.sin(2 * math.pi * f1 * t + p1) for f1, p1, _, _ in comps) * 0.03
            dp = sum(math.sin(2 * math.pi * f2 * t + p2) for _, _, f2, p2 in comps) * 0.025
            return dy, dp
        return drift

    def gaze(self, t):
        yaw, pitch = 0.0, 0.0
        moving = False
        for t0, a, b, kind, dur in self.gaze_keys:
            if t < t0:
                break
            if kind == "hold":
                yaw, pitch = a, b
            elif kind == "saccade":
                s = saccade_profile((t - t0) / dur) if dur > 0 else 1.0
                # glissade: a small (~4 %) post-saccadic overshoot that settles within ~40 ms
                over = 0.0
                if t - t0 > dur:
                    x = (t - t0 - dur) / 0.04
                    over = 0.04 * math.exp(-3.0 * x) * math.sin(math.pi * min(x, 1.0)) if x < 3 else 0.0
                moving = moving or (t - t0) < dur
                yaw, pitch = yaw + (a - yaw) * (s + over), pitch + (b - pitch) * (s + over)
            elif kind == "pursuit":
                pts = [(yaw, pitch)] + list(a)
                u = max(0.0, min(1.0, (t - t0) / dur))
                u = _smooth(u)                              # ease in/out of the whole pursuit
                seg = min(int(u * (len(pts) - 1)), len(pts) - 2)
                f = u * (len(pts) - 1) - seg
                # Catmull-Rom through the waypoints for a round, continuous path
                p0 = pts[max(seg - 1, 0)]; p1 = pts[seg]; p2 = pts[seg + 1]; p3 = pts[min(seg + 2, len(pts) - 1)]
                def cr(i):
                    return 0.5 * ((2 * p1[i]) + (-p0[i] + p2[i]) * f + (2 * p0[i] - 5 * p1[i] + 4 * p2[i] - p3[i]) * f * f
                                  + (-p0[i] + 3 * p1[i] - 3 * p2[i] + p3[i]) * f ** 3)
                yaw, pitch = cr(0), cr(1)
                moving = moving or u < 1.0
        if not moving:
            dy, dp = self._drift(t)
            yaw, pitch = yaw + dy, pitch + dp
        return yaw, pitch

    def blink_amount(self, t):
        b = 0.0
        for t0, amount, speed in self.blinks:
            b = max(b, amount * blink_profile((t - t0) * speed))
        return b

    def brow_base(self, t):
        mm = 0.0
        for t0, peak, rise, hold, fall in self.brow_gestures:
            x = t - t0
            if x < 0:
                continue
            if x < rise:
                mm += peak * _smooth(x / rise)
            elif x < rise + hold:
                mm += peak
            elif x < rise + hold + fall:
                mm += peak * (1.0 - _smooth((x - rise - hold) / fall))
        return mm

    def frames(self):
        n = int(round(self.duration * self.fps))
        out = []
        for i in range(n):
            t = i / self.fps
            yaw, pitch = self.gaze(t)
            b = self.blink_amount(t)
            pitch_eye = pitch - BELL_DEG * b                 # Bell's phenomenon
            yaw, pitch_eye = _clampgaze(yaw, pitch_eye)      # glissade/Bell never exceed rig limits
            brow =self.brow_base(t) + BROW_PER_UP_DEG * max(pitch, 0.0) - 0.6 * b
            out.append({
                "frame": i, "time_s": round(t, 6),
                "yaw_deg": round(yaw, 5), "pitch_deg": round(pitch_eye, 5),
                "blink": round(b, 5),
                "brow_L_mm": round(brow * BROW_ASYM[0], 5), "brow_R_mm": round(brow * BROW_ASYM[1], 5),
                "dist_m": NEUTRAL_DIST_M,
            })
        return out


# --------------------------------------------------------------------------- the three inputs

def left(seed=11):
    """Look towards the subject's LEFT (image right), hold, return. 5 s."""
    s = Sequence(5.0, seed)
    s.saccade(0.85, 17.5, 1.5)
    s.blink(0.80, 1.0)                 # gaze-evoked blink accompanying the large saccade
    s.brow(0.9, 0.6, 0.3, 1.6, 0.6)    # faint attentive lift
    s.saccade(2.05, 18.8, 0.6)         # small corrective re-fixation
    s.saccade(3.35, 0.0, 0.0)
    s.blink(4.10, 0.55, 1.1)           # partial blink after settling
    return s


def right(seed=23):
    """Look towards the subject's RIGHT (image left), hold, return. 5 s."""
    s = Sequence(5.0, seed)
    s.saccade(0.95, -17.0, 0.8)
    s.blink(0.92, 1.0)
    s.brow(1.0, 0.5, 0.3, 1.4, 0.6)
    s.saccade(2.20, -18.6, 0.2)
    s.saccade(3.45, 0.0, 0.0)
    s.blink(4.25, 0.5, 1.15)
    return s


def generate(seed=7):
    """Main demonstration, 12 s: look around, glance down, roll the eyes up, return with a blink."""
    s = Sequence(12.0, seed)
    s.saccade(0.90, 16.0, 1.0)                      # glance to subject's left
    s.saccade(1.85, 17.4, 0.4)                      # corrective micro re-fixation
    s.blink(2.55, 1.0)                              # blink with the large crossing saccade
    s.saccade(2.60, -17.5, 0.5)                     # across to subject's right
    s.saccade(3.70, -6.0, 13.0)                     # up
    s.brow(3.65, 2.2, 0.22, 0.75, 0.55)             # brow flash with the upward look
    s.saccade(4.85, 1.0, -7.0)                      # glance down; upper lid follows down
    # (no blink during the down-glance: a lowered lid over a lowered cornea exceeded the contact limit)
    s.pursuit(6.40, [(14.0, 1.0), (16.0, 8.0), (4.0, 14.5), (-11.0, 11.0), (-16.0, 2.5)], 1.9)  # eye roll
    s.brow(6.90, 1.8, 0.45, 0.6, 0.7)               # brows lift as the eyes roll over the top
    s.saccade(8.85, -2.0, 0.6)                      # back near centre
    s.blink(9.10, 1.0, 0.95)                        # complete blink, slightly slower
    s.saccade(9.95, 0.0, 0.0)                       # settle on the camera
    s.blink(11.0, 0.35, 1.3)                        # small incomplete blink before the end
    return s


INPUTS = {"left": left, "right": right, "generate": generate}
