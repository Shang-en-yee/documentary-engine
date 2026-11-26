/* ==================================================================
   asset.js — L2 素材层
   图片：cover 适配 + 肯伯恩斯（推拉/平移）+ 透视
   ================================================================== */
'use strict';

const ASSET = {
  cache: {},      // id -> {img, w, h}
  loaded: false
};

function preloadAssets(assets) {
  const jobs = (assets || []).map(a => new Promise(resolve => {
    if (!a.src) { resolve(); return; }
    const img = new Image();
    img.onload = () => {
      ASSET.cache[a.id] = { img, w: img.naturalWidth, h: img.naturalHeight, meta: a };
      resolve();
    };
    img.onerror = () => { console.warn('素材加载失败', a.id, a.src); resolve(); };
    // 允许 EDL 里写相对路径
    img.src = a.src;
  }));
  return Promise.all(jobs).then(() => { ASSET.loaded = true; });
}

/**
 * 把图片按 cover 方式铺满舞台，并叠加镜头运动。
 * @param shot  镜头对象
 * @param local 镜头内相对时间（秒）
 */
function drawAsset(shot, local) {
  const wrap = document.getElementById('asset-wrap');
  const imgEl = document.getElementById('asset-img');

  if (!shot.asset) { imgEl.style.opacity = '0'; return; }
  const rec = ASSET.cache[shot.asset];
  if (!rec) { imgEl.style.opacity = '0'; return; }

  if (imgEl.getAttribute('data-src') !== shot.asset) {
    imgEl.src = rec.meta.src;
    imgEl.setAttribute('data-src', shot.asset);
    imgEl.style.width = rec.w + 'px';
    imgEl.style.height = rec.h + 'px';
  }
  imgEl.style.opacity = '1';

  const dur = Math.max(0.001, shot.t1 - shot.t0);
  const p = clamp01(local / dur);
  const mo = shot.motion || { type: 'static' };
  const ease = EASE[mo.ease || 'linear'] || linear;

  // cover 基准缩放
  const cover = Math.max(W / rec.w, H / rec.h);

  // 可选裁切（crop: [x, y, w, h] 归一化）
  const op = shot.optics || {};
  let cropScale = 1;
  if (op.crop) cropScale = 1 / Math.min(op.crop[2], op.crop[3]);

  const e = ease(p);
  const zoom = mo.type === 'kenburns' ? (mo.zoom || 0) * e : 0;
  const panX = (mo.pan ? mo.pan[0] : 0) * e * W * 0.25;
  const panY = (mo.pan ? mo.pan[1] : 0) * e * H * 0.25;

  const s = cover * cropScale * (1 + zoom);
  const rot = op.rotate || 0;
  const persp = op.perspective || 0;

  // 透视放在外层，缩放/平移/旋转放在图片上
  wrap.style.transform = persp
    ? `perspective(1700px) rotateY(${(persp * -16).toFixed(2)}deg) rotateX(${(persp * 5).toFixed(2)}deg)`
    : 'none';

  imgEl.style.transform =
    `translate(${panX.toFixed(2)}px, ${panY.toFixed(2)}px) ` +
    `scale(${s.toFixed(5)}) rotate(${rot.toFixed(2)}deg)`;
  imgEl.style.transformOrigin = '50% 50%';

  // 文档类素材：压暗边缘，像被灯照着
  imgEl.style.filter = op.spotlight === false ? 'none'
    : 'brightness(0.92) contrast(1.06)';
}

/** 旧素材切换时清空，避免闪帧 */
function resetAsset() {
  const imgEl = document.getElementById('asset-img');
  imgEl.removeAttribute('data-src');
  imgEl.style.opacity = '0';
}
