/* ==================================================================
   text.js — L4 六层字幕
   T1 主字幕 / T2 引语 / T3 数据标注 / T4 角落计数 / T5 资料出处 / T6 时间刻度
   支持 accumulate（累积生长）与 accent（关键词染金）
   ================================================================== */
'use strict';

const TEXT_STATE = { key: null, nodes: [] };

/** 把 accnet 词包成 span，其余保持原样 */
function markAccent(text, accents) {
  if (!accents || !accents.length) return escapeHTML(text);
  let out = escapeHTML(text);
  // 长的先替换，避免短词抢先
  const sorted = accents.slice().sort((a, b) => b.length - a.length);
  for (const w of sorted) {
    if (!w) continue;
    const esc = escapeHTML(w);
    out = out.split(esc).join(`<span class="accent">${esc}</span>`);
  }
  return out;
}

function escapeHTML(s) {
  return String(s).replace(/[&<>]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;' }[c]));
}

/**
 * 收集当前镜头在 local 时刻应该显示的文字块。
 * accumulate：同一 tier+pos 下，已激活的句子依次追加。
 */
function collectTexts(shot, local) {
  const list = (shot.texts || []).slice().sort((a, b) => a.t - b.t);
  const groups = new Map();      // key -> {tier,pos,lines[]}
  for (const tx of list) {
    if (local < tx.t) continue;
    const key = `${tx.tier}|${tx.pos || ''}`;
    if (!groups.has(key)) groups.set(key, { tier: tx.tier, pos: tx.pos || '', items: [] });
    groups.get(key).items.push(tx);
  }
  return groups;
}

/** 本镜头全部文字（不按时间过滤），用于占位排版 */
function groupAllTexts(shot) {
  const groups = new Map();
  const list = (shot.texts || []).slice().sort((a, b) => a.t - b.t);
  for (const tx of list) {
    const key = `${tx.tier}|${tx.pos || ''}`;
    if (!groups.has(key)) groups.set(key, { tier: tx.tier, pos: tx.pos || '', items: [] });
    groups.get(key).items.push(tx);
  }
  return groups;
}

function renderTexts(shot, local) {
  const host = document.getElementById('texts');
  // 用「全部文字 + 隐藏未到的」来占位，避免累积时整块文字上下跳动
  const all = groupAllTexts(shot);
  const groups = collectTexts(shot, local);

  host.innerHTML = '';
  for (const [key, g] of all) {
    const active = groups.get(key);
    const el = document.createElement('div');
    let cls = 't tier-' + g.tier + (g.pos ? ' pos-' + g.pos : '');
    // T3 数据标注与 T1 字幕同镜时，必须上移，否则会压在一起
    if (g.tier === 'T3' && (all.has('T1|') || all.has('T2|'))) cls += ' raised';
    el.className = cls;

    // T1/T2：整组不足两行时，在末尾补空占位行
    // —— 目的是让所有镜头的字幕都从同一个顶部基线开始，切镜时不跳高度
    const needPad = (g.tier === 'T1' || g.tier === 'T2');
    const totalLines = g.items.reduce((n, x) => n + (x.lines ? x.lines.length : 0), 0);

    for (const tx of g.items) {
      const block = document.createElement('div');
      let html = '';
      const lines = tx.lines || [];
      for (const ln of lines) {
        html += `<div>${markAccent(ln, tx.accent)}</div>`;
      }
      block.innerHTML = html;

      const isActive = active && active.items.indexOf(tx) >= 0;
      if (!isActive) {
        // 占位：保留排版空间，但不可见
        block.style.visibility = 'hidden';
        block.style.opacity = '0';
      } else {
        const age = local - tx.t;
        const fade = tx.mode === 'fade' ? Math.min(1, age / 0.45) : 1;
        block.style.opacity = fade.toFixed(3);
      }
      el.appendChild(block);
    }

    if (needPad && totalLines < 2) {
      const pad = document.createElement('div');
      pad.innerHTML = '<div>&nbsp;</div>';
      pad.style.visibility = 'hidden';
      el.appendChild(pad);
    }

    host.appendChild(el);
  }
}

function resetTexts() {
  document.getElementById('texts').innerHTML = '';
}
