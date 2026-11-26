#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
preview.py — 渲前预览与自动质检

目的：**在全片渲染（40 分钟）之前，用 1 分钟把能发现的问题都发现掉。**

做什么：
  1. 构建页面（复用 build.py）
  2. 启动一次无头 Edge，逐镜 seek 到若干时间点
  3. 每个时间点做三件事：
     - 截图（半分辨率，用于人工目检）
     - 用 JS 读取所有文字元素的包围盒（用于重叠检测）
     - 采样文字背后的背景亮度（用于对比度检测）
  4. 输出：preview/ 目录 + 总览图 + qc.json + 控制台报告

检测项：
  * 文字重叠（T1/T2/T3 之间、字幕与资料标注之间）
  * 文字越界（超出安全区）
  * 字幕对比度不足（背景太亮或太暗）
  * 镜头亮度异常（过暗/过曝）

用法:
    python preview.py examples/voyager.json
    python preview.py examples/voyager.json --per-shot 3 --width 960
"""
import argparse, base64, json, os, subprocess, sys, tempfile, time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "io"))

EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
SAFE = {"x0": 0.04, "y0": 0.04, "x1": 0.96, "y1": 0.96}   # 安全区（归一化）

# 检测阈值
MIN_GAP = 6            # 两个文字块最小间距（px @1080p）
MIN_CONTRAST = 0.18    # 文字与背景的亮度差下限（0-1）
LUMA_MIN, LUMA_MAX = 8, 92   # 单镜平均亮度合理区间（0-255）


# ---------------------------------------------------------------- CDP
class CDP:
    def __init__(self, port, timeout=60):
        import websocket
        targets = None
        for _ in range(80):
            try:
                with urllib.request.urlopen(f"http://127.0.0.1:{port}/json/list", timeout=1) as r:
                    targets = json.loads(r.read().decode())
                if targets:
                    break
            except Exception:
                pass
            time.sleep(0.25)
        if not targets:
            raise RuntimeError("浏览器没起来")
        page = None
        for t in targets:
            if t.get("type") == "page":
                page = t
                break
        if page is None:
            raise RuntimeError("没有可用的 page target")
        self.ws = websocket.create_connection(page["webSocketDebuggerUrl"], timeout=timeout)
        self.id = 0
        self.send("Page.enable")
        self.send("Runtime.enable")

    def send(self, method, params=None):
        self.id += 1
        self.ws.send(json.dumps({"id": self.id, "method": method, "params": params or {}}))
        while True:
            msg = json.loads(self.ws.recv())
            if msg.get("id") == self.id:
                if "error" in msg:
                    raise RuntimeError(msg["error"])
                return msg.get("result", {})


def launch(width, height):
    port = 9400 + (os.getpid() % 400)
    prof = tempfile.mkdtemp(prefix="edgeprev_")
    proc = subprocess.Popen([
        EDGE, "--headless=new", "--disable-gpu", "--no-sandbox",
        "--hide-scrollbars", "--remote-allow-origins=*",
        f"--remote-debugging-port={port}", f"--user-data-dir={prof}",
        f"--window-size={width},{height}", "about:blank",
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return proc, port


# ---------------------------------------------------------------- 页面脚本
JS_TEXT_BOXES = r"""
JSON.stringify((() => {
  const out = [];
  document.querySelectorAll('#texts .t').forEach(el => {
    const r = el.getBoundingClientRect();
    if (r.width < 4 || r.height < 4) return;
    const cs = getComputedStyle(el);
    if (parseFloat(cs.opacity) < 0.02) return;
    out.push({
      cls: el.className,
      tier: (el.className.match(/tier-(T\d)/) || [])[1] || '?',
      x: r.x, y: r.y, w: r.width, h: r.height,
      text: (el.innerText || '').replace(/\n/g, ' ').slice(0, 40)
    });
  });
  return out;
})())
"""

JS_CANVAS_SIZE = ("JSON.stringify((() => { const s = document.getElementById('stage')"
                  ".getBoundingClientRect(); return {w:s.width,h:s.height}; })())")


# ---------------------------------------------------------------- 检测
def check_boxes(boxes, stage_w, stage_h):
    issues = []
    n = len(boxes)
    for i in range(n):
        a = boxes[i]
        # 越界
        if (a["x"] < SAFE["x0"] * stage_w - 1 or a["y"] < SAFE["y0"] * stage_h - 1 or
                a["x"] + a["w"] > SAFE["x1"] * stage_w + 1 or a["y"] + a["h"] > SAFE["y1"] * stage_h + 1):
            issues.append(f"越界: {a['tier']} 「{a['text']}」")
        # 重叠
        for j in range(i + 1, n):
            b = boxes[j]
            ox = min(a["x"] + a["w"], b["x"] + b["w"]) - max(a["x"], b["x"])
            oy = min(a["y"] + a["h"], b["y"] + b["h"]) - max(a["y"], b["y"])
            if ox > 2 and oy > 2:
                issues.append(f"重叠: {a['tier']} 与 {b['tier']} 交叠 {int(ox)}×{int(oy)}px")
            else:
                gap = max(-ox, -oy)
                if 0 <= gap < MIN_GAP and ox > 0:
                    issues.append(f"过近: {a['tier']}/{b['tier']} 间距 {int(gap)}px")
    return issues


def check_contrast(img_bgr, boxes, stage_w, stage_h):
    """采样文字框两侧的背景亮度，判断对比度"""
    import numpy as np
    issues = []
    H, W = img_bgr.shape[:2]
    for b in boxes:
        # 取文字块左右各 40px 的背景带
        y0 = int(b["y"] / stage_h * H); y1 = int((b["y"] + b["h"]) / stage_h * H)
        xr = int((b["x"] + b["w"]) / stage_w * W)
        x0 = max(0, xr + 4); x1 = min(W, xr + 44)
        if x1 - x0 < 4 or y1 - y0 < 4:
            continue
        patch = img_bgr[y0:y1, x0:x1]
        bg = float(patch.mean()) / 255.0
        # 主字幕是浅色，背景越亮对比越差
        if bg > 0.62:
            issues.append(f"对比度低: {b['tier']} 「{b['text']}」 背景亮度 {bg:.2f}")
    return issues


# ---------------------------------------------------------------- 主流程
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("edl")
    ap.add_argument("--per-shot", type=int, default=3, help="每镜取几个时间点")
    ap.add_argument("--width", type=int, default=1920)
    ap.add_argument("--height", type=int, default=1080)
    ap.add_argument("--out", default=None)
    a = ap.parse_args()

    edl_abs = os.path.abspath(a.edl)
    out_dir = a.out or os.path.join(os.path.dirname(HERE), "out", "preview")
    os.makedirs(out_dir, exist_ok=True)
    # 清理上次的静帧，避免不同片子的帧混进总览图
    for f in os.listdir(out_dir):
        if f.endswith(".jpg"):
            try:
                os.remove(os.path.join(out_dir, f))
            except OSError:
                pass

    # 1) 构建
    page = os.path.join(out_dir, "preview.html")
    from build import main as build_main
    import io as _io
    edl = json.load(open(edl_abs, encoding="utf-8"))
    build_main(edl_abs, page)
    url = "file:///" + urllib.request.quote(page.replace("\\", "/"), safe="/:")

    # 2) 启动
    proc, port = launch(a.width, a.height)
    issues_all, shots_qc = [], []
    try:
        cdp = CDP(port)
        cdp.send("Emulation.setDeviceMetricsOverride",
                 {"width": a.width, "height": a.height, "deviceScaleFactor": 1, "mobile": False})
        cdp.send("Page.navigate", {"url": url})
        for _ in range(100):
            r = cdp.send("Runtime.evaluate", {"expression": "!!window.__ready", "returnByValue": True})
            if r.get("result", {}).get("value"):
                break
            time.sleep(0.1)

        # 舞台固定 1920x1080，视口同尺寸，坐标系一致
        sw, sh = 1920.0, 1080.0

        shot_clock = 0
        total_shots = len(edl["shots"])
        for shot in edl["shots"]:
            t0, t1 = shot["t0"], shot["t1"]
            span = t1 - t0
            times = [t0 + span * (k + 0.5) / a.per_shot for k in range(a.per_shot)]
            sh_issues = []
            for t in times:
                cdp.send("Runtime.evaluate", {
                    "expression": "new Promise(r=>{__film.seek(%f);requestAnimationFrame(()=>requestAnimationFrame(()=>r(1)))})" % t,
                    "awaitPromise": True})
                rawb = cdp.send("Runtime.evaluate", {"expression": JS_TEXT_BOXES, "returnByValue": True})["result"]["value"]
                boxes = json.loads(rawb) if isinstance(rawb, str) else rawb
                iss = check_boxes(boxes, sw, sh)
                cap = cdp.send("Page.captureScreenshot", {"format": "jpeg", "quality": 86})
                raw = base64.b64decode(cap["data"])
                fn = f"{shot['id']}_{t:.1f}s.jpg"
                open(os.path.join(out_dir, fn), "wb").write(raw)
                # 素材是否真的加载（0 = 图挂了，画面会近乎全黑）
                if shot.get("asset"):
                    nw = cdp.send("Runtime.evaluate", {
                        "expression": "JSON.stringify([...document.querySelectorAll('#asset-wrap img')]"
                                      ".map(i=>i.naturalWidth))",
                        "returnByValue": True})["result"]["value"]
                    widths = json.loads(nw) if isinstance(nw, str) else nw
                    if not widths or max(widths) == 0:
                        iss.append("素材未加载（图片 naturalWidth=0）")
                # 对比度 + 亮度
                try:
                    import cv2
                    import numpy as np
                    img = cv2.imdecode(np.frombuffer(raw, np.uint8), cv2.IMREAD_COLOR)
                    iss += check_contrast(img, boxes, sw, sh)
                    luma = float(cv2.cvtColor(img, cv2.COLOR_BGR2GRAY).mean())
                    # 有素材的镜头应该更亮一点，否则说明图没出来
                    floor = 14 if shot.get("asset") else LUMA_MIN
                    if luma < floor:
                        iss.append(f"过暗: 平均亮度 {luma:.0f}（下限 {floor}）")
                    if luma > LUMA_MAX:
                        iss.append(f"过亮: 平均亮度 {luma:.0f}")
                except Exception:
                    luma = None
                for i in iss:
                    issues_all.append(f"{shot['id']} @{t:.1f}s  {i}")
                sh_issues += iss
            shot_clock += 1
            print(f"  [{shot_clock}/{total_shots}] {shot['id']:6s} {t0:5.0f}-{t1:5.0f}s  "
                  f"{'OK' if not sh_issues else str(len(sh_issues)) + ' 问题'}", flush=True)
            shots_qc.append({"id": shot["id"], "issues": sh_issues})
    finally:
        try:
            proc.terminate()
        except Exception:
            pass

    # 3) 汇总
    qc = {"film": os.path.basename(edl_abs), "shots": shots_qc,
          "total_issues": len(issues_all), "issues": issues_all}
    json.dump(qc, open(os.path.join(out_dir, "qc.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)

    # 4) 总览图
    try:
        from PIL import Image
        fs = sorted([f for f in os.listdir(out_dir) if f.endswith(".jpg") and f != "sheet.jpg"])
        if fs:
            cols, W, H = 5, 320, 180
            rows = (len(fs) + cols - 1) // cols
            sheet = Image.new("RGB", (cols * W, rows * H), (8, 9, 12))
            for i, f in enumerate(fs):
                im = Image.open(os.path.join(out_dir, f)).convert("RGB").resize((W, H))
                sheet.paste(im, ((i % cols) * W, (i // cols) * H))
            sheet.save(os.path.join(out_dir, "sheet.jpg"), quality=88)
    except Exception as e:
        print("总览图生成失败:", e)

    print(f"\n共 {len(edl['shots'])} 镜 / {len(issues_all)} 个问题")
    for i in issues_all[:40]:
        print("  [x]", i)
    if len(issues_all) > 40:
        print(f"  … 另有 {len(issues_all)-40} 条")
    print(f"\n产物: {out_dir}")
    return 1 if issues_all else 0


if __name__ == "__main__":
    sys.exit(main())
