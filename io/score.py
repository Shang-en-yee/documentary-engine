#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
make_score_from_track.py — 用现成曲目做配乐（裁切 + 响度包络 + 淡入淡出）

比程序合成更"像电影配乐"，代价是要遵守曲目授权（CC-BY 需署名）。

用法:
    python make_score_from_track.py \
        --track assets/music/"Eternal Hope.mp3" --track-start 72 --duration 180 \
        --edl examples/voyager.json --out out/score.wav \
        --credit "Eternal Hope — Kevin MacLeod (incompetech.com), CC BY 4.0"
"""
import argparse, json, os, subprocess, sys
import numpy as np

FF = r"C:\Users\bx\AppData\Roaming\Seewo\EasiNote5\Dependencies\FFmpeg\FFmpeg_2\ffmpeg.exe"
SR = 44100


def decode(path, start, dur):
    raw = os.path.join(os.environ["TEMP"], "track_%d.raw" % os.getpid())
    subprocess.run([FF, "-y", "-hide_banner", "-loglevel", "error",
                    "-ss", str(start), "-t", str(dur), "-i", path,
                    "-ac", "2", "-ar", str(SR), "-f", "s16le", raw], check=True)
    d = np.frombuffer(open(raw, "rb").read(), dtype=np.int16).astype(np.float32) / 32768
    os.remove(raw)
    return d[0::2].copy(), d[1::2].copy()


def envelope(edl, n):
    pts = sorted((edl.get("audio") or {}).get("envelope", []), key=lambda p: p["t"])
    if not pts:
        return np.ones(n, dtype=np.float32)
    t = np.arange(n) / SR
    xs = np.array([p["t"] for p in pts], dtype=np.float32)
    ys = np.array([p["gain"] for p in pts], dtype=np.float32)
    return np.interp(t, xs, ys).astype(np.float32)


def fade(x, sr, fin=0.8, fout=2.0):
    n = len(x)
    a = int(fin * sr)
    b = int(fout * sr)
    if a > 0:
        x[:a] *= np.linspace(0, 1, a) ** 1.6
    if b > 0:
        x[-b:] *= np.linspace(1, 0, b) ** 1.4
    return x


def write_wav(path, L, R):
    import wave
    data = np.empty(len(L) * 2, dtype=np.int16)
    data[0::2] = np.clip(L * 32767, -32768, 32767).astype(np.int16)
    data[1::2] = np.clip(R * 32767, -32768, 32767).astype(np.int16)
    with wave.open(path, "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(data.tobytes())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--track", required=True)
    ap.add_argument("--track-start", type=float, default=0.0)
    ap.add_argument("--duration", type=float, required=True)
    ap.add_argument("--edl", default=None, help="用它里面的 audio.envelope 塑形")
    ap.add_argument("--out", required=True)
    ap.add_argument("--credit", default="")
    ap.add_argument("--gain", type=float, default=2.4, help="整体增益")
    a = ap.parse_args()

    L, R = decode(a.track, a.track_start, a.duration)
    n = min(len(L), int(a.duration * SR))
    L, R = L[:n], R[:n]
    if len(L) < n:                     # 素材不够长就补静音
        L = np.pad(L, (0, n - len(L)))
        R = np.pad(R, (0, n - len(R)))

    if a.edl:
        env = envelope(json.load(open(a.edl, encoding="utf-8")), n)
        L *= env
        R *= env

    L = fade(L, SR) * a.gain
    R = fade(R, SR) * a.gain

    peak = max(np.abs(L).max(), np.abs(R).max(), 1e-9)
    if peak > 0.92:                    # 软限幅
        L = np.tanh(L / peak * 1.15) * 0.92
        R = np.tanh(R / peak * 1.15) * 0.92

    write_wav(a.out, L, R)
    rms = float(np.sqrt((L ** 2 + R ** 2).mean() / 2))
    print(f"OK  {a.out}  {n/SR:.1f}s  RMS {rms:.3f}  峰值 {max(np.abs(L).max(), np.abs(R).max()):.2f}")
    if a.credit:
        print(f"署名要求: {a.credit}")


if __name__ == "__main__":
    main()
