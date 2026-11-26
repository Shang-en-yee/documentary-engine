#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""从已渲染的帧目录直接编码 mp4（避免重渲）"""
import glob, os, subprocess, sys, tempfile
import cv2
import numpy as np

FF = r"C:\Users\bx\AppData\Roaming\Seewo\EasiNote5\Dependencies\FFmpeg\FFmpeg_2\ffmpeg.exe"


def main():
    fdir, out, fps = sys.argv[1], sys.argv[2], int(sys.argv[3]) if len(sys.argv) > 3 else 30
    files = sorted(glob.glob(os.path.join(fdir, "*.jpg")) + glob.glob(os.path.join(fdir, "*.png")))
    print(f"帧数 {len(files)}")
    if not files:
        sys.exit("没有帧")

    # 先写 mp4v 到临时 ASCII 路径（OpenCV 不支持非 ASCII 路径）
    tmp = os.path.join(tempfile.gettempdir(), "enc_frames_%d.mp4" % os.getpid())
    first = cv2.imdecode(np.fromfile(files[0], dtype=np.uint8), cv2.IMREAD_COLOR)
    H, W = first.shape[:2]
    vw = cv2.VideoWriter(tmp, cv2.VideoWriter_fourcc(*"mp4v"), fps, (W, H))
    for i, f in enumerate(files):
        img = cv2.imdecode(np.fromfile(f, dtype=np.uint8), cv2.IMREAD_COLOR)
        if img is None:
            continue
        vw.write(img)
        if i % 600 == 0:
            print(f"  {i}/{len(files)}", flush=True)
    vw.release()

    # 再转 H.264 到目标路径
    subprocess.run([FF, "-y", "-hide_banner", "-loglevel", "error", "-i", tmp,
                    "-c:v", "libx264", "-crf", "23", "-preset", "medium",
                    "-pix_fmt", "yuv420p", "-movflags", "+faststart", out], check=True)
    os.remove(tmp)
    print(f"OK {out}  {os.path.getsize(out)/1024/1024:.1f} MB")


if __name__ == "__main__":
    main()
