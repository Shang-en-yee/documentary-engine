#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
qc/selftest.py — 质检器的自检（单元测试）

用合成数据构造「已知有毛病」的序列，断言检测器真的能抓到。
质检器自己没被验证过，等于没有质检。

    python qc/selftest.py
"""
import os
import sys

import cv2
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))

import video as V  # noqa: E402

FPS = 30
W, H = 960, 540


def synth(n, base=40, noise=3, drift=0.0, seed=0):
    """合成一段有缓慢运动 + 颗粒的画面"""
    rng = np.random.default_rng(seed)
    frames = []
    for i in range(n):
        img = np.full((H, W, 3), base + i * drift, dtype=np.float32)
        img += rng.normal(0, noise, (H, W, 3))
        frames.append(np.clip(img, 0, 255).astype(np.uint8))
    return frames


def metrics(frames):
    lumas = np.array([cv2.cvtColor(f, cv2.COLOR_BGR2GRAY).mean() for f in frames])
    diffs = np.array([0.0] + [float(np.mean(np.abs(
        cv2.cvtColor(frames[i], cv2.COLOR_BGR2GRAY).astype(np.float32) -
        cv2.cvtColor(frames[i - 1], cv2.COLOR_BGR2GRAY).astype(np.float32))))
        for i in range(1, len(frames))])
    return lumas, diffs


def detect_stutter(diffs, med, run_limit=V.STUTTER_RUN):
    still = max(0.10, med * 0.20)
    run = best = 0
    for v in diffs:
        run = run + 1 if v < still else 0
        best = max(best, run)
    return best >= run_limit and med > 0.2


def detect_flicker(lumas):
    return float(np.median(np.abs(np.diff(lumas)))) > V.FLICKER_MED


def detect_black(lumas):
    run = best = 0
    for b in lumas < V.BLACK_LUMA:
        run = run + 1 if b else 0
        best = max(best, run)
    return best >= V.BLACK_RUN


def detect_pacing(durs):
    durs = np.array(durs, dtype=float)
    cv_ = durs.std() / max(durs.mean(), 1e-6)
    return cv_ < V.DUR_CV_MIN


CASES = []


def case(name):
    def deco(fn):
        CASES.append((name, fn))
        return fn
    return deco


@case("正常运动画面 → 不该报卡顿")
def _():
    f = synth(120, drift=1.2)
    lumas, diffs = metrics(f)
    assert not detect_stutter(diffs, np.median(diffs[1:])), "正常画面误报卡顿"


@case("冻结 20 帧 → 必须报卡顿")
def _():
    f = synth(120, drift=1.2)
    for i in range(40, 60):
        f[i] = f[39].copy()
    lumas, diffs = metrics(f)
    assert detect_stutter(diffs, np.median(diffs[1:])), "冻结没被抓到"


@case("每帧亮度抖动 ±25 → 必须报闪烁")
def _():
    f = synth(90, base=40)
    f = [np.clip(x.astype(np.int16) + (25 if i % 2 else -25), 0, 255).astype(np.uint8)
         for i, x in enumerate(f)]
    lumas, _ = metrics(f)
    assert detect_flicker(lumas), "闪烁没被抓到"


@case("稳定亮度 → 不该报闪烁")
def _():
    f = synth(90, base=60, noise=2)
    lumas, _ = metrics(f)
    assert not detect_flicker(lumas), "稳定画面误报闪烁"


@case("10 帧全黑 → 必须报黑场")
def _():
    f = synth(60, base=5, noise=1)
    lumas, _ = metrics(f)
    assert detect_black(lumas), "黑场没被抓到"


@case("正常曝光 → 不该报黑场")
def _():
    f = synth(60, base=45, noise=2)
    lumas, _ = metrics(f)
    assert not detect_black(lumas), "正常画面误报黑场"


@case("镜头时长全相同 → 必须报节奏塌方")
def _():
    assert detect_pacing([6] * 20), "均匀节奏没被抓到"


@case("镜头长短交错 → 不该报节奏")
def _():
    assert not detect_pacing([3, 9, 4, 12, 3, 8, 5, 11]), "正常节奏误报"


@case("plan 哈希：改字幕触发重渲，改标题不触发")
def _():
    from io import StringIO
    import json
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "planmod", os.path.join(os.path.dirname(HERE), "io", "plan.py"))
    P = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(P)

    import tempfile
    tmp = tempfile.mkdtemp()
    edl = {"meta": {"duration": 2, "fps": 30, "resolution": [1920, 1080]},
           "moods": {"a": {"hue": 30}},
           "acts": [{"id": "a1", "t0": 0, "t1": 2, "mood": "a"}],
           "shots": [{"id": "s1", "act": "a1", "t0": 0, "t1": 1, "asset": None,
                      "texts": [{"tier": "T1", "t": 0.2, "lines": ["甲"]}]},
                     {"id": "s2", "act": "a1", "t0": 1, "t1": 2, "asset": None,
                      "texts": []}]}
    p1 = P.build_plan(edl, tmp)
    edl["meta"]["title"] = "改了标题"
    p2 = P.build_plan(edl, tmp)
    assert [s["hash"] for s in p1["shots"]] == [s["hash"] for s in p2["shots"]], "改标题不该变哈希"

    edl["shots"][0]["texts"][0]["lines"] = ["乙"]
    p3 = P.build_plan(edl, tmp)
    assert p3["shots"][0]["hash"] != p1["shots"][0]["hash"], "改字幕必须变哈希"
    assert p3["shots"][1]["hash"] == p1["shots"][1]["hash"], "未改镜头不该变"


def main():
    ok = 0
    for name, fn in CASES:
        try:
            fn()
            print(f"  [ok]   {name}")
            ok += 1
        except AssertionError as e:
            print(f"  [FAIL] {name}  ← {e}")
        except Exception as e:
            print(f"  [ERR]  {name}  ← {type(e).__name__}: {e}")
    print(f"\n{ok}/{len(CASES)} 通过")
    sys.exit(0 if ok == len(CASES) else 1)


if __name__ == "__main__":
    main()
