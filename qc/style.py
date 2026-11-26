#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
qc/style.py — 风格质检（渲后 / 渲前都能跑）

lint 管结构和语法，preview 管排版和对比度，
style 管「好不好看」里能自动化的那部分：

  1. 饱和度超标（会把素材染成荧光色——伽利略第三幕踩过这个坑）
  2. 幕内亮度不一致（同一幕里镜头忽明忽暗）
  3. 色相跨度不足（整片一个颜色，没有叙事推进）
  4. 纯图形镜头太暗（没有素材托底时会黑成一片）
  5. 连续三镜同一构图（kenburns 方向相同 → 看着像没换镜）

用法:
    python qc/style.py examples/galileo.json            # 只查 EDL
    python qc/style.py examples/galileo.json out/frames  # 连成片一起查
"""
import argparse
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

# 阈值
SAT_MAX = 0.62          # 平均饱和度上限（超过说明调色过猛）
DROP_MAX = 18.0         # 幕内亮度极差上限
HUE_SPAN_MIN = 45       # 幕间色相跨度下限（度）
GRAPHIC_LUMA_MIN = 18   # 纯图形镜头平均亮度下限
KENBURNS_RUN = 3        # 连续同向推拉镜头上限


def read_frames(path):
    """读帧目录里每镜中间时刻的帧，返回 (亮度, 饱和度, 色相) 列表"""
    import cv2
    edl = json.load(open(os.path.join(ROOT, "examples", os.path.basename(path)),
                         encoding="utf-8")) if path.endswith(".json") else None
    return edl


def analyze_frame(p):
    import cv2
    im = cv2.imdecode(np.fromfile(p, dtype=np.uint8), cv2.IMREAD_COLOR)
    if im is None:
        return None
    hsv = cv2.cvtColor(im, cv2.COLOR_BGR2HSV)
    luma = float(cv2.cvtColor(im, cv2.COLOR_BGR2GRAY).mean())
    sat = float(hsv[..., 1].mean() / 255.0)
    # 色相：只统计饱和度足够高的像素
    m = hsv[..., 1] > 60
    hue = float(np.median(hsv[..., 0][m])) * 2.0 if m.sum() > 500 else 0.0
    return luma, sat, hue


def check_edl(edl):
    warns = []
    shots = edl["shots"]
    acts = {a["id"]: a for a in edl["acts"]}

    # 1) 纯图形镜头亮度
    for s in shots:
        if s.get("asset") is None and s.get("brightness", 1.0) < 1.4:
            warns.append(f"{s['id']}: 纯图形镜头 brightness={s.get('brightness', 1.0)}，"
                         f"建议 ≥1.7，否则会偏黑")

    # 2) 镜头时长与幕的归属
    for s in shots:
        a = acts.get(s.get("act"))
        if not a:
            warns.append(f"{s['id']}: 幕 {s.get('act')} 不存在")
        elif not (a["t0"] - 0.01 <= s["t0"] and s["t1"] <= a["t1"] + 0.01):
            warns.append(f"{s['id']}: 时间 {s['t0']}-{s['t1']} 超出幕 {a['id']} "
                         f"({a['t0']}-{a['t1']})")

    # 3) 连续同向推拉
    run, prev = 1, None
    for s in shots:
        z = (s.get("motion") or {}).get("zoom")
        sign = None if not z else ("in" if z > 0 else "out")
        if sign and sign == prev:
            run += 1
            if run > KENBURNS_RUN:
                warns.append(f"{s['id']}: 连续 {run} 镜同向推拉，观感单调")
        else:
            run = 1
        prev = sign

    # 4) 幕间色相跨度
    if len(acts) > 1:
        # 用各幕 mood 的 hue 近似（EDL 里有 moods 表就用它）
        moods = edl.get("moods") or {}
        hues = [moods[a["mood"]]["hue"] for a in edl["acts"]
                if a.get("mood") in moods and "hue" in moods[a["mood"]]]
        if len(hues) > 1:
            span = max(hues) - min(hues)
            if span < HUE_SPAN_MIN:
                warns.append(f"幕间色相跨度只有 {span:.0f}°，叙事色彩区分不足")
    return warns


def check_frames(edl, fdir):
    """逐镜检查：平均饱和度、幕内亮度极差、幕间色相"""
    files = sorted(os.listdir(fdir))
    files = [f for f in files if f.lower().endswith((".jpg", ".png"))]
    if not files:
        return ["帧目录为空"], {}

    rows = []
    for s in edl["shots"]:
        t = (s["t0"] + s["t1"]) / 2
        idx = min(int(t * edl["meta"].get("fps", 30)), len(files) - 1)
        r = analyze_frame(os.path.join(fdir, files[idx]))
        if r:
            rows.append((s["id"], s["act"], *r))

    warns = []
    # 饱和度
    for sid, act, luma, sat, hue in rows:
        if sat > SAT_MAX:
            warns.append(f"{sid}: 饱和度 {sat:.2f} > {SAT_MAX}，素材可能被染成荧光色")
    # 幕内亮度极差
    by_act = {}
    for sid, act, luma, sat, hue in rows:
        by_act.setdefault(act, []).append((sid, luma))
    for act, items in by_act.items():
        if len(items) < 2:
            continue
        lo = min(i[1] for i in items)
        hi = max(i[1] for i in items)
        if hi - lo > DROP_MAX:
            warns.append(f"幕 {act}: 亮度极差 {hi - lo:.0f}（{lo:.0f}–{hi:.0f}），同幕内忽明忽暗")
    # 幕间色相
    act_hue = {}
    for sid, act, luma, sat, hue in rows:
        if hue:
            act_hue.setdefault(act, []).append(hue)
    if len(act_hue) > 1:
        med = [float(np.median(v)) for v in act_hue.values()]
        span = max(med) - min(med)
        # 色相是环形，取最小角距
        span = min(span, 360 - span)
        if span < HUE_SPAN_MIN:
            warns.append(f"幕间实测色相跨度只有 {span:.0f}°，色彩推进不足")

    stats = {"shots": len(rows),
             "luma": [round(r[2], 1) for r in rows],
             "sat": [round(r[3], 2) for r in rows]}
    return warns, stats


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("edl")
    ap.add_argument("frames", nargs="?", default=None)
    a = ap.parse_args()

    edl = json.load(open(a.edl, encoding="utf-8"))
    warns = check_edl(edl)

    if a.frames:
        fw, stats = check_frames(edl, a.frames)
        warns += fw
        if stats.get("luma"):
            print(f"逐镜亮度: {stats['luma']}")
            print(f"逐镜饱和: {stats['sat']}")

    if warns:
        print(f"\n风格问题 {len(warns)} 条:")
        for w in warns:
            print("  [!]", w)
        sys.exit(1)
    print(f"\n风格质检通过：{len(edl['shots'])} 镜")


if __name__ == "__main__":
    main()
