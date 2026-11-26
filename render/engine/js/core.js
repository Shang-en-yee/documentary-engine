/* ==================================================================
   core.js — 基础工具：缓动、随机、色彩状态、颗粒
   ================================================================== */
'use strict';

const W = 1920, H = 1080;

// ---------- 缓动 ----------
const clamp01 = x => x < 0 ? 0 : (x > 1 ? 1 : x);
const easeOut = p => 1 - Math.pow(1 - clamp01(p), 3);
const easeInOut = p => {
  p = clamp01(p);
  return p < 0.5 ? 4 * p * p * p : 1 - Math.pow(-2 * p + 2, 3) / 2;
};
const linear = p => clamp01(p);
const EASE = { linear, easeInOut, easeOut };

/** 时间切片：从 start 起，用 dur 秒走完 0→1 */
function seg(t, start, dur) {
  if (dur <= 0) return t >= start ? 1 : 0;
  return clamp01((t - start) / dur);
}

// ---------- 确定性随机 ----------
function rng(seed) {
  let a = seed >>> 0;
  return function () {
    a |= 0; a = (a + 0x6D2B79F5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

// ---------- 色彩状态 ----------
/**
 * grade 用 CSS filter + 叠加色实现：
 *   filter  负责整体明度/饱和/色温
 *   overlay 负责把画面拉向某个色相
 */
const MOOD_CSS = {
  amber: {
    filter: 'saturate(0.90) contrast(1.06) brightness(0.68)',
    tint: 'rgba(232,158,72,0.55)',
    vignette: 0.9
  },
  steel: {
    filter: 'saturate(0.82) contrast(1.08) brightness(0.64)',
    tint: 'rgba(70,120,200,0.50)',
    vignette: 1.0
  },
  neutral: {
    filter: 'saturate(0.52) contrast(1.04) brightness(0.70)',
    tint: 'rgba(150,150,150,0.30)',
    vignette: 0.85
  },
  green: {
    filter: 'saturate(1.30) contrast(1.08) brightness(0.82) hue-rotate(78deg)',
    tint: 'rgba(30,220,150,0.75)',
    vignette: 1.05
  },
  jade: {
    filter: 'saturate(0.94) contrast(1.07) brightness(0.70) hue-rotate(12deg)',
    tint: 'rgba(60,170,150,0.26)',
    vignette: 0.95
  },
  deep: {
    filter: 'saturate(0.78) contrast(1.06) brightness(0.62)',
    tint: 'rgba(50,110,150,0.45)',
    vignette: 1.1
  }
};

function applyMood(moodName, brightMul) {
  const m = MOOD_CSS[moodName] || MOOD_CSS.neutral;
  const world = document.getElementById('world');
  let f = m.filter;
  if (brightMul && brightMul !== 1) {
    f = f.replace(/brightness\(([0-9.]+)\)/, (_, b) =>
      'brightness(' + (parseFloat(b) * brightMul).toFixed(3) + ')');
  }
  world.style.filter = f;
  const g = document.getElementById('grade');
  g.style.background = m.tint;
  g.style.opacity = '0.42';
  document.getElementById('vignette').style.opacity = String(m.vignette);
}

// ---------- 颗粒 ----------
const GRAIN = { alpha: 0.055, tiles: [] };

function buildGrain(ctx) {
  const N = 256;
  const r = rng(20261122);
  for (let k = 0; k < 4; k++) {
    const c = document.createElement('canvas');
    c.width = c.height = N;
    const cx = c.getContext('2d');
    const img = cx.createImageData(N, N);
    for (let i = 0; i < N * N; i++) {
      const v = Math.floor(r() * 256);
      img.data[i * 4] = v;
      img.data[i * 4 + 1] = v;
      img.data[i * 4 + 2] = v;
      img.data[i * 4 + 3] = 255;
    }
    cx.putImageData(img, 0, 0);
    GRAIN.tiles.push(ctx.createPattern(c, 'repeat'));
  }
  GRAIN.ctx = ctx;
}

function drawGrain(t) {
  const ctx = GRAIN.ctx;
  if (!ctx) return;
  const f = Math.round(t * 30);
  ctx.clearRect(0, 0, W, H);
  ctx.save();
  const ox = (f * 71) % 256, oy = (f * 137) % 256;
  ctx.translate(-ox, -oy);
  ctx.fillStyle = GRAIN.tiles[f % 4];
  ctx.fillRect(ox, oy, W, H);
  ctx.restore();
}

// ---------- Bloom（廉价版，给图形层用） ----------
function bloom(ctx, strength) {
  const s = strength == null ? 0.85 : strength;
  const tmp = document.createElement('canvas');
  tmp.width = Math.floor(W / 6);
  tmp.height = Math.floor(H / 6);
  const tc = tmp.getContext('2d');
  tc.drawImage(ctx.canvas, 0, 0, tmp.width, tmp.height);
  ctx.save();
  ctx.globalCompositeOperation = 'lighter';
  ctx.globalAlpha = s;
  ctx.imageSmoothingEnabled = true;
  ctx.drawImage(tmp, 0, 0, W, H);
  ctx.restore();
}

/** 把 "#rrggbb" 或 "r,g,b" 转成 rgba 字符串 */
function rgba(hex, a) {
  if (hex.indexOf(',') > 0) return `rgba(${hex},${a})`;
  const h = hex.replace('#', '');
  const r = parseInt(h.slice(0, 2), 16);
  const g = parseInt(h.slice(2, 4), 16);
  const b = parseInt(h.slice(4, 6), 16);
  return `rgba(${r},${g},${b},${a})`;
}
