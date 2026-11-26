#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
film.py — 主控（总导演）

一句话：把「写分镜 → 校验 → 预览 → 渲染 → 配乐 → 成片」串成一条命令。

    python film.py new 我的片子                  # 建骨架
    python film.py check examples/galileo.json   # 结构 + 风格
    python film.py preview examples/galileo.json # 渲前质检（30 秒）
    python film.py render examples/galileo.json  # 全片渲染
    python film.py all examples/galileo.json     # 一路到成片

各环节失败即停，不浪费后面的时间。
"""
import argparse
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PY = sys.executable
QC = os.path.join(HERE, "qc")
IO = os.path.join(HERE, "io")
OUT = os.path.join(HERE, "out")


def run(name, args, allow_fail=False, cwd=None):
    print(f"\n=== {name} " + "=" * max(0, 56 - len(name)), flush=True)
    r = subprocess.run([PY] + args, cwd=cwd or HERE)
    if r.returncode != 0 and not allow_fail:
        print(f"\n[{name}] 失败，中止")
        sys.exit(r.returncode)
    return r.returncode


def load(edl):
    return json.load(open(edl, encoding="utf-8"))


# ---------------------------------------------------------------- 命令

def cmd_new(path):
    if os.path.exists(path):
        sys.exit(f"已存在: {path}")
    edl = {
        "version": "1.0",
        "meta": {"title": os.path.splitext(os.path.basename(path))[0],
                 "duration": 0, "fps": 30, "resolution": [1920, 1080],
                 "language": "zh-CN"},
        "assets": [],
        "moods": {
            "amber": {"lift": [0.06, 0.03, -0.02], "tint": [0.10, 0.04, -0.04],
                      "sat": 0.92, "hue": 30},
            "steel": {"lift": [0.0, 0.01, 0.04], "tint": [-0.04, 0.01, 0.08],
                      "sat": 0.78, "hue": 215},
            "jade":  {"lift": [0.0, 0.02, 0.01], "tint": [-0.03, 0.05, 0.02],
                      "sat": 0.94, "hue": 150},
            "deep":  {"lift": [-0.02, 0.0, 0.04], "tint": [-0.03, 0.02, 0.10],
                      "sat": 0.72, "hue": 225},
        },
        "acts": [{"id": "a1", "t0": 0, "t1": 0, "mood": "amber", "title": "第一幕"}],
        "shots": [],
        "audio": {"envelope": []},
        "credits": {"attribution": []},
    }
    os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)
    json.dump(edl, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"已建骨架: {path}")
    print("下一步: 用 director.shots 里的镜头原型往里加镜头")


def cmd_draft(script, out, duration):
    args = [os.path.join(HERE, "director", "draft.py"), script]
    if out:
        args += ["--out", out]
    if duration:
        args += ["--duration", str(duration)]
    run("draft", args)


def cmd_check(edl):
    run("lint", [os.path.join(QC, "lint.py"), edl])
    run("style", [os.path.join(QC, "style.py"), edl], allow_fail=True)


def cmd_preview(edl, per_shot):
    rc = run("lint", [os.path.join(QC, "lint.py"), edl])
    run("preview", [os.path.join(QC, "preview.py"), edl, "--per-shot", str(per_shot)],
        allow_fail=False)


def cmd_render(edl, out_name):
    os.makedirs(OUT, exist_ok=True)
    stem = os.path.splitext(os.path.basename(edl))[0]
    page = os.path.join(OUT, f"{stem}.html")
    run("build", [os.path.join(IO, "build.py"), edl, page])

    meta = load(edl)["meta"]
    frames = os.path.join(OUT, f"frames_{stem}")
    silent = os.path.join(OUT, f"{stem}-silent.mp4")
    dur = meta["duration"]
    fps = meta.get("fps", 30)
    workers = os.environ.get("FILM_WORKERS", "3")
    cmd = [os.path.join(IO, "render.py"),
           "--edl", edl, "--html", page, "--frames", frames, "--out", silent,
           "--workers", workers, "--fps", str(fps), "--duration", str(dur)]
    if os.environ.get("FILM_FORCE"):
        cmd.append("--force")
    run("render", cmd)
    return silent, frames


def cmd_score(edl, silent):
    d = load(edl)
    track = ((d.get("audio") or {}).get("track") or {})
    if not track.get("src"):
        print("\n没有配乐曲目，跳过")
        return None
    stem = os.path.splitext(os.path.basename(edl))[0]
    src = track["src"]
    if not os.path.isabs(src):
        src = os.path.join(HERE, src)
    wav = os.path.join(OUT, f"score-{stem}.wav")
    run("score", [os.path.join(IO, "score.py"),
                  "--track", src,
                  "--track-start", str(track.get("track_start", 0)),
                  "--duration", str(d["meta"]["duration"]),
                  "--edl", edl, "--out", wav,
                  "--gain", str(track.get("gain", 2.6))])
    return wav


def cmd_encode(silent, wav, out, gamma=0.93):
    import subprocess as sp
    FF = r"C:\Users\bx\AppData\Roaming\Seewo\EasiNote5\Dependencies\FFmpeg\FFmpeg_2\ffmpeg.exe"
    print(f"\n=== encode " + "=" * 48)
    args = [FF, "-y", "-hide_banner", "-loglevel", "error", "-i", silent]
    if wav:
        args += ["-i", wav]
    args += ["-vf", f"eq=gamma={gamma}:contrast=1.03",
             "-c:v", "libx264", "-crf", "23", "-preset", "medium",
             "-pix_fmt", "yuv420p"]
    if wav:
        args += ["-c:a", "aac", "-b:a", "192k", "-af", "alimiter=limit=0.95", "-shortest"]
    args += ["-movflags", "+faststart", out]
    sp.run(args, check=True)
    mb = os.path.getsize(out) / 1024 / 1024
    print(f"成片: {out}  {mb:.1f} MB")


# ---------------------------------------------------------------- 入口

def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("new"); p.add_argument("path")
    p = sub.add_parser("draft"); p.add_argument("script")
    p.add_argument("--out", default=None); p.add_argument("--duration", type=float, default=None)
    p = sub.add_parser("check"); p.add_argument("edl")
    p = sub.add_parser("preview"); p.add_argument("edl")
    p.add_argument("--per-shot", type=int, default=2)
    p = sub.add_parser("render"); p.add_argument("edl"); p.add_argument("--out", default=None)
    p = sub.add_parser("video"); p.add_argument("edl"); p.add_argument("source")
    p = sub.add_parser("selftest")
    p = sub.add_parser("deliver"); p.add_argument("edl"); p.add_argument("video")
    p.add_argument("--outdir", default=None); p.add_argument("--cover-at", type=float, default=None)
    p = sub.add_parser("all"); p.add_argument("edl"); p.add_argument("--out", default=None)

    a = ap.parse_args()
    if a.cmd == "new":
        cmd_new(a.path); return
    if a.cmd == "draft":
        cmd_draft(a.script, a.out, a.duration); return
    if a.cmd == "check":
        cmd_check(a.edl); return
    if a.cmd == "video":
        run("video-qc", [os.path.join(QC, "video.py"), a.edl, a.source]); return
    if a.cmd == "deliver":
        args = [os.path.join(IO, "deliver.py"), "--edl", a.edl, "--video", a.video]
        if a.outdir: args += ["--outdir", a.outdir]
        if a.cover_at: args += ["--cover-at", str(a.cover_at)]
        run("deliver", args); return
    if a.cmd == "selftest":
        run("selftest", [os.path.join(QC, "selftest.py")]); return
    if a.cmd == "preview":
        cmd_preview(a.edl, a.per_shot); return

    stem = os.path.splitext(os.path.basename(a.edl))[0]
    final = a.out or os.path.join(OUT, f"{stem}-final.mp4")
    if a.cmd == "render":
        cmd_render(a.edl, stem); return

    # all
    cmd_preview(a.edl, 2)
    silent, frames = cmd_render(a.edl, stem)
    wav = cmd_score(a.edl, silent)
    cmd_encode(silent, wav, final)
    run("deliver", [os.path.join(IO, "deliver.py"), "--edl", a.edl,
                    "--video", final, "--outdir", os.path.join(OUT, "deliver")],
        allow_fail=True)
    run("video-qc", [os.path.join(QC, "video.py"), a.edl, final], allow_fail=True)
    run("compare", [os.path.join(QC, "compare.py"), a.edl, frames], allow_fail=True)
    print(f"\n完成: {final}")


if __name__ == "__main__":
    main()
