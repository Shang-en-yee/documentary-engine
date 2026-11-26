/* ==================================================================
   graphics.js — L2b 程序图形层
   kind 注册表。引擎主干不认识任何具体视觉，只按 kind 分发。
   ================================================================== */
'use strict';

const GRAPHICS = {};
let gctx = null;

function graphicsInit(ctx) { gctx = ctx; }

function registerKind(name, fn) { GRAPHICS[name] = fn; }

/** 主分发 */
function drawGraphics(shot, local, t) {
  const cv = document.getElementById('graphics');
  if (!gctx) return;
  gctx.clearRect(0, 0, W, H);
  const list = shot.graphics || [];
  for (const g of list) {
    const fn = GRAPHICS[g.kind];
    if (!fn) { console.warn('未实现的图形 kind:', g.kind); continue; }
    fn(gctx, local, g.params || {}, shot, t);
  }
  if (list.length) bloom(gctx, 0.75);
}

/* ---------------- 具体 kind ---------------- */

/** 竖线发光（临界线） */
registerKind('vline', (ctx, local, p) => {
  const x = (p.x == null ? 0.5 : p.x) * W;
  const g = ctx.createLinearGradient(0, 0, 0, H);
  g.addColorStop(0, 'rgba(232,200,122,0)');
  g.addColorStop(0.12, 'rgba(255,240,200,0.85)');
  g.addColorStop(0.9, 'rgba(232,200,122,0.25)');
  g.addColorStop(1, 'rgba(232,200,122,0)');
  ctx.strokeStyle = g;
  ctx.lineWidth = p.width || 2.2;
  ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, H); ctx.stroke();
});

/** 二维网格（数学底纹） */
registerKind('grid2d', (ctx, local, p) => {
  const sp = p.spacing || 46;
  const a = (p.alpha == null ? 0.06 : p.alpha);
  ctx.strokeStyle = `rgba(150,178,220,${a})`;
  ctx.lineWidth = 1;
  for (let x = 0; x <= W; x += sp) {
    ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, H); ctx.stroke();
  }
  for (let y = 0; y <= H; y += sp) {
    ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(W, y); ctx.stroke();
  }
});

/** 计数器：数字从 from 递增到 to */
registerKind('counter', (ctx, local, p) => {
  const dur = p.dur || 3;
  const k = easeOut(clamp01(local / dur));
  const v = (p.from || 0) + (p.to - (p.from || 0)) * k;
  const txt = p.format === 'comma'
    ? Math.round(v).toLocaleString('en-US')
    : Math.round(v).toString();
  ctx.save();
  ctx.font = `${p.size || 76}px "Noto Serif SC", serif`;
  ctx.fillStyle = p.color || 'rgba(255,246,230,0.96)';
  ctx.textAlign = 'center';
  ctx.fillText(txt, (p.x == null ? 0.5 : p.x) * W, (p.y == null ? 0.5 : p.y) * H);
  ctx.restore();
});

/** 进度环 */
registerKind('progress_ring', (ctx, local, p) => {
  const dur = p.dur || 3;
  const k = easeInOut(clamp01(local / dur));
  const cx = (p.x == null ? 0.5 : p.x) * W, cy = (p.y == null ? 0.5 : p.y) * H;
  const r = p.r || 150;
  ctx.save();
  ctx.strokeStyle = 'rgba(200,205,215,0.16)';
  ctx.lineWidth = 2;
  ctx.beginPath(); ctx.arc(cx, cy, r, 0, Math.PI * 2); ctx.stroke();
  ctx.strokeStyle = 'rgba(232,200,122,0.92)';
  ctx.lineWidth = 3.4;
  ctx.lineCap = 'round';
  ctx.beginPath();
  ctx.arc(cx, cy, r, -Math.PI / 2, -Math.PI / 2 + Math.PI * 2 * k);
  ctx.stroke();
  ctx.restore();
});

