---
name: documentary-engine
description: "用代码做纪录片级短片：写 EDL 分镜或用镜头库装配，自动校验、渲前质检、逐帧渲染、合成配乐，产出 1080p 成片。含图形摄像机（推拉/视差/拉伸）、六层字幕、21 种程序图形、四类量化质检与一个主控 CLI。当用户要做「有电影感的科普/纪实短片」「用代码而不是剪辑软件做视频」「把一段文案变成成片」时触发。"
license: MIT
type: tool
tags: ["documentary", "video", "code-animation", "edl", "storyboard", "canvas", "qc"]
---

# 纪录片引擎

用代码做「纪录片级」短片。输入是一份 **EDL（分镜数据）**，输出是 MP4。

**核心原则：渲染器不认识故事。** 所有创作决定都在 EDL 里，代码只负责执行。

---

## 两种用法

### A. 用镜头库装配（推荐）

```python
from director.film import Film
from director.assets import AssetTable
from director import shots as S

A = AssetTable()
A.add("europa", "assets/galileo/europa-PIA19048.jpg", "欧罗巴表面")

f = Film({...骨架...})
f.add(S.archive("s01", "a1", 0, 8, "europa", "jade",
                caption="NASA · 欧罗巴", lines=["木星旁边 有一颗月亮"]))
f.add(S.ending("s02", "a2", 8, 8, lines=["我们还没有到过那里"]))
f.finalize().save("examples/新片.json")
```

然后：

```bash
python film.py check   examples/新片.json
python film.py preview examples/新片.json
python film.py all     examples/新片.json
```

### C. 从剧本生成草案（最快）

写一份 30 行的剧本（`scripts/galileo.script.json` 是模板），引擎自动算时长、
选镜头类型、染金数字、补暗素材亮度、归一总长：

```bash
python film.py draft scripts/新片.script.json --duration 180
python film.py check   examples/新片-draft.json
python film.py preview examples/新片-draft.json
```

详见 `director/DRAFT.md`。

### B. 直接写 EDL

照 `examples/galileo.json` 改。字段规范见 `schemas/edl.schema.json`。

---

## 主控

```bash
python film.py new      <路径>     建骨架
python film.py check    <edl>      结构 + 风格（<2 秒）
python film.py preview  <edl>      渲前质检（30 秒）
python film.py render   <edl>      只渲染
python film.py all      <edl>      一路到成片
python film.py video    <edl> <成片>  视频级质检
python film.py selftest           质检器自检（9 项）
```

`all` = lint → style → preview → build → render → score → encode → compare。
任一环节失败即停。

---

## 模块

| 模块 | 职责 | 关键文件 |
|---|---|---|
| `director/` | 编排：EDL、镜头库、素材登记 | `film.py` `shots.py` `assets.py` |
| `render/engine/` | 渲染：只认 EDL | `render.html` `js/*.js` |
| `qc/` | 质检：结构 / 排版 / 色彩 / 指标 | `lint.py` `preview.py` `style.py` `compare.py` |
| `io/` | 输入输出：页面 / 截图 / 编码 / 配乐 | `build.py` `capture.py` `encode.py` `score.py` |

**改片子只动 `director/`。** 引擎与质检器是稳定的。

---

## EDL 关键字段

```json
{
  "meta":   { "title": "…", "duration": 180, "fps": 30, "resolution": [1920,1080] },
  "assets": [ { "id": "…", "src": "assets/…jpg", "license": "public-domain", "source_url": "…" } ],
  "moods":  { "amber": { "lift": [...], "tint": [...], "sat": 0.9, "hue": 45 } },
  "acts":   [ { "id": "a1", "t0": 0, "t1": 40, "mood": "amber" } ],
  "shots":  [ { "id": "s01", "t0": 0, "t1": 10, "asset": "…", "texts": [...], "graphics": [...] } ],
  "audio":  { "track": {...}, "envelope": [ { "t": 0, "gain": 0.1 } ] }
}
```

### 镜头字段

| 字段 | 作用 |
|---|---|
| `asset` | 素材 id；纯图形镜头为 `null` |
| `motion` | `kenburns`（zoom 0.02–0.06）/ `static` |
| `optics` | `perspective` / `rotate` / `crop` |
| `grade` | 覆盖所在幕的 mood |
| `brightness` | 逐镜亮度；纯图形镜头建议 1.7–2.1 |
| `camera` | 图形摄像机（见下） |
| `texts` / `graphics` | 见下 |

### 六层字幕

