#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
io/plan.py — 渲染计划与增量检测

渲染器是纯函数：第 i 帧只由 t=i/fps 决定。所以「改了哪些镜头」就等于
「要重渲哪些帧」。这里用镜头定义的哈希来判断改动。

    plan = build_plan(edl, frames_dir)
    # → {"total": 5400, "shots": [...], "dirty": [...], "dirty_frames": [...]}
"""
import glob
import hashlib
import json
import os


def _hash(obj):
    return hashlib.sha1(
        json.dumps(obj, sort_keys=True, ensure_ascii=False).encode("utf-8")
    ).hexdigest()[:16]


def build_plan(edl, frames_dir):
    """生成计划：每个镜头覆盖的帧区间 + 内容哈希 + 是否需要重渲"""
    fps = edl["meta"].get("fps", 30)
    total = int(round(edl["meta"]["duration"] * fps))

    # 影响全片的公共参数（调色表、分辨率）变了就要全渲
    global_sig = _hash({
        "moods": edl.get("moods"),
        "res": edl["meta"].get("resolution"),
        "fps": fps,
    })

    shots = []
    for s in edl["shots"]:
        f0 = int(round(s["t0"] * fps))
        f1 = int(round(s["t1"] * fps))
        # 只把真正影响画面的字段纳入哈希
        sig = _hash({
            "g": global_sig,
            "asset": s.get("asset"),
            "motion": s.get("motion"),
            "optics": s.get("optics"),
            "grade": s.get("grade"),
            "brightness": s.get("brightness"),
            "camera": s.get("camera"),
            "texts": s.get("texts"),
            "graphics": s.get("graphics"),
        })
        shots.append({"id": s["id"], "f0": f0, "f1": f1, "hash": sig})

    have = set(os.path.basename(p) for p in
               glob.glob(os.path.join(frames_dir, "*.jpg")) +
               glob.glob(os.path.join(frames_dir, "*.png")))

    dirty, dirty_frames, missing = [], [], []
    for sh in shots:
        idxs = list(range(sh["f0"], sh["f1"]))
        absent = [i for i in idxs if f"{i:05d}.jpg" not in have]
        reason = []
        if absent:
            reason.append(f"缺帧 {len(absent)}")
        dirty_frames.extend(absent)
        sh["missing"] = len(absent)
        if absent:
            dirty.append({"id": sh["id"], "reason": " / ".join(reason)})

    # 帧数不够（片尾被截断）也算缺
    for i in range(total):
        if f"{i:05d}.jpg" not in have and i not in dirty_frames:
            dirty_frames.append(i)

    return {
        "total": total,
        "fps": fps,
        "shots": shots,
        "dirty": dirty,
        "dirty_frames": sorted(set(dirty_frames)),
        "have": len(have),
    }


def load_prev_plan(path):
    if os.path.exists(path):
        try:
            data = json.load(open(path, encoding="utf-8"))
            return data.get("plan", data)
        except Exception:
            return None
    return None


def diff_plans(prev, cur):
    """比较两次计划，返回内容变了的镜头（哈希不同）"""
    if not prev:
        return [s["id"] for s in cur["shots"]], ["首次渲染"]
    old = {s["id"]: s for s in prev.get("shots", [])}
    changed = []
    for s in cur["shots"]:
        o = old.get(s["id"])
        if not o or o["hash"] != s["hash"] or o["f0"] != s["f0"] or o["f1"] != s["f1"]:
            changed.append(s["id"])
    return changed, []


def apply_diff(plan, prev, changed_ids):
    """把内容变化导致的帧也加入待渲列表"""
    if not changed_ids:
        return plan
    frames = set(plan["dirty_frames"])
    reasons = {d["id"]: d["reason"] for d in plan["dirty"]}
    for sh in plan["shots"]:
        if sh["id"] in changed_ids:
            frames.update(range(sh["f0"], sh["f1"]))
            reasons[sh["id"]] = "内容变更"
    plan["dirty_frames"] = sorted(frames)
    plan["dirty"] = [{"id": k, "reason": v} for k, v in reasons.items()]
    return plan