/** 3D 粒子场（透视 + 景深） */
registerKind('particles_3d', (ctx, local, p) => {
  const n = p.count || 200;
  const r = rng(p.seed || 7);
  const camZ = p.dist || 6;
  const f = 900;
  const spread = p.spread || 1;
  const pts = [];
  for (let i = 0; i < n; i++) {
    const x = (r() - 0.5) * 16 * spread;
    const y = (r() - 0.5) * 9 * spread;
    const z = (r() - 0.5) * 14 * spread;
    const drift = (local * (0.05 + r() * 0.12));
    const zz = z + camZ + drift;
    if (zz <= 0.1) continue;
    pts.push([W / 2 + x * f / zz, H / 2 + y * f / zz, zz, r()]);
  }
  pts.sort((a, b) => b[2] - a[2]);
  for (const [sx, sy, zz, rnd] of pts) {
    const rad = Math.max(0.4, Math.min(3.2, 5.5 / zz));
    const a = Math.min(0.85, 0.9 / zz) * (0.6 + 0.4 * Math.sin(local * 2 + rnd * 9));
    ctx.fillStyle = `rgba(212,228,255,${a.toFixed(3)})`;
    ctx.beginPath(); ctx.arc(sx, sy, rad, 0, 7); ctx.fill();
  }
});

/** bokeh 虚焦光斑 */
registerKind('bokeh', (ctx, local, p) => {
  const n = p.count || 10;
  const r = rng(p.seed || 31);
  for (let i = 0; i < n; i++) {
    const x = r() * W, y = r() * H;
    const rad = (p.radius ? p.radius[0] + r() * (p.radius[1] - p.radius[0]) : 120);
    const a = (p.alpha || 0.1) * (0.6 + 0.4 * Math.sin(local * 0.5 + i));
    const g = ctx.createRadialGradient(x, y, 0, x, y, rad);
    g.addColorStop(0, `rgba(255,214,150,${a})`);
    g.addColorStop(1, 'rgba(255,214,150,0)');
    ctx.fillStyle = g;
    ctx.beginPath(); ctx.arc(x, y, rad, 0, 7); ctx.fill();
  }
});


/** 高亮框：四角括号 + 可选标签（画在指定归一化位置） */
registerKind('highlight_box', (ctx, local, p) => {
  const cx = (p.x == null ? 0.5 : p.x) * W;
  const cy = (p.y == null ? 0.5 : p.y) * H;
  const bw = (p.w == null ? 0.1 : p.w) * W;
  const bh = (p.h == null ? 0.1 : p.h) * H;
  const grow = easeOut(clamp01(local / 0.7));
  const L = Math.min(bw, bh) * 0.28 * grow;
  ctx.strokeStyle = 'rgba(232,200,122,0.85)';
  ctx.lineWidth = 1.6;
  const x0 = cx - bw / 2, x1 = cx + bw / 2, y0 = cy - bh / 2, y1 = cy + bh / 2;
  const corners = [[x0, y0, 1, 1], [x1, y0, -1, 1], [x0, y1, 1, -1], [x1, y1, -1, -1]];
  for (const [x, y, sx, sy] of corners) {
    ctx.beginPath();
    ctx.moveTo(x, y + sy * L); ctx.lineTo(x, y); ctx.lineTo(x + sx * L, y);
    ctx.stroke();
  }
  if (p.label) {
    ctx.fillStyle = 'rgba(232,200,122,0.9)';
    ctx.font = '17px "Noto Serif SC", serif';
    ctx.textAlign = 'left';
    ctx.fillText(p.label, x1 + 16, y0 + 18);
  }
});


/* ---------------- 氛围类 kind：解决"画面静" ---------------- */

/** 星野：缓慢漂移的远景星点，给空间镜头加一层纵深 */
registerKind('starfield', (ctx, local, p) => {
  const n = p.count || 240;
  const r = rng(p.seed || 17);
  const drift = (p.drift == null ? 6 : p.drift);
  ctx.save();
  for (let i = 0; i < n; i++) {
    const bx = r() * W, by = r() * H;
    const z = 0.25 + r() * 0.75;
    const x = ((bx + local * drift * z) % (W + 40)) - 20;
    const y = (by + Math.sin(local * 0.3 + i) * 3 * z);
    const rad = 0.5 + z * 1.5;
    const a = (0.10 + r() * 0.45) * z * (0.7 + 0.3 * Math.sin(local * 1.6 + i));
    ctx.fillStyle = 'rgba(214,228,255,' + a.toFixed(3) + ')';
    ctx.beginPath(); ctx.arc(x, y, rad, 0, 7); ctx.fill();
  }
  ctx.restore();
});

