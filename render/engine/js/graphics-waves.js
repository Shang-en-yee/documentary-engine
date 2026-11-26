/* ==================================================================
   graphics-waves.js — 参考片「零点→波→质数阶梯」那套图形语法
   对应 93–101 秒：每个零点生成一条正弦波，所有波叠加成阶梯
   ================================================================== */
'use strict';

/**
 * wave_stack — 从左侧轴出发的一叠正弦波 + 叠加结果
 * params:
 *   n        波的数量（= 零点个数）
 *   x0/x1    波在画面里的水平范围（归一化）
 *   amp      最大振幅（像素）
 *   cycles   每条波的基础周期数
 *   sum      是否在最下方画叠加结果
 */
registerKind('wave_stack', (ctx, local, p) => {
  const n = p.n || 14;
  const x0 = (p.x0 == null ? 0.16 : p.x0) * W;
  const x1 = (p.x1 == null ? 0.94 : p.x1) * W;
  const y0 = (p.y0 == null ? 0.44 : p.y0) * H;   // 波束的垂直中心
  const span = (p.span == null ? 0.30 : p.span) * H;
  const amp = (p.amp == null ? 9 : p.amp);
  const rise = easeOut(clamp01(local / (p.rise || 1.6)));
  const r = rng(p.seed || 77);

  // 左轴
  const axisX = x0 - 26;
  ctx.strokeStyle = 'rgba(232,210,160,0.75)';
  ctx.lineWidth = 2;
  ctx.beginPath();
  ctx.moveTo(axisX, y0 - span * 0.62);
  ctx.lineTo(axisX, y0 + span * 0.62);
  ctx.stroke();

  const waves = [];
  const stagger = p.stagger == null ? 0.06 : p.stagger;   // 逐条出现的间隔（秒）
  for (let i = 0; i < n; i++) {
    const yy = y0 - span / 2 + (span * i) / Math.max(1, n - 1);
    const cycles = 1.2 + (i / n) * 5.5 + r() * 1.2;   // 越往后频率越高
    const a = amp * (0.55 + r() * 0.45) * (1 - i / (n * 2.4));
    const ph = r() * Math.PI * 2;
    const speed = 0.25 + r() * 0.5;
    waves.push({ yy, cycles, a, ph, speed, born: i * stagger });
  }

  // 每条波（各自的出现时间不同 → 逐条生长）
  for (const w of waves) {
    const wRise = clamp01((local - w.born * (p.staggerScale || 6)) / 1.1);
    if (wRise <= 0) continue;
    ctx.strokeStyle = 'rgba(210,226,255,' + (0.34 * wRise).toFixed(3) + ')';
    ctx.lineWidth = 1.1;
    ctx.beginPath();
    const xEnd = x0 + (x1 - x0) * rise * wRise;
    for (let x = x0; x <= xEnd; x += 6) {
      const u = (x - x0) / (x1 - x0);
      const s = Math.sin(u * Math.PI * 2 * w.cycles + w.ph + local * w.speed);
      const env = Math.min(1, u * 6) * (1 - Math.pow(u, 6) * 0.5);   // 起点收敛、末端略收
      const y = w.yy + s * w.a * env;
      x === x0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
    }
    ctx.stroke();
  }

  // 叠加结果：所有波求和后的阶梯（放大后画在下方）
  if (p.sum !== false && rise > 0.35) {
    const sy = (p.sumY == null ? 0.80 : p.sumY) * H;
    const k = clamp01((rise - 0.35) / 0.65);
    ctx.strokeStyle = 'rgba(255,235,190,' + (0.88 * k).toFixed(3) + ')';
    ctx.lineWidth = 1.8;
    ctx.beginPath();
    const xEnd = x0 + (x1 - x0) * k;
    let prevY = null;
    for (let x = x0; x <= xEnd; x += 4) {
      const u = (x - x0) / (x1 - x0);
      let sum = 0;
      for (const w of waves) {
        sum += Math.sin(u * Math.PI * 2 * w.cycles + w.ph + local * w.speed) * w.a;
      }
      const y = sy - sum * 1.05;
      if (prevY === null) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
      prevY = y;
    }
    ctx.stroke();
  }
});

/**
 * axis_labels — 轴上固定刻度的标签（如质数 2 3 5 7 …）
 * params: marks(字符串数组) x0/x1 y
 */
registerKind('axis_labels', (ctx, local, p) => {
  const marks = p.marks || ['2', '3', '5', '7', '11'];
  const x0 = (p.x0 == null ? 0.16 : p.x0) * W;
  const x1 = (p.x1 == null ? 0.94 : p.x1) * W;
  const y = (p.y == null ? 0.84 : p.y) * H;
  const rise = easeOut(clamp01(local / (p.rise || 1.2)));
  ctx.strokeStyle = 'rgba(210,220,235,0.35)';
  ctx.lineWidth = 1;
  ctx.beginPath(); ctx.moveTo(x0, y); ctx.lineTo(x0 + (x1 - x0) * rise, y); ctx.stroke();
  ctx.font = '15px Consolas, monospace';
  ctx.textAlign = 'center';
  for (let i = 0; i < marks.length; i++) {
    const x = x0 + (x1 - x0) * (i / (marks.length - 1));
    if (x > x0 + (x1 - x0) * rise + 1) continue;
    ctx.fillStyle = 'rgba(220,228,240,0.62)';
    ctx.beginPath(); ctx.arc(x, y, 2.2, 0, 7); ctx.fill();
    ctx.fillText(marks[i], x, y + 22);
  }
});
