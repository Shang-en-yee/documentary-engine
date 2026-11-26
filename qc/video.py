#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
qc/video.py — 视频级质检（渲后）

静帧质检看不出时间维度上的毛病。这里逐帧算指标，专抓：

  1. 闪烁      镜内相邻帧亮度跳变（颗粒/滤镜不稳定）
  2. 卡顿      同镜出现连续相同帧
  3. 意外硬切  镜内出现大帧差（本该只有镜头边界才有）
  4. 字幕抖动  底部文字块逐帧位移
  5. 黑场      连续多帧近乎全黑
  6. 节奏塌方  镜头时长过于均匀
  7. 音频      削波 / 长段静音（需要成片）

用法:
    python qc/video.py examples/x.json out/frames_x
    python qc/video.py examples/x.json out/x-final.mp4        # 直接测成片
"""
import argparse
import glob
import json
import os
import shutil
import subprocess
import sys
import tempfile

import cv2
import numpy as np

FF = r"C:\Users\bx\AppData\Roaming\Seewo\EasiNote5\Dependencies\FFmpeg\FFmpeg_2\ffmpeg.exe"

# 阈值
FLICKER_MED = 6.0        # 镜内亮度变化中位数上限
FLICKER_MAX = 16.0       # 单帧亮度变化上限
STUTTER_RUN = 12         # 连续相同帧上限（0.4 秒）
CUT_RATIO = 3.2          # 镜内帧差 / 中位数
CUT_MIN = 8.0            # 镜内帧差绝对值下限
JITTER_PX = 6.0          # 字幕块中心位移上限（1080p）
BLACK_LUMA = 6.0
BLACK_RUN = 8            # 连续黑帧上限
DUR_CV_MIN = 0.22        # 镜头时长变异系数下限


def load_frames(frames_or_video, workdir):
    """返回 (fps, [frame ndarray]) ；视频会抽到临时 ASCII 目录"""
    if os.path.isdir(frames_or_video):
        files = sorted(glob.glob(os.path.join(frames_or_video, "*.jpg")) +
                       glob.glob(os.path.join(frames_or_video, "*.png")))
        imgs = [cv2.imdecode(np.fromfile(p, dtype=np.uint8), cv2.IMREAD_COLOR)
                for p in files]
        return 30, [i for i in imgs if i is not None]

    # 视频：先拷成 ASCII 路径再抽帧
    src = os.path.abspath(frames_or_video)
    tmp = os.path.join(tempfile.gettempdir(), "vqc_%d.mp4" % os.getpid())
    shutil.copy2(src, tmp)
    outdir = os.path.join(workdir, "vf")
    os.makedirs(outdir, exist_ok=True)
    subprocess.run([FF, "-y", "-hide_banner", "-loglevel", "error",
                    "-i", tmp, "-vf", "scale=960:-1,fps=30",
                    os.path.join(outdir, "f%05d.jpg")], check=True)
    os.remove(tmp)
    files = sorted(glob.glob(os.path.join(outdir, "*.jpg")))
    imgs = [cv2.imdecode(np.fromfile(p, dtype=np.uint8), cv2.IMREAD_COLOR) for p in files]
    return 30, [i for i in imgs if i is not None]


def text_center(img, scale):
    """底部字幕带里亮块的水平中心（用于检测抖动）"""
    h, w = img.shape[:2]
    band = img[int(h * 0.72):int(h * 0.92)]
    g = cv2.cvtColor(band, cv2.COLOR_BGR2GRAY)
    mask = g > 150
    if mask.sum() < 40:
        return None
    xs = np.where(mask.any(axis=0))[0]
    return float((xs.min() + xs.max()) / 2)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("edl")
    ap.add_argument("source", help="帧目录或成片 mp4")
    a = ap.parse_args()

    edl = json.load(open(a.edl, encoding="utf-8"))
    fps = edl["meta"].get("fps", 30)
    work = tempfile.mkdtemp(prefix="vqc_")
    try:
        got_fps, imgs = load_frames(a.source, work)
        if not imgs:
            sys.exit("没有帧")
        scale = imgs[0].shape[1] / 1920.0 if imgs[0].shape[1] > 0 else 1.0
        print(f"共 {len(imgs)} 帧（{imgs[0].shape[1]}x{imgs[0].shape[0]}）")

        lumas = np.zeros(len(imgs), dtype=np.float32)
        diffs = np.zeros(len(imgs), dtype=np.float32)
        centers = np.full(len(imgs), np.nan, dtype=np.float32)
        prev = None
        for k, im in enumerate(imgs):
            g = cv2.cvtColor(im, cv2.COLOR_BGR2GRAY).astype(np.float32)
            lumas[k] = g.mean()
            if prev is not None:
                diffs[k] = float(np.mean(np.abs(g - prev)))
            prev = g
            c = text_center(im, scale)
            if c is not None:
                centers[k] = c
            imgs[k] = None

        # 把帧号映射回镜头
        def shot_of(fi):
            t = fi / fps
            for s in edl["shots"]:
                if s["t0"] - 0.02 <= t < s["t1"] - 0.02:
                    return s
            return edl["shots"][-1]

        issues = []
        shot_by_id = {sh['id']: sh for sh in edl['shots']}
        per_shot = {}
        for fi in range(len(imgs)):
            s = shot_of(fi)
            per_shot.setdefault(s["id"], []).append(fi)

        for sid, idxs in per_shot.items():
            s = shot_by_id.get(sid) or {}
            if len(idxs) < 8:
                continue
            # 跳过镜首 3 帧（与上一镜的切点）与镜尾 1 帧
            core = idxs[3:-1]
            dl = np.abs(np.diff(lumas[core]))
            dd = diffs[core[1:]]
            # 1) 闪烁
            if float(np.median(dl)) > FLICKER_MED:
                issues.append(f"{sid}: 闪烁，镜内亮度波动中位 {np.median(dl):.1f}")
            hot = np.where(dl > FLICKER_MAX)[0]
            if len(hot):
                issues.append(f"{sid}: 亮度跳变 {len(hot)} 帧，最大 {dl.max():.1f}")
            # 2) 卡顿
            med_d = float(np.median(dd)) if len(dd) else 0.0
            still = max(0.10, med_d * 0.20)
            run, best = 0, 0
            for v in dd:
                run = run + 1 if v < still else 0
                best = max(best, run)
            if best >= STUTTER_RUN and med_d > 0.2:
                issues.append(f"{sid}: 卡顿，最长连续 {best} 帧几乎不变"
                              f"（镜内中位帧差 {med_d:.2f}）")
            # 3) 意外硬切
            if len(dd) > 6:
                med = float(np.median(dd)) + 1e-6
                spikes = np.where((dd > max(12.0, med * 4.0)))[0]
                if len(spikes):
                    issues.append(f"{sid}: 镜内大跳变 {len(spikes)} 处"
                                  f"（帧差 {dd.max():.1f} vs 中位 {med:.1f}）")
            # 4) 字幕抖动
            has_gfx = bool(s.get("graphics"))
            cs = centers[core] if not has_gfx else np.array([])
            ok = ~np.isnan(cs)
            if ok.sum() > 10:
                v = cs[ok]
                spread = float(np.percentile(v, 95) - np.percentile(v, 5))
                spread1080 = spread / max(scale, 1e-6)
                if spread1080 > JITTER_PX * 3.5:
                    issues.append(f"{sid}: 字幕水平抖动 {spread1080:.0f}px(1080p)")

        # 5) 黑场
        black = lumas < BLACK_LUMA
        run = best = 0
        for b in black:
            run = run + 1 if b else 0
            best = max(best, run)
        if best >= BLACK_RUN:
            issues.append(f"全片: 最长连续黑帧 {best} 帧（{best/fps:.1f}s）")

        # 6) 节奏
        durs = np.array([s["t1"] - s["t0"] for s in edl["shots"]], dtype=float)
        if len(durs) > 3:
            cv_ = float(durs.std() / max(durs.mean(), 1e-6))
            if cv_ < DUR_CV_MIN:
                issues.append(f"节奏: 镜头时长变异系数 {cv_:.2f} < {DUR_CV_MIN}，过于均匀")

        # 7) 音频（仅成片）
        if not os.path.isdir(a.source):
            tmp = os.path.join(tempfile.gettempdir(), "vqc_a_%d.wav" % os.getpid())
            shutil.copy2(os.path.abspath(a.source),
                         os.path.join(tempfile.gettempdir(), "vqc_av_%d.mp4" % os.getpid()))
            subprocess.run([FF, "-y", "-hide_banner", "-loglevel", "error",
                            "-i", os.path.join(tempfile.gettempdir(), "vqc_av_%d.mp4" % os.getpid()),
                            "-ac", "2", "-ar", "44100", "-f", "s16le", tmp], check=False)
            if os.path.exists(tmp):
                d = np.frombuffer(open(tmp, "rb").read(), dtype=np.int16).astype(np.float32) / 32768
                os.remove(tmp)
                if len(d):
                    peak = float(np.abs(d).max())
                    if peak > 0.995:
                        issues.append(f"音频: 削波，峰值 {peak:.3f}")
                    # 2 秒窗口的静音段
                    win = 44100 * 2 * 2
                    silent = 0
                    for i in range(0, len(d) - win, win):
                        if np.abs(d[i:i + win]).max() < 0.002:
                            silent += 1
                    if silent > 1:
                        issues.append(f"音频: {silent} 个 2 秒窗口接近静音")

        # 报告
        print(f"\n平均亮度 {lumas.mean():.1f}  平均帧差 {diffs.mean():.2f}  "
              f"最长黑场 {best} 帧")
        if issues:
            print(f"\n视频级问题 {len(issues)} 条:")
            for i in issues:
                print("  [!]", i)
            sys.exit(1)
        print("\n视频级质检通过")
    finally:
        shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    main()
