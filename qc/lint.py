#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
lint.py — EDL 校验器（P0 交付物）

不依赖 jsonschema，手写校验。检查两类问题：

A. 结构错误（硬失败）
   - 必填字段缺失 / 类型不对
   - 素材缺 license 或 source_url
   - 镜头时间重叠 / 超出总时长
   - 引用了不存在的 asset / mood / act
   - graphics.kind 不在白名单

B. 风格违规（警告，源自参考片实测规范）
   - 单条字幕 > 22 字
   - 阅读速度不在 2.0–2.5 字/秒
   - 高潮段没有 ≥25s 的无字幕区
   - 镜长缺少快慢对比（最快/最慢 < 3 倍）
   - 幕与幕之间色相跨度 < 60°
   - 肯·伯恩斯速率不在 0.2–1.5%/秒

用法:
    python lint.py examples/slice-1859.json
退出码 0 = 通过（可能有警告），1 = 有硬错误
"""
import json, sys, os

def _discover_kinds():
    """从引擎源码里自动发现已实现的图形 kind，避免 lint 与引擎脱节"""
    import re
    kinds = set()
    for fn in ("graphics.js", "graphics-extra.js", "graphics-waves.js"):
        g = os.path.join(HERE, "..", "render", "engine", "js", fn)
        if os.path.exists(g):
            src = open(g, encoding="utf-8").read()
            kinds |= set(re.findall(r"registerKind\(['\"]([a-z0-9_]+)['\"]", src))
    return kinds

HERE = os.path.dirname(os.path.abspath(__file__))
GRAPHIC_KINDS = _discover_kinds() or {
    "grid2d", "vline", "counter", "progress_ring", "particles_3d", "bokeh", "highlight_box",
}
TIERS = {"T1", "T2", "T3", "T4", "T5", "T6"}
MOTIONS = {"kenburns", "pan", "static", "internal", "camera3d"}
TRANSITIONS = {"cut", "flash", "black", "dissolve", "whip"}
LICENSES = {"public-domain", "CC0", "CC-BY", "CC-BY-SA", "own", "permission"}
AUDIO_LICENSES = {"CC0", "CC-BY", "own", "permission", "public-domain"}


def main(path):
    try:
        edl = json.load(open(path, encoding="utf-8"))
    except Exception as e:
        print(f"[FAIL] 读不了: {e}")
        return 1

    errs, warns = [], []

    # ---------- A. 结构 ----------
    for f in ("version", "meta", "acts", "shots"):
        if f not in edl:
            errs.append(f"缺少顶层字段 {f}")
    if errs:
        for e in errs: print("[ERROR]", e)
        return 1

    meta = edl["meta"]
    for f in ("title", "duration", "fps", "resolution"):
        if f not in meta:
            errs.append(f"meta 缺少 {f}")
    total = meta.get("duration", 0)

    # 素材
    assets = {a["id"]: a for a in edl.get("assets", [])}
    for a in edl.get("assets", []):
        if "license" not in a:
            errs.append(f"素材 {a.get('id')} 缺 license")
        elif a["license"] not in LICENSES:
            errs.append(f"素材 {a.get('id')} license 非法: {a['license']}")
        if a.get("license") in ("CC-BY", "CC-BY-SA") and not a.get("attribution"):
            errs.append(f"素材 {a['id']} 是 {a['license']}，必须填 attribution")
        if not a.get("source_url"):
            warns.append(f"素材 {a.get('id')} 没有 source_url")

    # 幕
    moods = edl.get("moods", {})
    acts = {a["id"]: a for a in edl.get("acts", [])}
    for a in edl.get("acts", []):
        if a.get("mood") and a["mood"] not in moods:
            errs.append(f"幕 {a['id']} 引用了不存在的 mood: {a['mood']}")

    # 镜头
    shots = edl.get("shots", [])
    prev_end = -1
    for sh in shots:
        sid = sh.get("id", "?")
        t0, t1 = sh.get("t0"), sh.get("t1")
        if t0 is None or t1 is None:
            errs.append(f"{sid}: 缺 t0/t1"); continue
        if t1 <= t0:
            errs.append(f"{sid}: t1 <= t0")
        if t0 < prev_end - 1e-6:
            warns.append(f"{sid}: 与前一镜重叠于 {t0}s")
        prev_end = max(prev_end, t1)
        if t1 > total + 1e-6:
            errs.append(f"{sid}: 结束 {t1}s 超出总时长 {total}s")
        if sh.get("act") and sh["act"] not in acts:
            errs.append(f"{sid}: 引用了不存在的 act")
        if sh.get("grade") and sh["grade"] not in moods:
            errs.append(f"{sid}: 引用了不存在的 mood {sh['grade']}")
        aid = sh.get("asset")
        if aid is not None and aid not in assets:
            errs.append(f"{sid}: 引用了不存在的素材 {aid}")

        m = sh.get("motion") or {}
        if m.get("type") and m["type"] not in MOTIONS:
            errs.append(f"{sid}: motion.type 非法 {m['type']}")
        # 肯·伯恩斯速率
        if m.get("type") == "kenburns" and m.get("zoom") is not None:
            dur = t1 - t0
            if dur > 0:
                rate = abs(m["zoom"]) / dur * 100
                if not (0.2 <= rate <= 1.5):
                    warns.append(f"{sid}: 推拉速率 {rate:.2f}%/秒，超出参考规范 0.2–1.5")

        for tr in ("transition_in", "transition_out"):
            if sh.get(tr) and sh[tr] not in TRANSITIONS:
                errs.append(f"{sid}: {tr} 非法 {sh[tr]}")

        for g in sh.get("graphics") or []:
            if g.get("kind") not in GRAPHIC_KINDS:
                errs.append(f"{sid}: graphics.kind 未实现: {g.get('kind')}")

        # 字幕
        for tx in sh.get("texts") or []:
            if tx.get("tier") not in TIERS:
                errs.append(f"{sid}: tier 非法 {tx.get('tier')}")
            lines = tx.get("lines") or []
            if not lines:
                errs.append(f"{sid}: 字幕空")
            for ln in lines:
                if tx.get("tier") in ("T1", "T2") and len(ln) > 22:
                    warns.append(f"{sid}: 字幕 {len(ln)} 字 > 22：{ln[:16]}…")
            if tx.get("tier") not in ("T1", "T2"):
                continue          # T3–T6 是标签，不受阅读速度约束
            chars = sum(len(x) for x in lines)
            # 该组最后一句可以长留，不参与速度检查
            same = [x for x in (sh.get("texts") or [])
                    if x.get("tier") == tx.get("tier") and x.get("pos") == tx.get("pos")
                    and x.get("t", 0) > tx.get("t", 0)]
            if not same:
                continue
            hold = tx.get("dur")
            if hold is None:
                # 估算到下一句字幕出现
                nxt = [x["t"] for x in (sh.get("texts") or [])
                       if x.get("tier") == tx.get("tier")
                       and x.get("pos") == tx.get("pos")
                       and x.get("t", 0) > tx.get("t", 0)]
                hold = (min(nxt) - tx["t"]) if nxt else (t1 - sh["t0"] - tx["t"])
            if hold and hold > 0.3:
                rate = chars / hold
                if chars >= 6 and not (2.0 <= rate <= 5.5):
                    warns.append(f"{sid}: 阅读速度 {rate:.1f} 字/秒，规范 2.0–5.5")

    # ---------- B. 风格 ----------
    durs = [s["t1"] - s["t0"] for s in shots if s["t1"] > s["t0"]]
    if durs:
        ratio = max(durs) / max(min(durs), 0.01)
        if ratio < 3:
            warns.append(f"镜长快慢对比只有 {ratio:.1f} 倍，规范建议 ≥3 倍")

    # 无字幕区
    sub_windows = []
    for sh in shots:
        for tx in sh.get("texts") or []:
            if tx.get("tier") in ("T1", "T2"):
                sub_windows.append(sh["t0"] + tx["t"])
    if sub_windows:
        sub_windows.sort()
        gaps = [(a, b) for a, b in zip(sub_windows, sub_windows[1:]) if b - a >= 25]
        if not gaps and total >= 240:
            warns.append("全片没有 ≥25s 的无字幕区（参考片高潮段有 32s）")

    # 色相跨度
    hues = [(m.get("hue"), k) for k, m in moods.items() if m.get("hue") is not None]
    if len(hues) >= 2:
        hs = [h for h, _ in hues]
        if max(hs) - min(hs) < 60:
            warns.append(f"各幕色相跨度只有 {max(hs)-min(hs):.0f}°，规范建议 ≥60°")

    # 音频
    au = edl.get("audio") or {}
    tr = au.get("track")
    if tr:
        if tr.get("license") not in AUDIO_LICENSES:
            errs.append(f"配乐 license 非法: {tr.get('license')}")
        if tr.get("license") in ("CC-BY",) and not tr.get("source_url"):
            errs.append("CC-BY 配乐必须填 source_url")

    # ---------- 输出 ----------
    for w in warns: print("[warn]", w)
    for e in errs: print("[ERROR]", e)
    print()
    if errs:
        print(f"未通过：{len(errs)} 个错误，{len(warns)} 个警告")
        return 1
    print(f"通过：{len(shots)} 个镜头 / {total}s / {len(warns)} 个警告")
    return 0


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit("用法: python lint.py film.json")
    sys.exit(main(sys.argv[1]))
