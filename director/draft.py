#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
director/draft.py — 剧本 → 分镜草案

输入一份「剧本」（比 EDL 轻得多，只写叙事和素材提示），输出一份完整 EDL。
人只需要再调配色、个别镜头和图形。

剧本格式（JSON，30 行左右就能撑起 3 分钟）：

{
  "title": "伽利略号的最后一天",
  "assets": { "launch": "assets/galileo/launch-8913765.jpg", ... },
  "acts": [
    { "id": "a1", "title": "出发", "mood": "amber",
      "beats": [
        { "text": "1989 年 10 月 18 日\\n亚特兰蒂斯号升空",
          "asset": "launch", "caption": "NASA · STS-34",
          "accent": ["升空"] },
        { "text": "没有一枚火箭\\n能一次把它送到那里", "graphics": "timeline" }
      ]
    }
  ]
}

生成规则
  时长 = 字数 / 4.2 + 1.2（入）+ 0.8（出），夹在 3–12 秒
  素材 → archive 镜头，推拉方向交替
  无素材 → 图形镜头（timeline / dots / waves 三选一，可显式指定）
  数字自动染金；显式 accent 优先
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

from director.film import Film            # noqa: E402
from director.assets import AssetTable    # noqa: E402
from director import shots as S           # noqa: E402

MOODS = {
    "amber": {"lift": [0.06, 0.03, -0.02], "tint": [0.10, 0.04, -0.04], "sat": 0.92, "hue": 30},
    "steel": {"lift": [0.0, 0.01, 0.04], "tint": [-0.04, 0.01, 0.08], "sat": 0.78, "hue": 215},
    "jade":  {"lift": [0.0, 0.02, 0.01], "tint": [-0.03, 0.05, 0.02], "sat": 0.94, "hue": 150},
    "deep":  {"lift": [-0.02, 0.0, 0.04], "tint": [-0.03, 0.02, 0.10], "sat": 0.72, "hue": 225},
    "neutral": {"lift": [0, 0, 0], "tint": [0, 0, 0], "sat": 0.85, "hue": 0},
}

CHARS_PER_SEC = 4.2
LEAD, TAIL = 1.2, 0.8
MIN_DUR, MAX_DUR = 3.0, 12.0


def count_chars(s):
    return len(s.replace(" ", "").replace("\n", ""))


def beat_duration(beat):
    lines = beat["text"].split("\n")
    chars = sum(count_chars(l) for l in lines)
    dur = chars / CHARS_PER_SEC + LEAD + TAIL
    return round(max(MIN_DUR, min(MAX_DUR, dur)), 1)


def auto_accent(text):
    """数字自动染金（年份、数量），其余靠显式 accent"""
    import re
    nums = re.findall(r"\d+[\d,\.]*\s*(?:年|月|日|时|分|秒|次|颗|吨|公里|小时|天)?", text)
    out = []
    for n in nums:
        n = n.strip()
        if n and n not in out:
            out.append(n)
    return out[:1]




def auto_brightness(src):
    """素材本身太暗就自动提亮（暗图配暗调色会黑成一片）"""
    try:
        import cv2
        import numpy as np
        path = src if os.path.isabs(src) else os.path.join(ROOT, src)
        im = cv2.imdecode(np.fromfile(path, dtype=np.uint8), cv2.IMREAD_COLOR)
        if im is None:
            return 1.0
        mean = float(cv2.cvtColor(im, cv2.COLOR_BGR2GRAY).mean())
        if mean < 40:
            return round(min(2.6, max(1.0, 44.0 / max(mean, 8))), 2)
        return 1.0
    except Exception:
        return 1.0

GRAPHIC_SETS = {
    "timeline": lambda ctx: S.timeline_panel(ctx.get("marks") or ["1", "2", "3"], active=0),
    "dots": lambda ctx: S.dots_panel(count=ctx.get("count", 240)),
    "waves": lambda ctx: S.waves_panel(n=ctx.get("n", 13), sum_curve=True,
                                       push=1.2, seed=ctx.get("seed", 77)),
}


