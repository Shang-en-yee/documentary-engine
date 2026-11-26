#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""shotsheet.py — 从渲染帧生成逐镜总览图"""
import cv2, numpy as np, json, os, sys
from PIL import Image, ImageDraw, ImageFont


def imread_u(p):
    return cv2.imdecode(np.fromfile(p, dtype=np.uint8), cv2.IMREAD_COLOR)


def main(base):
    edl = json.load(open(os.path.join(base, "examples", "voyager.json"), encoding="utf-8"))
    fdir = os.path.join(base, "out", "frames_v2")
    fs = sorted(os.listdir(fdir))
    fps = edl["meta"]["fps"]
    fnt = ImageFont.truetype(r"C:\Windows\Fonts\msyh.ttc", 15)
    W, H = 480, 270
    cols, rows = 4, 3
    per = cols * rows
    shots = edl["shots"]
    for s in range((len(shots) + per - 1) // per):
        sheet = Image.new("RGB", (cols * W, rows * H), (8, 9, 12))
        dr = ImageDraw.Draw(sheet)
        for k in range(per):
            i = s * per + k
            if i >= len(shots):
                break
            sh = shots[i]
            t = (sh["t0"] + sh["t1"]) / 2
            f = os.path.join(fdir, fs[min(int(t * fps), len(fs) - 1)])
            im = cv2.cvtColor(imread_u(f), cv2.COLOR_BGR2RGB)
            p = Image.fromarray(im).resize((W, H - 24))
            x, y = (k % cols) * W, (k // cols) * H
            sheet.paste(p, (x, y))
            dr.rectangle([x, y + H - 24, x + W, y + H], fill=(14, 16, 22))
            label = "%s  %d-%ds" % (sh["id"], sh["t0"], sh["t1"])
            dr.text((x + 4, y + H - 21), label, fill=(240, 200, 120), font=fnt)
        out = os.path.join(base, "out", "shots-%d.jpg" % (s + 1))
        sheet.save(out, quality=90)
        print(out)


if __name__ == "__main__":
    main(sys.argv[1])
