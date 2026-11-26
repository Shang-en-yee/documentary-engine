#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
compare.py — 按幕统计成片指标，并与参考基线对照

    python compare.py examples/voyager.json out/frames_voyager

输出每个 act 的：帧间差、运动帧占比、覆盖率、亮度，
以及全片汇总和参考片基线（来自 04-参考片拆解 的实测值）。

基线（参考片《1859-2026》234s@2x，同一套算法）：
    frame_diff 2.29 | moving 0.774 | coverage 0.381 | luma 31.7
但参考片含大量实拍/档案素材，纯程序图形片段的自然亮度更低，
所以亮度只作参考，不作硬指标。
"""
import json, os, sys, glob
import cv2
import numpy as np

REF = {"frame_diff": 2.29, "moving": 0.774, "coverage": 0.381, "luma": 31.7}


def imread_u(p):
    return cv2.imdecode(np.fromfile(p, dtype=np.uint8), cv2.IMREAD_COLOR)


def metrics(frames):
    prev = None
    d, lum, cov = [], [], []
    for i, f in enumerate(frames):
        im = imread_u(f)
        if im is None:
            continue
        g = cv2.cvtColor(cv2.resize(im, (640, 360)), cv2.COLOR_BGR2GRAY).astype(np.float32)
        lum.append(float(g.mean()))
        if prev is not None:
            d.append(float(np.abs(g - prev).mean()))
        prev = g
        if i % 15 == 0:
            g2 = cv2.cvtColor(im, cv2.COLOR_BGR2GRAY).astype(np.float32)
            k = np.ones((15, 15), np.float32) / 225
            m = cv2.filter2D(g2, -1, k)
            v = cv2.filter2D(g2 * g2, -1, k) - m * m
            sd = np.sqrt(np.maximum(v, 0))
            cov.append(float(((sd > 2.5) | ((g2 - m) > 6)).mean()))
    if not d:
        return None
    d = np.array(d)
    return {
        "frame_diff": round(float(d.mean()), 2),
        "moving": round(float((d > 0.4).mean()), 3),
        "coverage": round(float(np.mean(cov)), 3),
        "luma": round(float(np.mean(lum)), 1),
    }


def main():
    if len(sys.argv) < 3:
        sys.exit("用法: python compare.py film.json frames_dir")
    edl_path, fdir = sys.argv[1], sys.argv[2]
    edl = json.load(open(edl_path, encoding="utf-8"))
    fps = edl["meta"]["fps"]
    files = sorted(glob.glob(os.path.join(fdir, "*.jpg")) + glob.glob(os.path.join(fdir, "*.png")))

    print(f"素材: {len(files)} 帧 / {len(files)/fps:.1f}s")
    print("-" * 74)
    print(f"{'幕':<8}{'帧数':>6}{'frame_diff':>12}{'moving':>9}{'coverage':>10}{'luma':>7}")
    print("-" * 74)

    allm = []
    for act in edl["acts"]:
        a = int(act["t0"] * fps)
        b = int(act["t1"] * fps)
        sub = files[a:b]
        m = metrics(sub)
        if not m:
            continue
        allm.append(m)
        print(f"{act.get('title','?'):<8}{len(sub):>6}{m['frame_diff']:>12.2f}"
              f"{m['moving']:>9.2f}{m['coverage']:>10.3f}{m['luma']:>7.1f}")

    print("-" * 74)
    if allm:
        avg = {k: round(float(np.mean([m[k] for m in allm])), 2) for k in allm[0]}
        print(f"{'全片':<8}{len(files):>6}{avg['frame_diff']:>12.2f}"
              f"{avg['moving']:>9.2f}{avg['coverage']:>10.3f}{avg['luma']:>7.1f}")
    print(f"{'参考片':<8}{'—':>6}{REF['frame_diff']:>12.2f}"
          f"{REF['moving']:>9.3f}{REF['coverage']:>10.3f}{REF['luma']:>7.1f}")


if __name__ == "__main__":
    main()
