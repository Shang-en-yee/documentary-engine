/* ==================================================================
   main.js — 时间轴与主渲染循环
   render(t) 是时间的纯函数：给定 t，画出这一帧。
   ================================================================== */
'use strict';

const FILM = {
  edl: null,
  duration: 0,
  scenes: []          // [{shot, t0, t1}]
};

function findShot(t) {
  const s = FILM.scenes;
  for (let i = 0; i < s.length; i++) {
    if (t >= s[i].t0 && t < s[i].t1) return s[i];
  }
  return s.length ? s[s.length - 1] : null;
}

function render(t) {
  const sc = findShot(t);
  if (!sc) return;
  const shot = sc.shot;
  const local = t - sc.t0;

  // L2 素材
  drawAsset(shot, local);

  // L2b 程序图形（先画到离屏缓冲，再按 shot.camera 合成，支持推拉）
  if (GCAM.ready) {
    drawGraphicsToBuffer(shot, local, t);
    applyGraphicsCamera(shot, local);
  } else {
    drawGraphics(shot, local, t);
  }

  // L4 文字（支持逐镜字幕高度覆盖）
  document.getElementById('stage').style.setProperty(
    '--t1-bottom', (shot.text_y == null ? 10.4 : shot.text_y) + '%');
  renderTexts(shot, local);

  // L5 调色（按镜头 grade 覆盖 act mood），支持逐镜亮度微调
  applyMood(shot.grade || shot._mood || 'neutral', shot.brightness);

  // L5 颗粒
  drawGrain(t);
}

async function boot() {
  const edl = window.__EDL__;
  if (!edl) { document.body.innerHTML = '<pre style="color:#f66">缺少 __EDL__</pre>'; return; }
  FILM.edl = edl;

  // 幕 → 镜头继承 mood
  const actMood = {};
  for (const a of edl.acts || []) actMood[a.id] = a.mood;

  FILM.scenes = (edl.shots || []).map(s => {
    s._mood = actMood[s.act] || 'neutral';
    return { shot: s, t0: s.t0, t1: s.t1 };
  });
  FILM.duration = edl.meta.duration;

  // 素材预加载
  await preloadAssets(edl.assets);

  // 颗粒
  buildGrain(document.getElementById('grain').getContext('2d'));

  // 图形层（主画布 + 离屏摄像机缓冲）
  const gctx = document.getElementById('graphics').getContext('2d');
  graphicsInit(gctx);
  gcamInit(gctx);

  // 对外接口（给导出器用）
  window.__film = {
    duration: FILM.duration,
    fps: edl.meta.fps,
    seek: t => { render(t); return true; },
    render
  };

  // URL ?t= 直接定位
  const q = new URLSearchParams(location.search);
  const t0 = parseFloat(q.get('t') || '0');
  render(t0);
  window.__ready = true;
}

window.addEventListener('DOMContentLoaded', boot);
