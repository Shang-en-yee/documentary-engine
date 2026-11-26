#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build.py — 把 EDL 注入引擎，产出可渲染的单页

    python build.py examples/slice-earth.json out.html

原理：engine/render.html 预留 window.__EDL__ 注入点；
本脚本把 EDL 序列化成 JSON 塞进 <head>，并重写素材相对路径为绝对 file:// 路径。
"""
import json, sys, os, io, html, urllib.parse

HERE = os.path.dirname(os.path.abspath(__file__))
ENGINE = os.path.join(HERE, "..", "render", "engine", "render.html")


def to_file_url(p):
    p = p.replace("\\", "/")
    # 中文路径必须百分号编码，否则浏览器可能加载不到
    return "file:///" + urllib.parse.quote(p, safe="/:")


def main(edl_path, out_path):
    edl = json.load(open(edl_path, encoding="utf-8"))
    base_dir = os.path.dirname(HERE)   # 项目根目录（io/ 的上一级）

    # 把素材相对路径解析成绝对 file:// URL，缺文件直接报错
    for a in edl.get("assets", []):
        src = a.get("src")
        if not src:
            continue
        if not os.path.isabs(src):
            src = os.path.normpath(os.path.join(base_dir, src))
        if not os.path.exists(src):
            raise SystemExit(f"[build] 素材不存在: {src}")
        a["src"] = to_file_url(src)

    engine_dir = os.path.dirname(ENGINE)
    eng_url = to_file_url(engine_dir)
    page = io.open(ENGINE, encoding="utf-8").read()

    # 资源路径改成绝对路径
    page = page.replace('href="css/engine.css"', f'href="{eng_url}/css/engine.css"')
    for js in ("core", "asset", "graphics", "graphics-extra", "graphics-camera", "graphics-waves", "text", "main"):
        page = page.replace(f'src="js/{js}.js"', f'src="{eng_url}/js/{js}.js"')

    inject = "<script>window.__EDL__ = " + json.dumps(edl, ensure_ascii=False) + ";</script>\n</head>"
    if "</head>" not in page:
        sys.exit("render.html 缺少 </head>")
    page = page.replace("</head>", inject, 1)

    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    io.open(out_path, "w", encoding="utf-8").write(page)

    total = sum(s["t1"] - s["t0"] for s in edl["shots"])
    print(f"OK  {out_path}")
    print(f"    镜头 {len(edl['shots'])} 个，时长 {total:.1f}s，素材 {len(edl.get('assets', []))} 条")
    print(f"    预览: file:///{out_path.replace(os.sep, '/')}?t=0")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        sys.exit("用法: python build.py film.json out.html")
    main(sys.argv[1], sys.argv[2])
