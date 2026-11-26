/* ==================================================================
   graphics-camera.js — 图形摄像机（v2）
   ------------------------------------------------------------------
   新增三件事：
   1. 分层深度：graphics[].depth（0=远, 1=近），按深度分 3 组，
      每组用不同强度的摄像机变换合成 → 视差
   2. 各向异性缩放：camera.sx / sy 可以不同（拉伸）
   3. 元素级独立轨道：graphics[].t0 / dur，各自计算自己的进度
   ================================================================== */
'use strict';

const GCAM = {
  main: null,
  layers: [],        // 按深度分组的离屏缓冲
  ready: false,
  DEPTHS: [0.25, 0.6, 1.0]   // 远 / 中 / 近
};

function gcamInit(mainCtx) {
  GCAM.main = mainCtx;
  GCAM.layers = GCAM.DEPTHS.map(() => {
    const c = document.createElement('canvas');
    c.width = W;
    c.height = H;
    return { canvas: c, ctx: c.getContext('2d') };
  });
  GCAM.ready = true;
}

function depthIndex(depth) {
  const d = depth == null ? 0.6 : depth;
  if (d < 0.42) return 0;
  if (d < 0.8) return 1;
  return 2;
}

/** 把图形按深度画到各自的离屏缓冲 */
function drawGraphicsToBuffer(shot, local, t) {
  if (!GCAM.ready) return;
  for (const L of GCAM.layers) {
    L.ctx.setTransform(1, 0, 0, 1, 0, 0);
    L.ctx.clearRect(0, 0, W, H);
  }

  GCAM.overlay = [];      // 不参与摄像机变换的元素（坐标轴、标签）
  const list = shot.graphics || [];
  for (const g of list) {
    const fn = GRAPHICS[g.kind];
    if (!fn) { console.warn('未实现的图形 kind:', g.kind); continue; }

    // 元素级独立轨道：g.t0 之前不画，g.dur 控制自身进度
    const t0 = g.t0 || 0;
    if (local < t0) continue;
    const gl = local - t0;

    if (g.overlay) {
      // 先记录，稍后在摄像机之外绘制（保证字不被拉伸）
      GCAM.overlay.push({ g, gl });
      continue;
    }
    const L = GCAM.layers[depthIndex(g.depth)];
    fn(L.ctx, gl, g.params || {}, shot, t, g.dur);
  }

  for (const L of GCAM.layers) {
    // 只对非空层做 bloom
    bloom(L.ctx, 0.7);
  }
}

/**
 * 合成：每层按深度做不同强度的摄像机变换
 *   camera = { s0,s1 | sx0,sx1,sy0,sy1, x0,x1, y0,y1, t0,t1, ease, cx,cy, parallax }
 */
function applyGraphicsCamera(shot, local) {
  const ctx = GCAM.main;
  const cam = shot.camera || {};
  ctx.setTransform(1, 0, 0, 1, 0, 0);
  ctx.clearRect(0, 0, W, H);

  const t = clamp01((local - (cam.t0 || 0)) /
                    Math.max(0.001, (cam.t1 || 1) - (cam.t0 || 0)));
  const p = (EASE[cam.ease || 'easeInOut'] || easeInOut)(t);

  const s0 = cam.s0 == null ? 1 : cam.s0;
  const s1 = cam.s1 == null ? 1 : cam.s1;
  const base = s0 + (s1 - s0) * p;
  const ax = (cam.sx0 == null ? base : cam.sx0 + ((cam.sx1 == null ? base : cam.sx1) - cam.sx0) * p);
  const ay = (cam.sy0 == null ? base : cam.sy0 + ((cam.sy1 == null ? base : cam.sy1) - cam.sy0) * p);

  const cx = (cam.cx == null ? 0.5 : cam.cx) * W;
  const cy = (cam.cy == null ? 0.5 : cam.cy) * H;
  const dx = (cam.x0 || 0) + ((cam.x1 || 0) - (cam.x0 || 0)) * p;
  const dy = (cam.y0 || 0) + ((cam.y1 || 0) - (cam.y0 || 0)) * p;
  const par = cam.parallax == null ? 1 : cam.parallax;

  for (let i = 0; i < GCAM.layers.length; i++) {
    const depth = GCAM.DEPTHS[i];
    // 远景动得少，近景动得多
    const k = par === 0 ? 1 : (1 - par) + par * depth;
    const sx = 1 + (ax - 1) * k;
    const sy = 1 + (ay - 1) * k;
    ctx.save();
    ctx.translate(cx, cy);
    ctx.scale(sx, sy);
    ctx.translate(-cx + dx * k, -cy + dy * k);
    ctx.drawImage(GCAM.layers[i].canvas, 0, 0);
    ctx.restore();
  }

  // overlay：保持屏幕坐标，不随摄像机缩放
  if (GCAM.overlay && GCAM.overlay.length) {
    ctx.setTransform(1, 0, 0, 1, 0, 0);
    for (const { g, gl } of GCAM.overlay) {
      const fn = GRAPHICS[g.kind];
      if (fn) fn(ctx, gl, g.params || {}, shot, local, g.dur);
    }
  }
}
