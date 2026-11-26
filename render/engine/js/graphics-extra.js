/* ==================================================================
   graphics-extra.js — 第二批图形 kind：数据与空间
   依赖 graphics.js 里的 registerKind / rng / easeOut / clamp01
   ================================================================== */
'use strict';

/** 等距柱状图 + 拟合曲线 */
registerKind('iso_bars', (ctx, local, p) => {
  const n = p.count || 18;
  const r = rng(p.seed || 23);
  const cx = (p.x == null ? 0.5 : p.x) * W;
  const cy = (p.y == null ? 0.62 : p.y) * H;
  const bw = (p.barW || 26), gap = (p.gap || 34);
  const hMax = (p.hMax || 210);
  const skew = 0.82, tilt = 0.42;
  const rise = easeOut(clamp01(local / (p.dur || 1.8)));
  const vals = [];
  for (let i = 0; i < n; i++) {
    const u = (i + 0.5) / n;
    const g = Math.exp(-Math.pow((u - 0.46) / 0.22, 2));
    vals.push(g * (0.85 + r() * 0.3));
  }
  for (let i = 0; i < n; i++) {
    const x = cx + (i - n / 2) * gap;
    const h = vals[i] * hMax * rise;
    const topY = cy - h;
    ctx.fillStyle = 'rgba(70,190,150,0.50)';
    ctx.beginPath();
    ctx.moveTo(x, cy);
    ctx.lineTo(x + bw * skew, cy - bw * tilt * 0.5);
    ctx.lineTo(x + bw * skew, topY - bw * tilt * 0.5);
    ctx.lineTo(x, topY);
    ctx.closePath(); ctx.fill();
    ctx.fillStyle = 'rgba(46,160,128,0.72)';
    ctx.beginPath();
    ctx.moveTo(x, topY);
    ctx.lineTo(x + bw * skew, topY - bw * tilt * 0.5);
    ctx.lineTo(x + bw, topY);
    ctx.lineTo(x + bw - bw * skew, topY + bw * tilt * 0.5);
    ctx.closePath(); ctx.fill();
    ctx.fillStyle = 'rgba(34,120,98,0.50)';
    ctx.beginPath();
    ctx.moveTo(x + bw, cy);
    ctx.lineTo(x + bw * skew, cy - bw * tilt * 0.5);
    ctx.lineTo(x + bw * skew, topY - bw * tilt * 0.5);
    ctx.lineTo(x + bw, topY);
    ctx.closePath(); ctx.fill();
  }
  ctx.strokeStyle = 'rgba(232,200,122,0.85)';
  ctx.lineWidth = 2;
  ctx.beginPath();
  for (let i = 0; i <= 60; i++) {
    const u = i / 60;
    const g = Math.exp(-Math.pow((u - 0.46) / 0.22, 2));
    const x = cx + (u * n - n / 2) * gap;
    const y = cy - g * hMax * rise * 0.98 - bw * tilt * 0.25;
    i ? ctx.lineTo(x, y) : ctx.moveTo(x, y);
  }
  ctx.stroke();
});

/** 光柱阵：向消失点收束的一排竖光 */
registerKind('beam_array', (ctx, local, p) => {
  const n = p.count || 9;
  const vpx = (p.vx == null ? 0.5 : p.vx) * W;
  const vpy = (p.vy == null ? 0.34 : p.vy) * H;
  const hue = p.hue || '120,240,190';
  for (let i = 0; i < n; i++) {
    const t = i / Math.max(1, n - 1);
    const x = vpx + (i - (n - 1) / 2) * (W * 0.11) * (0.35 + t);
    const botY = H * (0.55 + 0.42 * t);
    const w = 2 + t * 12;
    const a = (0.10 + 0.22 * (1 - t)) * (0.75 + 0.25 * Math.sin(local * 1.6 + i));
    const g = ctx.createLinearGradient(x, 0, x, botY);
    g.addColorStop(0, 'rgba(' + hue + ',' + (a * 0.2).toFixed(3) + ')');
    g.addColorStop(0.55, 'rgba(' + hue + ',' + a.toFixed(3) + ')');
    g.addColorStop(1, 'rgba(' + hue + ',0)');
    ctx.fillStyle = g;
    ctx.fillRect(x - w / 2, 0, w, botY);
  }
  const rg = ctx.createRadialGradient(vpx, vpy, 0, vpx, vpy, H * 0.5);
  rg.addColorStop(0, 'rgba(' + hue + ',0.16)');
  rg.addColorStop(1, 'rgba(' + hue + ',0)');
  ctx.fillStyle = rg;
  ctx.beginPath(); ctx.arc(vpx, vpy, H * 0.5, 0, 7); ctx.fill();
});

