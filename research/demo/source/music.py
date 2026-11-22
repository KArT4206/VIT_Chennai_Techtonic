"""Instrumental soundtrack synthesised from scratch (numpy only): no samples, no vocals, no speech.

    python3 research/demo/source/music.py <out.wav> <timeline.csv>

Layers, all generated here: a slow chord pad (detuned sine/triangle, slow attack), a low drone that thickens during the
pupil-alignment scene, a soft filtered pulse during the dataset/dynamics/performance scenes, quiet filtered-noise
swells at scene boundaries, and a resolving final chord. Mastered to about -18 dBFS RMS with a soft limiter (peak < -1 dBFS) with a 2 s fade-out.
"""
import csv, sys, wave
import numpy as np

out, tl = sys.argv[1:3]
SR = 48000
scenes = [(r["scene"], float(r["start_s"]), float(r["end_s"])) for r in csv.DictReader(open(tl))]
T = scenes[-1][2]; n = int(T * SR); t = np.arange(n) / SR
rng = np.random.default_rng(2026)


def note(f):
    return 440.0 * 2 ** ((f - 69) / 12)


def lowpass(x, cutoff):
    a = np.exp(-2 * np.pi * cutoff / SR); y = np.empty_like(x); acc = 0.0
    for i in range(len(x)):
        acc = (1 - a) * x[i] + a * acc; y[i] = acc
    return y


def env(start, end, att=1.5, rel=1.5):
    e = np.clip((t - start) / att, 0, 1) * np.clip((end - t) / rel, 0, 1)
    return e * e * (3 - 2 * e)


mix = np.zeros((n, 2))
# chord pad: A minor - F - C - G  (MIDI roots), 8 s per chord
chords = [[57, 60, 64, 69], [53, 57, 60, 65], [48, 55, 60, 64], [55, 59, 62, 67]]
for ci, start in enumerate(np.arange(0, T, 8.0)):
    ch = chords[ci % 4]; e = env(start, min(start + 9.0, T), 2.5, 3.0)
    for j, m in enumerate(ch):
        f = note(m)
        for det, pan in ((-0.12, 0.3), (0.12, 0.7)):
            ph = 2 * np.pi * f * (1 + det / 100) * t
            s = (0.7 * np.sin(ph) + 0.3 * (2 / np.pi) * np.arcsin(np.sin(ph))) * e * 0.045
            mix[:, 0] += s * (1 - pan); mix[:, 1] += s * pan
# drone: low A, louder in the discovery scene (tension), plus a quiet high fifth there
disc = next(s for s in scenes if s[0].startswith("5"))
dr_e = 0.35 + 0.65 * env(disc[1], disc[2], 2.0, 2.0)
drone = (np.sin(2 * np.pi * note(33) * t) + 0.4 * np.sin(2 * np.pi * note(45) * t)) * dr_e * 0.05
high = np.sin(2 * np.pi * note(88) * t) * env(disc[1] + 3, disc[2] - 1, 3, 3) * 0.012 * (0.6 + 0.4 * np.sin(2 * np.pi * 0.25 * t))
mix += np.c_[drone + high, drone + high]
# soft pulse, 96 bpm, during dataset / dynamics / performance
p0 = next(s[1] for s in scenes if s[0].startswith("7")); p1 = next(s[2] for s in scenes if s[0].startswith("9"))
pulse = np.zeros(n); beat = 60 / 96
for bt in np.arange(p0, p1, beat):
    i = int(bt * SR); L = int(0.25 * SR); k = np.arange(min(L, n - i)) / SR
    pulse[i:i + len(k)] += np.sin(2 * np.pi * (55 + 30 * np.exp(-k * 30)) * k) * np.exp(-k * 14) * 0.18
mix += np.c_[pulse, pulse] * env(p0, p1, 1.0, 1.0)[:, None]
# quiet noise swells into each new scene (transition accents)
noise = lowpass(rng.standard_normal(n), 1800)
sw = np.zeros(n)
for _, st, _ in scenes[1:]:
    sw += np.exp(-((t - st) / 0.35) ** 2)
mix += np.c_[noise * sw * 0.02, noise * sw * 0.02]
# final resolving chord (A major add9) over the last scene
fs = scenes[-1][1]
for m in (45, 57, 61, 64, 71):
    mix += np.c_[np.sin(2 * np.pi * note(m) * t), np.sin(2 * np.pi * note(m) * t * 1.001)] * env(fs - 0.5, T, 1.0, 2.0)[:, None] * 0.05
mix[:, 0] = lowpass(mix[:, 0], 6000); mix[:, 1] = lowpass(mix[:, 1], 6000)
mix *= np.clip((T - t) / 2.0, 0, 1)[:, None] * np.clip(t / 0.8, 0, 1)[:, None]
rms = np.sqrt((mix ** 2).mean()); mix *= 10 ** (-18 / 20) / rms
mix = 0.89 * np.tanh(mix / 0.89)          # soft limiter: peaks stay below -1 dBFS, no hard clipping
with wave.open(out, "wb") as w:
    w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR); w.writeframes((mix * 32767).astype("<i2").tobytes())
print("MUSIC_DONE", out, round(T, 2), "s", "peak", round(float(np.abs(mix).max()), 3))