| tier | 用途 |
|---|---|
| T1 | 叙事主字幕（宋体，白 + 金色关键词，画面 76% 起） |
| T2 | 引语 |
| T3 | 数据标注 |
| T4 | 角落计数 |
| T5 | 资料出处 |
| T6 | 时间刻度 |

- `accent: ["关键词"]` 染色，每句 1–2 个概念词或数字
- `mode: "accumulate"` 同一句逐段接续，不整句弹

### 图形摄像机

```json
"camera": { "s0": 1.0, "s1": 1.26,
            "sx0": 1.0, "sx1": 1.32, "sy0": 1.0, "sy1": 1.22,
            "t0": 0.2, "t1": 4.8, "ease": "easeInOut",
            "cy": 0.44, "parallax": 0.6 }
```

### 图形元素

```json
{ "kind": "wave_stack", "depth": 0.7, "t0": 0.15,
  "params": { "n": 15, "stagger": 0.04 } }
```

- `depth` 越小越远 → 推近时动得少，产生视差
- `t0` 起始秒
- `overlay: true` 不参与摄像机变换（坐标轴、数字）

### 21 种 kind

| 类别 | kind |
|---|---|
| 网格/轴 | `grid2d` `polar_grid` `ring_ticks` `axis_ticks` `timeline_axis` `axis_labels` |
| 线/光 | `vline` `hline` `light_streak` `beam_array` `highlight_box` |
| 数据 | `iso_bars` `scatter_axis` `curve_fit` `counter` `progress_ring` `checklist` |
| 粒子/空间 | `particles_3d` `starfield` `aurora` `bokeh` `embers` |
| 信号 | `wave_stack` `code_wall` |

---

## 质检

### lint.py（结构）

字幕 ≤22 字、阅读速度 2.0–5.5 字/秒、推拉 0.2–1.5%/秒、素材必须有 license + source_url、镜长对比 ≥3 倍、幕间色相跨度 ≥60°。

### preview.py（渲前排版，30 秒）

文字重叠 >2px、越界 4% 安全区、间距 <6px、字幕对比度（背景亮度 >0.62）、单镜亮度 <8 或 >92。

### style.py（色彩与观感）

饱和度 >0.62、纯图形镜头 brightness <1.4、幕内亮度极差 >18、幕间色相 <45°、连续 >3 镜同向推拉。带帧目录跑还会打印逐镜亮度/饱和度。

### video.py（渲后，时间维度）

闪烁 / 卡顿 / 意外硬切 / 字幕抖动 / 黑场 / 节奏塌方 / 削波 / 静音。
详见 `qc/VIDEO.md`。自带单元测试：`python film.py selftest`。

### compare.py（渲后指标）

| 指标 | 目标 |
|---|---|
| frame_diff | ≥ 1.5 |
| moving | ≥ 0.70 |
| coverage | ≥ 0.20 |
| luma | 16–30 |

**测源帧，不要测编码后的视频。**

---

## 已知限制

| 限制 | 说明 |
|---|---|
| 渲染 | 串行 0.4–1.2 秒/帧；2 实例并行 3.7×；改单镜走增量约 1 分钟 |
| 图形 | 21 个 kind，无真三维 |
| 素材 | 只有 NASA API 内置 |
| 音频 | 只能裁切 + 包络 |
| 自动回环 | 质检能报错，不能自动改 |

---

## 常见坑

1. **别用 `ctx.shadowBlur`** —— 软件渲染 5 秒/帧，用 `bloom()`。
2. **字幕时长用 `retime`/`spread` 算**，别手写。
3. **累积式字幕必须预留空间**，否则第二行出现时整块跳 85px。
4. **调色只作用 `#world` 层**，否则绿色场景字幕变绿。
5. **纯图形镜头要 `brightness ≥ 1.7`**，否则黑成一片。
6. **hue-rotate 超过 30° 会毁掉素材原色**（伽利略第三幕教训，改用 `jade`）。
7. **渲前先跑 preview**，40 分钟冤枉路走一次就够。改完 EDL 直接重跑 render，会自动增量。
8. **调色分级可以后置到编码**（`eq=gamma=`），不必重渲。
9. **成片覆盖率 < 0.15 一定是素材没加载**——不是「暗调美学」。抽出第一帧看一眼再交付。引擎已加两道闸：build 缺文件硬报错、preview 查 `naturalWidth` 与逐镜亮度下限。

---

## 目录

```
film.py               主控 CLI
director/             编排层（改片子只动这里）
render/engine/        渲染器
qc/                   质检
io/                   输入输出
schemas/              EDL 规范
reference/            阈值、图形语言分析
examples/             示例分镜（voyager / galileo / demo-europa）
assets/               素材（NASA 抓取脚本 + 已下载图片）
```
