# -*- coding: utf-8 -*-
"""
director.shots — 镜头库

两部片子写下来，真正重复的是这些「镜头原型」。
把它们参数化，组装新片就不用从零敲 JSON。

用法：
    from director.shots import archive, graphics_shot, montage, ending
    f.add(archive("s01", "a1", 0, 9, "launch", grade="amber",
                  cap="NASA · STS-34 · 1989-10-18",
                  lines=["1989 年 10 月 18 日", "亚特兰蒂斯号升空"]))
"""


# ---------------------------------------------------------------- 基础工具

def t1(t, lines, accent=None, mode="accumulate"):
    return {"tier": "T1", "t": t, "mode": mode, "lines": lines, "accent": accent or []}


def t2(t, lines, accent=None):
    return {"tier": "T2", "t": t, "mode": "fade", "lines": lines, "accent": accent or []}


def cap(t, text):
    return {"tier": "T5", "t": t, "pos": "tl", "mode": "fade", "lines": [text]}


def t3(t, text, raised=True):
    d = {"tier": "T3", "t": t, "mode": "fade", "lines": [text]}
    return d


def t4(t, text):
    return {"tier": "T4", "t": t, "pos": "tr", "mode": "fade", "lines": [text]}


def spread(lines, t0=0.8, gap=None, accent=None):
    """把一串句子按阅读节奏排开，返回 T1 列表"""
    out = []
    t = t0
    for i, ln in enumerate(lines):
        out.append(t1(t, [ln], accent if isinstance(accent, list) and i < len(accent) else None))
        t += gap if gap else max(1.8, min(4.2, len(ln) / 3.4))
    return out


def _shot(sid, act, t0, t1_, asset, grade, motion, texts,
          graphics=None, optics=None, brightness=1.0, camera=None,
          tin="cut", tout="cut"):
    d = {
        "id": sid, "act": act, "t0": round(t0, 2), "t1": round(t1_, 2),
        "asset": asset, "grade": grade, "motion": motion,
        "graphics": graphics or [], "texts": texts or [],
        "transition_in": tin, "transition_out": tout,
    }
    if optics:
        d["optics"] = optics
    if brightness != 1.0:
        d["brightness"] = brightness
    if camera:
        d["camera"] = camera
    return d


KB = lambda zoom, pan=(0.0, 0.0): {"type": "kenburns", "zoom": zoom,
                                   "pan": list(pan), "ease": "linear"}
STATIC = {"type": "static"}


# ---------------------------------------------------------------- 镜头原型

def archive(sid, act, t0, dur, asset, grade, *, caption=None, lines=(),
            accent=None, zoom=0.04, pan=(0.0, 0.0), optics=None,
            brightness=1.0, tin="cut", tout="cut"):
    """档案素材 + 缓慢推拉 + 逐句字幕"""
    texts = []
    if caption:
        texts.append(cap(0.4, caption))
    texts += spread(lines, t0=0.8, accent=accent)
    return _shot(sid, act, t0, t0 + dur, asset, grade, KB(zoom, pan), texts,
                 optics=optics, brightness=brightness, tin=tin, tout=tout)


def graphics_shot(sid, act, t0, dur, grade, *, graphics, lines=(),
                  accent=None, camera=None, brightness=1.8,
                  tin="cut", tout="cut"):
    """纯图形镜头（无素材）"""
    return _shot(sid, act, t0, t0 + dur, None, grade, STATIC,
                 spread(lines, t0=0.6, accent=accent),
                 graphics=graphics, brightness=brightness,
                 camera=camera, tin=tin, tout=tout)


def montage(act, t0, items, *, dur=0.8, grade="steel"):
    """闪帧蒙太奇：items = [(id, asset), ...]"""
    out = []
    for i, (sid, asset) in enumerate(items):
        out.append(_shot(sid, act, t0 + i * dur, t0 + (i + 1) * dur,
                         asset, grade, STATIC, [], tin="cut", tout="cut"))
    return out


def hold(sid, act, t0, dur, asset, grade, *, lines=(), accent=None,
         brightness=1.0, zoom=0.03):
    """静止长镜，只放一句重话"""
    return _shot(sid, act, t0, t0 + dur, asset, grade, KB(zoom),
                 spread(lines, t0=0.5, accent=accent), brightness=brightness)


def ending(sid, act, t0, dur, *, lines, accent=None, grade="deep",
           beams=11, hue="150,210,255", brightness=2.0):
    """落版：光柱 + 短句"""
    return _shot(sid, act, t0, t0 + dur, None, grade, STATIC,
                 spread(lines, t0=0.3, accent=accent),
                 graphics=[{"kind": "beam_array",
                            "params": {"count": beams, "vx": 0.5, "vy": 0.27, "hue": hue}}],
                 brightness=brightness, tin="black", tout="black")


# ---------------------------------------------------------------- 常用图形组

def waves_panel(*, n=13, sum_curve=False, marks=None, parallax=0.5,
                push=1.2, seed=77):
    """波束 + 可选叠加曲线 + 可选刻度轴 + 摄像机推近"""
    g = [
        {"kind": "grid2d", "depth": 0.2, "params": {"spacing": 58, "alpha": 0.04}},
        {"kind": "wave_stack", "depth": 0.7, "t0": 0.15,
         "params": {"n": n, "x0": 0.1, "x1": 0.95, "y0": 0.38, "span": 0.38,
                    "amp": 9, "rise": 1.2, "sum": sum_curve, "sumY": 0.72,
                    "seed": seed, "stagger": 0.045}},
    ]
    if marks:
        g.append({"kind": "axis_labels", "overlay": True, "t0": 0.7,
                  "params": {"x0": 0.1, "x1": 0.95, "y": 0.84,
                             "marks": marks, "rise": 1.0}})
    cam = {"s0": 1.0, "s1": push, "t0": 0.1, "t1": 5.4,
           "ease": "easeInOut", "cy": 0.43, "parallax": parallax}
    return g, cam


def timeline_panel(marks, active=0, y=0.62):
    return [{"kind": "grid2d", "depth": 0.25, "params": {"spacing": 68, "alpha": 0.05}},
            {"kind": "timeline_axis", "overlay": True,
             "params": {"y": y, "x0": 0.13, "x1": 0.87, "dur": 1.6,
                        "marks": marks, "active": active}}]


def dots_panel(count=240, y=0.52):
    return [{"kind": "scatter_axis", "depth": 0.5,
             "params": {"y": y, "x0": 0.13, "x1": 0.87, "count": count,
                        "mode": "regular", "dur": 3.6}}]
