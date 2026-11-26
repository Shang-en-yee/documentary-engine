#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
make_demo.py — 用镜头库装配一部 40 秒短片

这是模块化架构的验证：不手写 JSON，只用 director 的镜头原型组装。

    python director/make_demo.py
    python film.py check   examples/demo-europa.json
    python film.py preview examples/demo-europa.json
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

from director.film import Film            # noqa: E402
from director.assets import AssetTable    # noqa: E402
from director import shots as S           # noqa: E402

# ---------- 素材登记 ----------
A = AssetTable()
A.add("europa", "assets/galileo/europa-PIA19048.jpg", "欧罗巴表面 · 伽利略号")
A.add("chaos", "assets/galileo/europa-PIA23873.jpg", "欧罗巴混沌地形")
A.add("ocean", "assets/galileo/ocean-PIA10131.jpg", "欧罗巴冰壳与海洋 · 剖面构想")
A.add("jupiter", "assets/galileo/jupiter-PIA21985.jpg", "木星大红斑")

f = Film({
    "version": "1.0",
    "meta": {"title": "欧罗巴 · 冰下之海", "subtitle": "demo", "duration": 0,
             "fps": 30, "resolution": [1920, 1080], "language": "zh-CN"},
    "assets": list(A),
    "moods": {
        "amber": {"lift": [0.06, 0.03, -0.02], "tint": [0.10, 0.04, -0.04], "sat": 0.92, "hue": 30},
        "steel": {"lift": [0.0, 0.01, 0.04], "tint": [-0.04, 0.01, 0.08], "sat": 0.78, "hue": 215},
        "jade":  {"lift": [0.0, 0.02, 0.01], "tint": [-0.03, 0.05, 0.02], "sat": 0.94, "hue": 150},
        "deep":  {"lift": [-0.02, 0.0, 0.04], "tint": [-0.03, 0.02, 0.10], "sat": 0.72, "hue": 225},
    },
    "acts": [
        {"id": "a1", "t0": 0, "t1": 0, "mood": "jade", "title": "冰"},
        {"id": "a2", "t0": 0, "t1": 0, "mood": "deep", "title": "海"},
        {"id": "a3", "t0": 0, "t1": 0, "mood": "deep", "title": "落版"},
    ],
    "shots": [],
    "audio": {
        "track": {"src": "assets/music/Eternal Hope.mp3", "title": "Eternal Hope",
                  "author": "Kevin MacLeod", "license": "CC-BY",
                  "source_url": "https://incompetech.com/music/royalty-free/index.html",
                  "track_start": 96, "gain": 2.6},
        "envelope": [{"t": 0, "gain": 0.16}, {"t": 16, "gain": 0.24},
                     {"t": 28, "gain": 0.32}, {"t": 40, "gain": 0.30}],
    },
    "credits": {"attribution": ["影像：NASA（公有领域）",
                                "配乐：Eternal Hope — Kevin MacLeod，CC BY 4.0"]},
})

# ---------- 装配 ----------
# 第一幕 · 冰（0–18）
f.add(S.archive("d01", "a1", 0, 7, "europa", "jade",
                caption="NASA · 欧罗巴表面 · 伽利略号",
                lines=["木星旁边 有一颗月亮"], zoom=0.05))
f.add(S.hold("d02", "a1", 7, 2.5, "jupiter", "jade",
             lines=["它有海 但被冰封着"], zoom=-0.03))
f.add(S.hold("d03", "a1", 9.5, 8.5, "chaos", "jade",
             lines=["表面全是裂缝"], zoom=-0.045))

# 第二幕 · 海（18–32）
g, cam = S.waves_panel(n=11, sum_curve=True, push=1.22, seed=31)
f.add(S.graphics_shot("d04", "a2", 18, 7, "deep", graphics=g, camera=cam,
                      lines=["裂缝底下 有别的东西", "木星的磁场 在它旁边抖动"],
                      accent=["别的东西"]))
f.add(S.archive("d05", "a2", 25, 7, "ocean", "deep",
                caption="欧罗巴冰壳与海洋 · 剖面构想",
                lines=["冰层下面 有一片海"], accent=["海"], zoom=0.04))

# 第三幕 · 落版（32–40）
f.add(S.ending("d06", "a3", 32, 8, grade="deep",
               lines=["我们还没有到过那里"], accent=["没有到过"]))

f.finalize()
out = os.path.join(ROOT, "examples", "demo-europa.json")
f.save(out)
print(f"已生成 {out}")
print(f"  镜头 {len(f.shots)}  素材 {len(A)}  时长 {f.total():.0f}s")
print("  连续性问题:", f.check_continuity() or "无")