/** 极光带：地平线附近缓慢起伏的发光带 */
registerKind('aurora', (ctx, local, p) => {
  const cy = (p.y == null ? 0.55 : p.y) * H;
  const h = (p.height == null ? 0.18 : p.height) * H;
  const amp = (p.amp == null ? 26 : p.amp);
  const hue = p.hue || '60,220,170';
  for (let layer = 0; layer < 3; layer++) {
    const off = local * (6 + layer * 4);
    ctx.beginPath();
    ctx.moveTo(0, H);
    for (let x = 0; x <= W; x += 24) {
      const y = cy + layer * 14
        + Math.sin((x + off * 3) / 260 + layer) * amp
        + Math.sin((x - off) / 90 + layer * 2) * amp * 0.35;
      ctx.lineTo(x, y);
    }
    ctx.lineTo(W, H); ctx.closePath();
    const g = ctx.createLinearGradient(0, cy - h, 0, cy + h);
    g.addColorStop(0, 'rgba(' + hue + ',0)');
    g.addColorStop(0.45, 'rgba(' + hue + ',' + (0.16 - layer * 0.04) + ')');
    g.addColorStop(1, 'rgba(' + hue + ',0)');
    ctx.fillStyle = g;
    ctx.fill();
  }
});

/** 光柱：从一点向上升起的细光束 + 上升粒子 */
registerKind('light_streak', (ctx, local, p) => {
  const x = (p.x == null ? 0.5 : p.x) * W;
  const y0 = (p.y == null ? 0.72 : p.y) * H;
  const w = p.width || 4;
  const g = ctx.createLinearGradient(0, y0, 0, 0);
  g.addColorStop(0, 'rgba(232,200,122,0.55)');
  g.addColorStop(0.5, 'rgba(255,240,205,0.22)');
  g.addColorStop(1, 'rgba(232,200,122,0)');
  ctx.fillStyle = g;
  ctx.fillRect(x - w / 2, 0, w, y0);
  // 光晕
  const rg = ctx.createRadialGradient(x, y0, 0, x, y0, 120);
  rg.addColorStop(0, 'rgba(255,244,214,0.30)');
  rg.addColorStop(1, 'rgba(255,244,214,0)');
  ctx.fillStyle = rg;
  ctx.beginPath(); ctx.arc(x, y0, 120, 0, 7); ctx.fill();
  // 上升粒子
  const r = rng(p.seed || 5);
  for (let i = 0; i < (p.motes || 40); i++) {
    const sp = 0.06 + r() * 0.16;
    const yy = y0 - ((local * sp * H + r() * y0) % y0);
    const xx = x + (r() - 0.5) * 60 * (1 - yy / y0);
    const a = 0.50 * (yy / y0) * (0.6 + 0.4 * Math.sin(local * 3 + i));
    ctx.fillStyle = 'rgba(255,238,200,' + a.toFixed(3) + ')';
    ctx.beginPath(); ctx.arc(xx, yy, 1.6, 0, 7); ctx.fill();
  }
});

/** 余烬：从下方升起的火星（发射镜头用） */
registerKind('embers', (ctx, local, p) => {
  const r = rng(p.seed || 3);
  const n = p.count || 70;
  for (let i = 0; i < n; i++) {
    const sp = 0.05 + r() * 0.2;
    const y = H - ((local * sp * H + r() * H) % (H * 1.1));
    const x = (p.x0 == null ? 0.25 : p.x0) * W + r() * (H * 0.55);
    const a = 0.55 * (y / H) * (0.5 + 0.5 * Math.sin(local * 4 + i * 1.7));
    ctx.fillStyle = 'rgba(255,206,140,' + a.toFixed(3) + ')';
    ctx.beginPath(); ctx.arc(x, y, 1.4 + r() * 1.4, 0, 7); ctx.fill();
  }
});
