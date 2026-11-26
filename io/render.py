#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
io/render.py — 增量 + 并行渲染调度

两件事：
  1. 增量：只重渲「镜头定义变了」或「帧文件缺失」的帧
  2. 并行：把待渲帧切成 N 段，起 N 个浏览器实例同时渲

    python io/render.py --edl examples/demo-europa.json --html out/x.html \
        --frames out/frames_x --out out/x.mp4 --workers 3

    加 --force 全量重渲；加 --no-encode 只渲帧。
"""
import argparse
import json
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import plan as P  # noqa: E402

CAPTURE = os.path.join(HERE, "capture.py")


def chunks(seq, n):
    if n <= 1:
        return [seq]
    k, m = divmod(len(seq), n)
    out, i = [], 0
    for w in range(n):
        size = k + (1 if w < m else 0)
        out.append(seq[i:i + size])
        i += size
    return [c for c in out if c]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--edl", required=True)
    ap.add_argument("--html", required=True)
    ap.add_argument("--frames", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--workers", type=int, default=3)
    ap.add_argument("--base-port", type=int, default=9410)
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--no-encode", action="store_true")
    ap.add_argument("--fps", type=int, default=None)
    ap.add_argument("--duration", type=float, default=None)
    a = ap.parse_args()

    edl = json.load(open(a.edl, encoding="utf-8"))
    fps = a.fps or edl["meta"].get("fps", 30)
    dur = a.duration or edl["meta"]["duration"]
    os.makedirs(a.frames, exist_ok=True)
    plan_path = os.path.join(a.frames, "..", f"render_plan_{os.path.basename(a.frames)}.json")
    plan_path = os.path.abspath(plan_path)

    prev = P.load_prev_plan(plan_path)
    plan = P.build_plan(edl, a.frames)
    changed, note = P.diff_plans(prev, plan)
    if prev and not a.force:
        plan = P.apply_diff(plan, prev, changed)

    todo = plan["dirty_frames"] if not a.force else list(range(plan["total"]))
    if a.force:
        changed = [s["id"] for s in plan["shots"]]

    print(f"总帧 {plan['total']}  已有 {plan['have']}  待渲 {len(todo)}")
    if changed:
        print(f"内容变更镜头: {', '.join(changed[:12])}" + (" …" if len(changed) > 12 else ""))
    elif prev:
        print("没有内容变更")

    if todo:
        removed = 0
        for i in todo:
            p = os.path.join(a.frames, f"{i:05d}.jpg")
            if os.path.exists(p):
                try:
                    os.remove(p)
                    removed += 1
                except OSError:
                    pass
        print(f"清掉旧帧 {removed} 张")

    if not todo:
        print("无需渲染，直接编码")
    else:
        # 并行分段
        parts = chunks(todo, max(1, a.workers))
        tmpdir = os.path.join(os.environ.get("TEMP", "."), "rchunks_%d" % os.getpid())
        os.makedirs(tmpdir, exist_ok=True)

        procs = []
        t_start = time.time()
        for w, part in enumerate(parts):
            listfile = os.path.join(tmpdir, f"frames_{w}.txt")
            open(listfile, "w").write("\n".join(str(i) for i in part))
            cmd = [sys.executable, CAPTURE,
                   "--html", a.html, "--duration", str(dur), "--fps", str(fps),
                   "--frames", a.frames, "--only", listfile,
                   "--port", str(a.base_port + w), "--no-encode"]
            procs.append((w, len(part), subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                encoding="utf-8", errors="replace")))

        print(f"并行渲染：{len(parts)} 个实例，{len(todo)} 帧")
        for w, n, pr in procs:
            out, _ = pr.communicate()
            tail = [ln for ln in out.strip().splitlines() if ln.strip()]
            last = tail[-1] if tail else ""
            safe = last.encode("ascii", "ignore").decode("ascii").strip()
            print(f"  worker{w}  {n:5d} frames  rc={pr.returncode}  {safe[:70]}")

        dt = time.time() - t_start
        print(f"渲染用时 {dt:.0f}s（{dt/max(1,len(todo))*1000:.0f} ms/帧，均摊到 {len(parts)} 实例）")

    # 写计划留档
    json.dump({"plan": plan, "changed": changed},
              open(plan_path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    if a.no_encode:
        print("跳过编码")
        return

    # 编码（全片所有帧）
    ff = os.path.join(os.environ.get("TEMP", "."), f"enc_{os.getpid()}.mp4")
    import cv2
    import numpy as np
    import glob
    have = sorted(glob.glob(os.path.join(a.frames, "*.jpg")))
    if not have:
        sys.exit("没有帧可编码")
    first = cv2.imdecode(np.fromfile(have[0], dtype=np.uint8), cv2.IMREAD_COLOR)
    H, W = first.shape[:2]
    vw = cv2.VideoWriter(ff, cv2.VideoWriter_fourcc(*"mp4v"), fps, (W, H))
    for p in have:
        img = cv2.imdecode(np.fromfile(p, dtype=np.uint8), cv2.IMREAD_COLOR)
        if img is None:
            continue
        if img.shape[:2] != (H, W):
            img = cv2.resize(img, (W, H))
        vw.write(img)
    vw.release()
    import shutil
    shutil.move(ff, a.out)
    print(f"编码完成 {len(have)} 帧 → {a.out}  {os.path.getsize(a.out)/1024/1024:.1f} MB")


if __name__ == "__main__":
    main()