/** 代码墙：滚动的等宽字符流 */
registerKind('code_wall', (ctx, local, p) => {
  const r = rng(p.seed || 41);
  const size = p.size || 15;
  const cols = Math.ceil(W / (size * 0.62));
  const rows = Math.ceil(H / (size * 1.35)) + 2;
  const alpha = p.alpha == null ? 0.22 : p.alpha;
  const scroll = (local * (p.speed || 26)) % (size * 1.35);
  ctx.font = size + 'px Consolas, monospace';
  ctx.textAlign = 'left';
  const chars = '01[]{}()<>/=+-*:;.,abcdef0123456789';
  const dens = p.density || 0.42;
  for (let ry = 0; ry < rows; ry++) {
    for (let cxi = 0; cxi < cols; cxi++) {
      if (r() > dens) continue;
      const ch = chars[Math.floor(r() * chars.length)];
      const a = alpha * (0.35 + r() * 0.65);
      ctx.fillStyle = 'rgba(150,220,190,' + a.toFixed(3) + ')';
      ctx.fillText(ch, cxi * size * 0.62, ry * size * 1.35 - scroll);
    }
  }
});

/** 散点轴：横轴上的一串点 */
registerKind('scatter_axis', (ctx, local, p) => {
  const y = (p.y == null ? 0.62 : p.y) * H;
  const x0 = (p.x0 == null ? 0.1 : p.x0) * W;
  const x1 = (p.x1 == null ? 0.9 : p.x1) * W;
  const n = p.count || 60;
  const r = rng(p.seed || 61);
  const rise = easeOut(clamp01(local / (p.dur || 1.5)));
  ctx.strokeStyle = 'rgba(210,220,235,0.30)';
  ctx.lineWidth = 1;
  ctx.beginPath(); ctx.moveTo(x0, y); ctx.lineTo(x1, y); ctx.stroke();
  for (let i = 0; i < n; i++) {
    const u = (p.mode === 'regular') ? (i + 1) / (n + 1) : Math.pow(r(), 0.7);
    if (u > rise) continue;
    const x = x0 + (x1 - x0) * u;
    const a = 0.35 + r() * 0.5;
    ctx.fillStyle = 'rgba(232,214,180,' + a.toFixed(3) + ')';
    ctx.beginPath(); ctx.arc(x, y, 1.8 + r() * 1.4, 0, 7); ctx.fill();
  }
});

/** 时间轴：等距刻度 + 高亮当前节点 */
registerKind('timeline_axis', (ctx, local, p) => {
  const y = (p.y == null ? 0.78 : p.y) * H;
  const x0 = (p.x0 == null ? 0.12 : p.x0) * W;
  const x1 = (p.x1 == null ? 0.88 : p.x1) * W;
  const marks = p.marks || ['1977', '1979', '1980', '1986', '1989', '2012', '2026'];
  const active = p.active == null ? marks.length - 1 : p.active;
  const rise = easeOut(clamp01(local / (p.dur || 1.2)));
  ctx.strokeStyle = 'rgba(210,220,235,0.28)';
  ctx.lineWidth = 1;
  ctx.beginPath(); ctx.moveTo(x0, y); ctx.lineTo(x0 + (x1 - x0) * rise, y); ctx.stroke();
  ctx.font = '17px "Noto Serif SC", serif';
  ctx.textAlign = 'center';
  for (let i = 0; i < marks.length; i++) {
    const x = x0 + (x1 - x0) * (i / (marks.length - 1));
    if (x > x0 + (x1 - x0) * rise + 1) continue;
    const on = (i === active);
    ctx.fillStyle = on ? 'rgba(232,200,122,0.95)' : 'rgba(200,210,225,0.42)';
    ctx.beginPath(); ctx.arc(x, y, on ? 4 : 2.2, 0, 7); ctx.fill();
    ctx.fillStyle = on ? 'rgba(240,228,200,0.92)' : 'rgba(190,200,215,0.45)';
    ctx.fillText(marks[i], x, y + 26);
  }
});

/** 勾选清单 */
registerKind('checklist', (ctx, local, p) => {
  const items = p.items || ['校验通过', '签名一致'];
  const x = (p.x == null ? 0.12 : p.x) * W;
  const y0 = (p.y == null ? 0.30 : p.y) * H;
  ctx.font = '22px "Noto Serif SC", serif';
  ctx.textAlign = 'left';
  for (let i = 0; i < items.length; i++) {
    const t = local - i * 0.45;
    if (t < 0) continue;
    const a = Math.min(1, t / 0.35);
    const yy = y0 + i * 44;
    ctx.strokeStyle = 'rgba(120,220,170,' + (0.9 * a).toFixed(3) + ')';
    ctx.lineWidth = 2;
    ctx.beginPath(); ctx.moveTo(x, yy - 6); ctx.lineTo(x + 8, yy + 3); ctx.lineTo(x + 20, yy - 14); ctx.stroke();
    ctx.fillStyle = 'rgba(225,232,240,' + (0.85 * a).toFixed(3) + ')';
    ctx.fillText(items[i], x + 34, yy);
  }
});