def build_draft(script, out_path=None, target=None):
    A = AssetTable()
    for aid, src in (script.get("assets") or {}).items():
        A.add(aid, src, "")

    f = Film({
        "version": "1.0",
        "meta": {"title": script.get("title", "未命名"),
                 "subtitle": script.get("subtitle", ""),
                 "duration": 0, "fps": script.get("fps", 30),
                 "resolution": [1920, 1080], "language": "zh-CN"},
        "assets": list(A),
        "moods": MOODS,
        "acts": [], "shots": [],
        "audio": script.get("audio") or {"envelope": []},
        "credits": script.get("credits") or {"attribution": []},
    })

    t = 0.0
    zoom_dir = 1
    n_shot = 0
    used = {}          # 素材复用计数
    for ai, act in enumerate(script.get("acts", [])):
        aid = act.get("id") or f"a{ai+1}"
        f.edl["acts"].append({"id": aid, "t0": 0, "t1": 0,
                              "mood": act.get("mood", "steel"),
                              "title": act.get("title", "")})
        grade = act.get("mood", "steel")
        for beat in act.get("beats", []):
            n_shot += 1
            sid = beat.get("id") or f"s{n_shot:02d}"
            dur = beat.get("dur") or beat_duration(beat)
            # 节奏塑形：单行短句压缩成呼吸点，带出处的长句拉长
            lines_n = len([l for l in beat["text"].split("\n") if l.strip()])
            if lines_n <= 1 and "dur" not in beat:
                dur *= 0.62          # 一句话 = 快切
            elif beat.get("caption") and lines_n >= 2 and "dur" not in beat:
                dur *= 1.18          # 有出处的长镜 = 停留
            lines = [l for l in beat["text"].split("\n") if l.strip()]
            accent = beat.get("accent") or auto_accent(beat["text"])

            if beat.get("asset"):
                zoom = 0.045 if zoom_dir > 0 else -0.04
                zoom_dir *= -1
                src = (script.get("assets") or {}).get(beat["asset"], "")
                bright = beat.get("brightness") or auto_brightness(src)
                # 同一素材第二次出现时换裁切，避免"同一张图放三遍"
                n_use = used.get(beat["asset"], 0)
                used[beat["asset"]] = n_use + 1
                optics = beat.get("optics")
                if n_use > 0 and not optics:
                    crops = [[0.10, 0.06, 0.62, 0.62], [0.28, 0.18, 0.48, 0.48]]
                    optics = {"crop": crops[(n_use - 1) % len(crops)]}
                parts = S.archive(sid, aid, t, dur, beat["asset"], grade,
                                  caption=beat.get("caption"),
                                  lines=lines, accent=accent, zoom=zoom,
                                  optics=optics,
                                  brightness=bright)
            elif (ai == len(script.get("acts", [])) - 1
                  and beat is act.get("beats", [])[-1]
                  and not beat.get("graphics")):
                parts = S.ending(sid, aid, t, dur, lines=lines, accent=accent,
                                 grade=grade, brightness=beat.get("brightness", 2.0))
            else:
                gkey = beat.get("graphics") or "timeline"
                make = GRAPHIC_SETS.get(gkey, GRAPHIC_SETS["timeline"])
                g = make(beat)
                cam = None
                if isinstance(g, tuple):
                    g, cam = g
                parts = S.graphics_shot(sid, aid, t, dur, grade, graphics=g,
                                        lines=lines, accent=accent, camera=cam,
                                        brightness=beat.get("brightness", 1.8))
            f.add(parts)
            t += dur

    if target:
        cur = sum(s["t1"] - s["t0"] for s in f.shots)
        k = target / cur if cur else 1.0
        for s in f.shots:
            s["t1"] = round(s["t0"] + (s["t1"] - s["t0"]) * k, 2)
        print(f" 时长归一化 {cur:.0f}s → {target:.0f}s（×{k:.2f}）")

    f.finalize()
    if out_path:
        f.save(out_path)
    return f


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("script")
    ap.add_argument("--out", default=None)
    ap.add_argument("--duration", type=float, default=None, help="目标总时长（秒）")
    a = ap.parse_args()
    script = json.load(open(a.script, encoding="utf-8"))
    out = a.out or os.path.join(ROOT, "examples",
                                os.path.splitext(os.path.basename(a.script))[0] + "-draft.json")
    f = build_draft(script, out, target=a.duration)
    print(f"草案已生成: {out}")
    print(f"  镜头 {len(f.shots)}  素材 {len(f.edl['assets'])}  时长 {f.total():.0f}s")
    for act in f.edl["acts"]:
        print(f"   {act['id']} {act['title']:6s} {act['t0']:5.1f}–{act['t1']:5.1f}s  {act['mood']}")


if __name__ == "__main__":
    main()
