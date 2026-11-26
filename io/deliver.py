#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
io/deliver.py — 交付层：字幕 / 封面 / 元数据 / 章节

成片之外，平台还需要四样东西：

  1. SRT 字幕（累积式字幕要按"这一句出现时画面上有哪些字"来导）
  2. 封面图（可指定取帧时间，叠加标题）
  3. 元数据 JSON（标题、时长、章节、素材授权清单）
  4. 章节时间点（B站/YouTube 的分P或章节）

用法:
    python io/deliver.py --edl examples/x.json --video out/x-final.mp4 \
        --outdir out/deliver --cover-at 145
"""
import argparse
import json
import os
import subprocess
import sys

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
FF = r"C:\Users\bx\AppData\Roaming\Seewo\EasiNote5\Dependencies\FFmpeg\FFmpeg_2\ffmpeg.exe"

FONT_CANDIDATES = [
    r"C:\Windows\Fonts\msyh.ttc",
    r"C:\Windows\Fonts\msyhbd.ttc",
    r"C:\Windows\Fonts\simhei.ttf",
]


def srt_time(t):
    h = int(t // 3600)
    m = int((t % 3600) // 60)
    s = t % 60
    return f"{h:02d}:{m:02d}:{s:06.3f}".replace(".", ",")


def build_srt(edl):
    """按镜头把字幕事件展开成 SRT；累积式字幕导出「当时画面上的全部文字」"""
    cues = []
    for sh in edl["shots"]:
        texts = sorted(sh.get("texts") or [], key=lambda x: x.get("t", 0))
        if not texts:
            continue
        # 分组：同 tier 视为一组，累积显示
        for i, tx in enumerate(texts):
            tier = tx.get("tier")
            if tier not in ("T1", "T2"):
                continue
            start = sh["t0"] + tx.get("t", 0)
            # 结束时间 = 同组下一条字幕的出现时间，或镜头结束
            later = [x["t"] for x in texts
                     if x.get("tier") == tier and x.get("t", 0) > tx.get("t", 0)]
            end = sh["t0"] + (min(later) if later else (sh["t1"] - sh["t0"]))
            # 累积：把本组在 start 之前出现过的句子都带上
            shown = [x for x in texts
                     if x.get("tier") == tier and x.get("t", 0) <= tx.get("t", 0)]
            lines = []
            for x in shown:
                lines.extend(x.get("lines") or [])
            if not lines:
                continue
            cues.append((start, max(end, start + 0.4), "\n".join(lines)))

    cues.sort()
    out = []
    for i, (a, b, txt) in enumerate(cues, 1):
        out.append(f"{i}\n{srt_time(a)} --> {srt_time(b)}\n{txt}\n")
    return "\n".join(out)


def crop_letterbox(img):
    """去掉上下黑边（B站封面 16:9 更好用）"""
    g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    rows = np.where(g.mean(axis=1) > 8)[0]
    if len(rows) < 10:
        return img
    return img[rows.min():rows.max() + 1]


def cover_from_asset(src, title, out_path, size=(1920, 1080)):
    """用素材原图做封面：干净、无字幕、留出标题空间"""
    path = src if os.path.isabs(src) else os.path.join(ROOT, src)
    im = cv2.imdecode(np.fromfile(path, dtype=np.uint8), cv2.IMREAD_COLOR)
    if im is None:
        return False
    H, W = im.shape[:2]
    target = size[0] / size[1]
    if W / H > target:                      # 太宽 → 裁两侧
        nw = int(H * target)
        im = im[:, (W - nw) // 2:(W - nw) // 2 + nw]
    else:                                    # 太高 → 裁上下
        nh = int(W / target)
        im = im[(H - nh) // 2:(H - nh) // 2 + nh]
    img = Image.fromarray(cv2.cvtColor(im, cv2.COLOR_BGR2RGB)).resize(size, Image.LANCZOS)
    return _stamp(img, title, out_path)


def _stamp(img, title, out_path):
    W, H = img.size
    draw = ImageDraw.Draw(img, "RGBA")
    for y in range(int(H * 0.58), H):
        a = int(165 * (y - H * 0.58) / (H * 0.42))
        draw.rectangle([0, y, W, y + 1], fill=(0, 0, 0, a))
    fsize = max(56, int(W * 0.048))
    font = None
    for p in FONT_CANDIDATES:
        if os.path.exists(p):
            font = ImageFont.truetype(p, fsize)
            break
    if font is None:
        font = ImageFont.load_default()
    x, y = int(W * 0.055), int(H * 0.775)
    draw.text((x + 4, y + 4), title, font=font, fill=(0, 0, 0, 160))
    draw.text((x, y), title, font=font, fill=(242, 230, 202, 255))
    img.save(out_path, quality=92)
    small = os.path.splitext(out_path)[0] + "-1146.jpg"
    img.resize((1146, 645), Image.LANCZOS).save(small, quality=92)
    return True


def make_cover(video, t, title, out_path, size=(1920, 1080)):
    tmp = os.path.join(os.environ.get("TEMP", "."), "cover_%d.png" % os.getpid())
    subprocess.run([FF, "-y", "-hide_banner", "-loglevel", "error",
                    "-ss", str(t), "-i", video, "-frames:v", "1", tmp], check=True)
    im = cv2.imdecode(np.fromfile(tmp, dtype=np.uint8), cv2.IMREAD_COLOR)
    os.remove(tmp)
    if im is None:
        return False
    img = Image.fromarray(cv2.cvtColor(im, cv2.COLOR_BGR2RGB))
    img = img.resize(size, Image.LANCZOS)

    draw = ImageDraw.Draw(img, "RGBA")
    # 底部渐变压暗，保证标题可读
    W, H = img.size
    for y in range(int(H * 0.62), H):
        a = int(150 * (y - H * 0.62) / (H * 0.38))
        draw.rectangle([0, y, W, y + 1], fill=(0, 0, 0, a))

    fsize = max(48, int(W * 0.045))
    font = None
    for p in FONT_CANDIDATES:
        if os.path.exists(p):
            font = ImageFont.truetype(p, fsize)
            break
    if font is None:
        font = ImageFont.load_default()
    x, y = int(W * 0.06), int(H * 0.76)
    draw.text((x + 3, y + 3), title, font=font, fill=(0, 0, 0, 170))
    draw.text((x, y), title, font=font, fill=(240, 228, 200, 255))

    img.save(out_path, quality=92)
    # 再存一份平台常用尺寸
    small = os.path.splitext(out_path)[0] + "-1146.jpg"
    img.resize((1146, 645), Image.LANCZOS).save(small, quality=92)
    return True


def build_meta(edl, srt_name, cover_name):
    d = edl["meta"].get("duration", 0)
    chapters = []
    for a in edl.get("acts", []):
        chapters.append({"title": a.get("title", a["id"]),
                         "start": round(a["t0"], 1)})
    assets = [{"id": a["id"], "caption": a.get("caption", ""),
               "license": a.get("license"), "source": a.get("source_url")}
              for a in edl.get("assets", [])]
    track = (edl.get("audio") or {}).get("track") or {}
    return {
        "title": edl["meta"].get("title", ""),
        "subtitle": edl["meta"].get("subtitle", ""),
        "duration_sec": d,
        "duration": f"{int(d//60)}:{int(d%60):02d}",
        "resolution": edl["meta"].get("resolution", [1920, 1080]),
        "fps": edl["meta"].get("fps", 30),
        "chapters": chapters,
        "subtitles": srt_name,
        "cover": cover_name,
        "music": {"title": track.get("title"), "author": track.get("author"),
                  "license": track.get("license")} if track else None,
        "credits": (edl.get("credits") or {}).get("attribution", []),
        "assets": assets,
        "shots": len(edl["shots"]),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--edl", required=True)
    ap.add_argument("--video", required=True)
    ap.add_argument("--outdir", default=None)
    ap.add_argument("--cover-at", type=float, default=None,
                    help="封面取帧时间（秒），默认取最亮的一镜中点")
    a = ap.parse_args()

    edl = json.load(open(a.edl, encoding="utf-8"))
    stem = os.path.splitext(os.path.basename(a.video))[0]
    outdir = a.outdir or os.path.join(ROOT, "out", "deliver")
    os.makedirs(outdir, exist_ok=True)

    # 1) SRT
    srt = build_srt(edl)
    srt_path = os.path.join(outdir, f"{stem}.srt")
    open(srt_path, "w", encoding="utf-8").write(srt)
    n_cues = srt.count("-->")
    print(f"字幕 {n_cues} 条 → {srt_path}")

    # 2) 封面
    cover_at = a.cover_at
    if cover_at is None:
        shots = edl["shots"]
        best = max(shots, key=lambda s: (s["t1"] - s["t0"]) if s.get("asset") else 0)
        cover_at = (best["t0"] + best["t1"]) / 2
    cover_path = os.path.join(outdir, f"{stem}-cover.jpg")
    title = edl["meta"].get("title", "")
    # 优先：最长有素材镜头的原图（干净，无字幕）
    with_asset = [s for s in edl["shots"] if s.get("asset")]
    ok = False
    if with_asset:
        fav = max(with_asset, key=lambda s: s["t1"] - s["t0"])
        src = {x["id"]: x.get("src") for x in edl.get("assets", [])}.get(fav["asset"])
        if src:
            ok = cover_from_asset(src, title, cover_path)
            if ok:
                print(f"封面（素材原图 {fav['asset']}）→ {cover_path}")
    if not ok:
        ok = make_cover(a.video, cover_at, title, cover_path)
        print(f"封面（成片取帧 {cover_at:.0f}s）→ {cover_path if ok else '失败'}")

    # 3) 元数据
    meta = build_meta(edl, os.path.basename(srt_path),
                      os.path.basename(cover_path) if ok else None)
    meta_path = os.path.join(outdir, f"{stem}-meta.json")
    json.dump(meta, open(meta_path, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"元数据 → {meta_path}")
    print(f"  章节 {len(meta['chapters'])} 个  素材 {len(meta['assets'])} 条  "
          f"简繁? 否")
    for c in meta["chapters"]:
        print(f"   {c['start']:>6.1f}s  {c['title']}")


if __name__ == "__main__":
    main()
