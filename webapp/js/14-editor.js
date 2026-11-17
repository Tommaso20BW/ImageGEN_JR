/* ---------- Editor libero ----------
   Una pagina a livelli disegnata qui nella Mini App: foto, testi, logo JR, sfumature e forme, ognuno
   da spostare (un dito), zoomare e ruotare (due dita) e con le sue opzioni (bianco e nero, bagliore,
   ombra, contorno, colori, font…). Quello che vedi è quello che arriva: all'anteprima la pagina si
   disegna a piena risoluzione e va al servizio come immagine finita (kind 'free').
   Modelli: la pagina senza le foto si salva con un nome nel repo degli asset (/templates); per
   riusarla basta rimettere le foto. */

const FR_FONTS = [
  ['Poppins', 'Poppins-Medium.ttf'], ['Anton', 'Anton-Regular.ttf'], ['Bebas Neue', 'BebasNeue2014-Regular.ttf'],
  ['JR Didone', 'JRDidoneCondensed-Regular.ttf'], ['Inter', 'Inter-Medium.ttf'], ['Teko', 'Teko-Regular.ttf'],
  ['Dharma Gothic', 'DharmaGothicEBold.otf'], ['Special Elite', 'SpecialElite-Regular.ttf'], ['Corinthiago', 'Corinthiago.ttf'],
  ['Allogist', 'AllogistItalic.ttf'], ['JR Fasi', 'JRFasi-Regular.ttf'], ['Matchday', 'MatchdayInfo.ttf']
];
const FR_FORMATS = [['3:4', 1500, 2000], ['4:5', 1600, 2000], ['1:1', 1500, 1500], ['9:16', 1125, 2000]];
const FR_TYPE_NAMES = {photo:'Foto', text:'Testo', logo:'Logo JR', shade:'Sfumatura', rect:'Forma'};

const fr = {doc:null, pickTpl:'', sel:'', tplId:'', tplName:'', images:{}, cuts:{}, cutBusy:{}, undo:{}, brush:null, brushSize:44, erasing:false, cache:{}, fonts:{}, logo:null, templates:null,
  exportKey:'', exportId:'', drawQueued:false, guides:[0, 0]};

let frSeq = 0;
const frId = () => `l${Date.now().toString(36)}${(frSeq++).toString(36)}`;
const frClone = o => JSON.parse(JSON.stringify(o));
const frLayer = id => fr.doc && fr.doc.layers.find(l => l.id === id);
const frEffects = () => ({glow:{on:false, color:'#ffffff', blur:18, strength:35}, shadow:{on:false, color:'#000000', blur:20, dx:0, dy:10, strength:60},
  stroke:{on:false, color:'#000000', width:6}});

function frNew(type) {
  const W = fr.doc.w, H = fr.doc.h;
  const base = {id:frId(), type, x:W / 2, y:H / 2, scale:1, rot:0, opacity:100};
  if (type === 'photo') return {...base, bw:false, bright:0, contrast:0, sharpen:false, blur:0, ...frEffects()};
  if (type === 'text') return {...base, text:'Testo', font:'Poppins', size:120, color:'#ffffff', align:'center',
    upper:false, spacing:0, line:110, fit:0, ...frEffects()};
  if (type === 'logo') return {...base, ...frLogoSpot(W), color:'auto', ...frEffects()};
  if (type === 'shade') return {...base, dir:'bottom', color:'#000000', from:55, strength:80};
  return {...base, w:900, h:180, color:'#000000', radius:0, ...frEffects()};
}

// Il posto di sempre del logo JR, come nelle altre grafiche (overlay 3:4 della FOTO + JR): in alto a
// destra, alto 94 e a 24 dal bordo destro e 18 da quello alto su una pagina larga 1500 (in proporzione).
function frLogoSpot(W) {
  const size = W * 94 / 1500;
  const asp = fr.logoImg ? fr.logoImg.width / fr.logoImg.height : 0.69;
  return {x:W - W * 24 / 1500 - size * asp / 2, y:W * 18 / 1500 + size / 2, size, scale:1, rot:0};
}
function frLogoHome(l) { Object.assign(l, frLogoSpot(fr.doc.w)); }

function frBlank(w=1500, h=2000) { return {v:1, w, h, bg:'#000000', caption:'', layers:[]}; }

/* ---------- risorse: font, logo, foto ---------- */
function frFile(name) { return `${directBase}/editorfile?session=${encodeURIComponent(session)}&name=${encodeURIComponent(name)}`; }

function frFont(family) {
  if (fr.fonts[family]) return fr.fonts[family];
  const row = FR_FONTS.find(f => f[0] === family);
  if (!row || !directBase || typeof FontFace !== 'function') return (fr.fonts[family] = Promise.resolve(false));
  fr.fonts[family] = new FontFace(`FR ${family}`, `url(${frFile(row[1])})`).load()
    .then(face => { document.fonts.add(face); frDraw(); return true; })
    .catch(() => { delete fr.fonts[family]; return false; });
  return fr.fonts[family];
}

// Logo come blob locale (un'immagine di un altro sito "sporcherebbe" la tela e non si potrebbe esportare).
function frLogo() {
  if (fr.logo) return fr.logo;
  fr.logo = fetch(frFile('jrlogo')).then(r => r.ok ? r.blob() : Promise.reject())
    .then(b => createImageBitmap(b)).then(bm => { fr.logoImg = bm; frDraw(); return bm; })
    .catch(() => { fr.logo = null; return null; });
  return fr.logo;
}

async function frReadPhoto(file) {
  let src;
  try { src = await createImageBitmap(file, {imageOrientation:'from-image'}); }
  catch (_) {
    src = await new Promise((resolve, reject) => {
      const im = new Image(); im.onload = () => resolve(im); im.onerror = reject; im.src = URL.createObjectURL(file);
    });
  }
  const k = Math.min(1, 2400 / Math.max(src.width, src.height));
  const c = document.createElement('canvas');
  c.width = Math.round(src.width * k); c.height = Math.round(src.height * k);
  c.getContext('2d').drawImage(src, 0, 0, c.width, c.height);
  return c;
}

// Foto con i suoi filtri (bianco e nero, luminosità, contrasto, nitidezza): calcolata una volta per impostazioni.
function frProcessed(l) {
  const src = (l.cutout && fr.cuts[l.id]) || fr.images[l.id];    // senza sfondo, se è pronta
  if (!src) return null;
  const key = [l.bw, l.bright, l.contrast, l.sharpen, src.width, src === fr.images[l.id] ? 0 : 1].join('|');
  const hit = fr.cache[l.id];
  if (hit && hit.key === key) return hit.canvas;
  const c = document.createElement('canvas');
  c.width = src.width; c.height = src.height;
  const ctx = c.getContext('2d');
  ctx.drawImage(src, 0, 0);
  if (l.bw || l.bright || l.contrast || l.sharpen) {
    const img = ctx.getImageData(0, 0, c.width, c.height), p = img.data;
    const b = l.bright * 2.55, k = (100 + l.contrast) / 100;
    for (let i = 0; i < p.length; i += 4) {
      let r = p[i], g = p[i + 1], bl = p[i + 2];
      if (l.bw) r = g = bl = 0.299 * r + 0.587 * g + 0.114 * bl;
      p[i] = (r - 128) * k + 128 + b; p[i + 1] = (g - 128) * k + 128 + b; p[i + 2] = (bl - 128) * k + 128 + b;
    }
    if (l.sharpen) frSharpen(img);
    ctx.putImageData(img, 0, 0);
  }
  fr.cache[l.id] = {key, canvas:c};
  return c;
}

// Nitidezza: maschera di contrasto 3x3 (centro forte, croce in negativo).
function frSharpen(img) {
  const {width:w, height:h, data:p} = img, src = new Uint8ClampedArray(p), a = 0.35;
  for (let y = 1; y < h - 1; y++) {
    for (let x = 1; x < w - 1; x++) {
      const i = (y * w + x) * 4;
      for (let c = 0; c < 3; c++) {
        const v = src[i + c] * (1 + 4 * a) - a * (src[i - 4 + c] + src[i + 4 + c] + src[i - w * 4 + c] + src[i + w * 4 + c]);
        p[i + c] = v;
      }
    }
  }
}

/* ---------- disegno ---------- */
function frPhotoSize(l) {
  // a scala 1 la foto copre tutta la pagina
  const src = fr.images[l.id];
  const sw = src ? src.width : 3, sh = src ? src.height : 4;
  const k = Math.max(fr.doc.w / sw, fr.doc.h / sh) * l.scale;
  return [sw * k, sh * k];
}

function frTextLines(l) { return String(l.upper ? l.text.toUpperCase() : l.text).split('\n'); }

function frTextFont(l, ctx) {
  let size = l.size * l.scale;
  const font = s => `${s}px "FR ${l.font}", sans-serif`;
  ctx.font = font(size);
  if (l.fit > 0) {
    const widest = Math.max(...frTextLines(l).map(t => frMeasure(ctx, t, l.spacing * l.scale)));
    if (widest > l.fit * l.scale) { size *= l.fit * l.scale / widest; ctx.font = font(size); }
  }
  return size;
}

function frMeasure(ctx, text, spacing) {
  return ctx.measureText(text).width + Math.max(0, text.length - 1) * spacing;
}

// Riquadro del livello (centrato in x, y, prima della rotazione): [larghezza, altezza].
function frBox(l, ctx) {
  if (l.type === 'photo') return frPhotoSize(l);
  if (l.type === 'logo') { const im = fr.logoImg; const h = l.size * l.scale; return [im ? h * im.width / im.height : h * 0.75, h]; }
  if (l.type === 'rect') return [l.w * l.scale, l.h * l.scale];
  if (l.type === 'text') {
    const size = frTextFont(l, ctx), lines = frTextLines(l);
    const w = Math.max(...lines.map(t => frMeasure(ctx, t, l.spacing * l.scale)), size * 0.3);
    return [w, size * (1 + (lines.length - 1) * l.line / 100)];
  }
  return [fr.doc.w, fr.doc.h];
}

function frWithEffects(ctx, l, paint) {
  // ombra e bagliore: la stessa forma ridisegnata con shadowBlur (più passate = più intenso)
  const fx = (e, dx, dy) => {
    if (!e || !e.on) return;
    const passes = Math.max(1, Math.round(e.strength / 34));
    ctx.save();
    ctx.shadowColor = frAlpha(e.color, Math.min(1, e.strength / 100 * 1.6 / passes + 0.15));
    ctx.shadowBlur = e.blur * fr.k;
    ctx.shadowOffsetX = (dx || 0) * fr.k; ctx.shadowOffsetY = (dy || 0) * fr.k;
    for (let i = 0; i < passes; i++) paint(true);
    ctx.restore();
  };
  fx(l.shadow, l.shadow && l.shadow.dx, l.shadow && l.shadow.dy);
  fx(l.glow, 0, 0);
  paint(false);
}

function frAlpha(hex, a) {
  const m = /^#?([0-9a-f]{6})$/i.exec(hex || '');
  const n = m ? parseInt(m[1], 16) : 0;
  return `rgba(${n >> 16 & 255},${n >> 8 & 255},${n & 255},${a.toFixed(3)})`;
}

function frDrawLayer(ctx, l) {
  const W = fr.doc.w, H = fr.doc.h;
  ctx.save();
  ctx.globalAlpha = (l.opacity == null ? 100 : l.opacity) / 100;
  if (l.type === 'shade') {
    const v = {bottom:[0, 0, 0, H], top:[0, H, 0, 0], left:[W, 0, 0, 0], right:[0, 0, W, 0]}[l.dir] || [0, 0, 0, H];
    const g = ctx.createLinearGradient(...v.map(n => n));
    const from = Math.min(0.99, l.from / 100);
    g.addColorStop(0, frAlpha(l.color, 0));
    g.addColorStop(from, frAlpha(l.color, 0));
    for (let i = 1; i <= 6; i++) {                   // curva morbida, come nel poster
      const t = i / 6;
      g.addColorStop(from + (1 - from) * t, frAlpha(l.color, Math.pow(t, 1.6) * l.strength / 100));
    }
    ctx.fillStyle = g;
    ctx.fillRect(0, 0, W, H);
    ctx.restore();
    return;
  }
  ctx.translate(l.x, l.y);
  ctx.rotate(l.rot * Math.PI / 180);
  const [w, h] = frBox(l, ctx);
  if (l.type === 'photo') {
    const img = frProcessed(l);
    if (img) {
      if (l.blur) ctx.filter = `blur(${l.blur * fr.k}px)`;
      frWithEffects(ctx, l, () => ctx.drawImage(img, -w / 2, -h / 2, w, h));
    } else if (fr.editing) {                         // posto vuoto (solo nell'editor)
      ctx.fillStyle = '#2a2a2e'; ctx.fillRect(-w / 2, -h / 2, w, h);
      ctx.fillStyle = '#8d8b86'; ctx.font = `600 ${Math.round(70)}px -apple-system, system-ui, sans-serif`;
      ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
      ctx.rotate(-l.rot * Math.PI / 180);
      ctx.fillText('Tocca + Foto per inserirla', 0, 0);
    }
  } else if (l.type === 'logo') {
    const im = fr.logoImg;
    if (im) {
      const color = l.color === 'auto' ? frAutoColor(ctx, l, w, h) : l.color;
      const tint = frTinted(im, color);
      frWithEffects(ctx, l, () => ctx.drawImage(tint, -w / 2, -h / 2, w, h));
    }
  } else if (l.type === 'rect') {
    ctx.fillStyle = l.color;
    const r = Math.min(l.radius * l.scale, w / 2, h / 2);
    frWithEffects(ctx, l, () => { ctx.beginPath(); frRound(ctx, -w / 2, -h / 2, w, h, r); ctx.fill(); });
  } else if (l.type === 'text') {
    const size = frTextFont(l, ctx), lines = frTextLines(l), lh = size * l.line / 100, sp = l.spacing * l.scale;
    ctx.textBaseline = 'alphabetic';
    ctx.lineJoin = 'round';
    const top = -h / 2 + size * 0.8;
    const paint = shadowPass => {
      lines.forEach((t, i) => {
        const tw = frMeasure(ctx, t, sp);
        const x0 = l.align === 'left' ? -w / 2 : l.align === 'right' ? w / 2 - tw : -tw / 2;
        const y = top + i * lh;
        frText(ctx, t, x0, y, sp, l, shadowPass);
      });
    };
    frWithEffects(ctx, l, paint);
  }
  ctx.restore();
}

function frText(ctx, t, x, y, sp, l, shadowPass) {
  const parts = sp ? [...t] : [t];
  let cx = x;
  for (const ch of parts) {
    if (l.stroke && l.stroke.on && !shadowPass) {
      ctx.strokeStyle = l.stroke.color; ctx.lineWidth = l.stroke.width * 2 * l.scale;
      ctx.strokeText(ch, cx, y);
    }
    ctx.fillStyle = l.color;
    ctx.fillText(ch, cx, y);
    cx += ctx.measureText(ch).width + sp;
  }
}

function frRound(ctx, x, y, w, h, r) {
  ctx.moveTo(x + r, y); ctx.arcTo(x + w, y, x + w, y + h, r); ctx.arcTo(x + w, y + h, x, y + h, r);
  ctx.arcTo(x, y + h, x, y, r); ctx.arcTo(x, y, x + w, y, r); ctx.closePath();
}

function frTinted(im, color) {
  const key = `${color}|${im.width}`;
  if (fr.tint && fr.tint.key === key) return fr.tint.canvas;
  const c = document.createElement('canvas');
  c.width = im.width; c.height = im.height;
  const x = c.getContext('2d');
  x.drawImage(im, 0, 0);
  x.globalCompositeOperation = 'source-in';
  x.fillStyle = color; x.fillRect(0, 0, c.width, c.height);
  fr.tint = {key, canvas:c};
  return c;
}

// Logo "automatico": nero se quello che c'è sotto è chiaro, bianco se è scuro.
function frAutoColor(ctx, l, w, h) {
  try {
    const m = ctx.getTransform();
    const x = Math.max(0, Math.round(m.e - w * fr.k / 2 - 20 * fr.k)), y = Math.max(0, Math.round(m.f - h * fr.k / 2 - 20 * fr.k));
    const ww = Math.max(1, Math.min(ctx.canvas.width - x, Math.round((w + 40) * fr.k)));
    const hh = Math.max(1, Math.min(ctx.canvas.height - y, Math.round((h + 40) * fr.k)));
    const p = ctx.getImageData(x, y, ww, hh).data;
    let sum = 0;
    for (let i = 0; i < p.length; i += 4) sum += 0.299 * p[i] + 0.587 * p[i + 1] + 0.114 * p[i + 2];
    return sum / (p.length / 4) > 140 ? '#000000' : '#ffffff';
  } catch (_) { return '#ffffff'; }
}

function frRender(canvas, k, editing) {
  const ctx = canvas.getContext('2d');
  fr.k = k;
  fr.editing = editing;
  ctx.setTransform(1, 0, 0, 1, 0, 0);
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  ctx.setTransform(k, 0, 0, k, 0, 0);
  ctx.fillStyle = fr.doc.bg || '#000000';
  ctx.fillRect(0, 0, fr.doc.w, fr.doc.h);
  for (const l of fr.doc.layers) if (!l.hidden) frDrawLayer(ctx, l);
}

/* ---------- selezione come Canva ----------
   L'elemento scelto ha un riquadro con le maniglie: angoli = ingrandisci, cerchio sotto = ruota,
   lati (solo forme) = allunga. Sopra compare una barretta con le azioni veloci. */
const FR_SEL = '#8b3dff';
const FR_GRAB = 18;                       // raggio di tocco delle maniglie (px dello schermo)

function frCssK() { const c = $('frCanvas'); return c && c.clientWidth ? c.clientWidth / fr.doc.w : 1; }   // px schermo per unità di pagina

function frGeom(l) {
  const ctx = $('frCanvas').getContext('2d');
  ctx.save(); ctx.setTransform(1, 0, 0, 1, 0, 0);
  const [w, h] = frBox(l, ctx);
  ctx.restore();
  const a = l.rot * Math.PI / 180, cs = Math.cos(a), sn = Math.sin(a);
  const u = 1 / frCssK(), pad = 6 * u;
  return {w, h, a, u, pad, hw:w / 2 + pad, hh:h / 2 + pad,
    pt:(lx, ly) => [l.x + lx * cs - ly * sn, l.y + lx * sn + ly * cs],
    local:(px, py) => { const dx = px - l.x, dy = py - l.y; return [dx * cs + dy * sn, -dx * sn + dy * cs]; }};
}

function frHandles(l) {
  const g = frGeom(l);
  const out = [['nw', -g.hw, -g.hh], ['ne', g.hw, -g.hh], ['sw', -g.hw, g.hh], ['se', g.hw, g.hh], ['rot', 0, g.hh + 34 * g.u]];
  if (l.type === 'rect') out.push(['e', g.hw, 0], ['w', -g.hw, 0], ['n', 0, -g.hh], ['s', 0, g.hh]);
  return {g, list:out};
}

function frHandleAt(px, py) {
  const l = frLayer(fr.sel);
  if (!l || l.type === 'shade' || l.hidden) return null;
  const {g, list} = frHandles(l);
  const [lx, ly] = g.local(px, py);
  let best = null, bd = FR_GRAB * g.u;
  for (const [name, hx, hy] of list) {
    const d = Math.hypot(lx - hx, ly - hy);
    if (d < bd) { bd = d; best = name; }
  }
  return best;
}

// Disegnata su una tela trasparente sopra tutta l'area grigia: le maniglie restano visibili anche fuori dalla pagina.
function frDrawSelection(ctx) {
  const px = 1 / frCssK() / 2;
  ctx.save();
  ctx.fillStyle = '#ff2d87';
  if (fr.guides[0]) ctx.fillRect(fr.doc.w / 2 - px, 0, 2 * px, fr.doc.h);
  if (fr.guides[1]) ctx.fillRect(0, fr.doc.h / 2 - px, fr.doc.w, 2 * px);
  const l = frLayer(fr.sel);
  if (fr.brush && l) {                                   // gomma: i tratti, niente maniglie
    ctx.lineCap = ctx.lineJoin = 'round';
    ctx.strokeStyle = ctx.fillStyle = 'rgba(139,61,255,.5)';
    for (const s of fr.brush.strokes) {
      ctx.lineWidth = s.r * 2;
      ctx.beginPath();
      if (s.pts.length === 1) { ctx.arc(s.pts[0][0], s.pts[0][1], s.r, 0, Math.PI * 2); ctx.fill(); continue; }
      s.pts.forEach(([x, y], i) => (i ? ctx.lineTo(x, y) : ctx.moveTo(x, y)));
      ctx.stroke();
    }
  } else if (l && l.type !== 'shade' && !l.hidden) {
    const {g, list} = frHandles(l);
    ctx.translate(l.x, l.y);
    ctx.rotate(g.a);
    const lw = 1.5 * g.u;
    ctx.strokeStyle = FR_SEL; ctx.lineWidth = lw;
    ctx.strokeRect(-g.hw, -g.hh, g.hw * 2, g.hh * 2);
    if (!fr.dragging || fr.dragging === 'rot') {
      ctx.beginPath(); ctx.moveTo(0, g.hh); ctx.lineTo(0, g.hh + 22 * g.u); ctx.stroke();
      for (const [name, hx, hy] of list) {
        ctx.beginPath();
        if (name === 'rot') ctx.arc(hx, hy, 11 * g.u, 0, Math.PI * 2);
        else if (name.length === 1) frRound(ctx, hx - (name === 'n' || name === 's' ? 9 : 3.5) * g.u, hy - (name === 'e' || name === 'w' ? 9 : 3.5) * g.u,
          (name === 'n' || name === 's' ? 18 : 7) * g.u, (name === 'e' || name === 'w' ? 18 : 7) * g.u, 3.5 * g.u);
        else ctx.arc(hx, hy, 7 * g.u, 0, Math.PI * 2);
        ctx.fillStyle = '#ffffff'; ctx.fill();
        ctx.lineWidth = lw; ctx.strokeStyle = 'rgba(0,0,0,.25)'; ctx.stroke();
      }
      // freccia circolare nel cerchio di rotazione
      const [, rx, ry] = list.find(h => h[0] === 'rot');
      ctx.beginPath(); ctx.arc(rx, ry, 5 * g.u, -Math.PI * 0.9, Math.PI * 0.55);
      ctx.strokeStyle = '#333'; ctx.lineWidth = 1.6 * g.u; ctx.stroke();
    }
  }
  ctx.restore();
}

function frDraw() {
  if (fr.drawQueued) return;
  fr.drawQueued = true;
  requestAnimationFrame(() => {
    fr.drawQueued = false;
    const c = $('frCanvas');
    if (!c || !fr.doc || !c.offsetParent) return;
    const box = $('frStageBox');
    const bw = box.clientWidth - 8, bh = Math.max(160, box.clientHeight - 8);
    const cssW = Math.min(bw, bh * fr.doc.w / fr.doc.h);
    const cssH = cssW * fr.doc.h / fr.doc.w;
    const dpr = Math.min(2, window.devicePixelRatio || 1);
    c.style.width = `${cssW}px`; c.style.height = `${cssH}px`;
    const pw = Math.round(cssW * dpr), ph = Math.round(cssH * dpr);
    if (c.width !== pw || c.height !== ph) { c.width = pw; c.height = ph; }
    frRender(c, pw / fr.doc.w, true);
    const o = $('frOver');
    const ow = Math.round(box.clientWidth * dpr), oh = Math.round(box.clientHeight * dpr);
    if (o.width !== ow || o.height !== oh) { o.width = ow; o.height = oh; }
    const octx = o.getContext('2d');
    octx.setTransform(1, 0, 0, 1, 0, 0);
    octx.clearRect(0, 0, ow, oh);
    const kk = cssW / fr.doc.w * dpr;
    octx.setTransform(kk, 0, 0, kk, c.offsetLeft * dpr, c.offsetTop * dpr);
    frDrawSelection(octx);
    frFloat();
  });
}

// Barretta sopra l'elemento scelto (Duplica, Elimina…), come in Canva.
function frFloat() {
  const f = $('frFloat'), l = frLayer(fr.sel), c = $('frCanvas');
  if (!f) return;
  if (!l || l.hidden || l.type === 'shade' || fr.dragging || fr.brush) { f.hidden = true; return; }
  const g = frGeom(l), k = frCssK();
  const pts = [[-g.hw, -g.hh], [g.hw, -g.hh], [-g.hw, g.hh], [g.hw, g.hh + 34 * g.u]].map(p => g.pt(...p));
  const xs = pts.map(p => p[0] * k), ys = pts.map(p => p[1] * k);
  f.hidden = false;
  const fw = f.offsetWidth, fh = f.offsetHeight, box = $('frStageBox');
  let x = c.offsetLeft + (Math.min(...xs) + Math.max(...xs)) / 2 - fw / 2;
  // mai sopra all'elemento: sopra di lui, altrimenti sotto; se non c'è spazio da nessuna parte
  // la barretta sparisce (Duplica ed Elimina sono anche in Posizione)
  let y = c.offsetTop + Math.min(...ys) - fh - 10;
  if (y < 2) y = c.offsetTop + Math.max(...ys) + 10;
  if (y + fh > box.clientHeight - 2) { f.hidden = true; return; }
  x = Math.max(4, Math.min(box.clientWidth - fw - 4, x));
  f.style.transform = `translate(${Math.round(x)}px,${Math.round(y)}px)`;
}

/* ---------- tocchi sulla pagina ---------- */
function frHit(px, py) {
  for (let i = fr.doc.layers.length - 1; i >= 0; i--) {
    const l = fr.doc.layers[i];
    if (l.hidden || l.type === 'shade') continue;
    if (frHitsLayer(l, px, py)) return l;
  }
  return null;
}

function frHitsLayer(l, px, py) {
  const g = frGeom(l);
  const [lx, ly] = g.local(px, py);
  const pad = 10 * g.u;
  return Math.abs(lx) <= g.w / 2 + pad && Math.abs(ly) <= g.h / 2 + pad;
}

function initFreeCanvas() {
  const c = $('frCanvas'), area = $('frStageBox');
  const pts = new Map();
  let mode = '', start = null, last = null, moved = false, wasSel = false, downAt = null;
  const toPage = e => { const r = c.getBoundingClientRect(); return [(e.clientX - r.left) / r.width * fr.doc.w, (e.clientY - r.top) / r.height * fr.doc.h]; };
  const two = () => {
    const [p, q] = [...pts.values()];
    return {x:(p[0] + q[0]) / 2, y:(p[1] + q[1]) / 2, d:Math.hypot(p[0] - q[0], p[1] - q[1]), a:Math.atan2(q[1] - p[1], q[0] - p[0])};
  };
  const norm = r => ((r + 540) % 360) - 180;
  const snapRot = r => { for (const t of [-180, -90, 0, 90, 180]) if (Math.abs(r - t) < 3) return t === -180 ? 180 : t; return r; };
  area.addEventListener('pointerdown', e => {
    if (!fr.doc || e.target.closest('#frFloat')) return;
    area.setPointerCapture(e.pointerId);
    const p = toPage(e);
    pts.set(e.pointerId, p);
    const l = frLayer(fr.sel);
    if (fr.brush) {                                      // gomma: il dito dipinge la zona da cancellare
      if (fr.erasing || pts.size > 1) { mode = ''; return; }
      fr.brush.strokes.push({r:fr.brushSize / 2 / frCssK(), pts:[p]});
      mode = 'paint'; frDraw();
      return;
    }
    if (pts.size === 2) {
      if (l && l.type !== 'shade') { mode = 'pinch'; last = two(); }
      return;
    }
    moved = false; downAt = p;
    const handle = frHandleAt(...p);
    if (handle) {
      mode = handle;
      const g = frGeom(l);
      start = {p, scale:l.scale, rot:l.rot, w:l.w, h:l.h, d:Math.hypot(p[0] - l.x, p[1] - l.y), a:Math.atan2(p[1] - l.y, p[0] - l.x), g};
      return;
    }
    // il tocco sceglie l'elemento sotto il dito (quello già scelto ha la precedenza); fuori da tutto: nessuno
    const hit = l && !l.hidden && l.type !== 'shade' && frHitsLayer(l, ...p) ? l : frHit(...p);
    wasSel = !!(hit && hit.id === fr.sel);
    if (hit) { if (!wasSel) frSelect(hit.id, true); mode = 'move'; start = {x:hit.x, y:hit.y, p}; }
    else { mode = ''; if (fr.sel) frSelect('', true); }
  });
  area.addEventListener('pointermove', e => {
    if (!pts.has(e.pointerId)) return;
    const p = toPage(e);
    pts.set(e.pointerId, p);
    const l = frLayer(fr.sel);
    if (mode === 'paint') {
      const s = fr.brush && fr.brush.strokes[fr.brush.strokes.length - 1];
      if (s) { s.pts.push(p); frDraw(); }
      return;
    }
    if (!l || !mode) return;
    if (!moved && downAt && Math.hypot(p[0] - downAt[0], p[1] - downAt[1]) * frCssK() < 4 && mode === 'move') return;
    if (!moved) { moved = true; fr.dragging = mode; }
    if (mode === 'pinch' && pts.size >= 2) {
      const now = two();
      l.x += now.x - last.x; l.y += now.y - last.y;
      l.scale = Math.min(8, Math.max(0.05, l.scale * now.d / last.d));
      l.rot = snapRot(norm(l.rot + (now.a - last.a) * 180 / Math.PI));
      last = now;
    } else if (mode === 'move') {
      const thr = 8 / frCssK();
      const nx = start.x + p[0] - start.p[0], ny = start.y + p[1] - start.p[1];
      const sx = Math.abs(nx - fr.doc.w / 2) < thr, sy = Math.abs(ny - fr.doc.h / 2) < thr;
      if ((sx && !fr.guides[0]) || (sy && !fr.guides[1])) haptic('select');
      fr.guides = [sx, sy];
      l.x = sx ? fr.doc.w / 2 : nx; l.y = sy ? fr.doc.h / 2 : ny;
    } else if (mode === 'rot') {
      const a = Math.atan2(p[1] - l.y, p[0] - l.x);
      const r = snapRot(norm(start.rot + (a - start.a) * 180 / Math.PI));
      if (r !== l.rot && [0, 90, -90, 180].includes(r)) haptic('select');
      l.rot = r;
    } else if (mode.length === 2) {                      // angoli: ingrandisci dal centro
      l.scale = Math.min(8, Math.max(0.05, start.scale * Math.hypot(p[0] - l.x, p[1] - l.y) / start.d));
    } else {                                             // lati della forma: allunga
      const [lx, ly] = start.g.local(...p);
      if (mode === 'e' || mode === 'w') l.w = Math.max(10, Math.round(2 * Math.abs(lx) / l.scale));
      else l.h = Math.max(4, Math.round(2 * Math.abs(ly) / l.scale));
    }
    frDraw();
  });
  const end = e => {
    if (!pts.has(e.pointerId)) return;
    pts.delete(e.pointerId);
    if (pts.size === 1 && mode === 'pinch') { mode = ''; return; }
    if (pts.size) return;
    if (mode === 'paint') { mode = ''; frPanel(); return; }
    const l = frLayer(fr.sel);
    // tocco senza spostare: testo già scelto = scrivi; foto vuota = scegli la foto
    if (!moved && l && mode === 'move') {
      if (l.type === 'photo' && !fr.images[l.id]) { frPick(l.id); }
      else if (l.type === 'text' && wasSel) frTool('edit', true);
    } else if (!moved && !l && !fr.doc.layers.length && mode !== 'pinch') frPick('new');
    mode = ''; fr.dragging = ''; fr.guides = [0, 0];
    frDraw();
    if (moved && fr.tool) frPanel();
  };
  area.addEventListener('pointerup', end);
  area.addEventListener('pointercancel', end);
  area.addEventListener('wheel', e => {
    const l = frLayer(fr.sel);
    if (!l || l.type === 'shade') return;
    e.preventDefault();
    l.scale = Math.min(8, Math.max(0.05, l.scale * Math.exp(-e.deltaY * 0.0015)));
    frDraw();
  }, {passive:false});
  area.addEventListener('touchmove', e => e.preventDefault(), {passive:false});
  window.addEventListener('resize', frDraw);
  if (typeof ResizeObserver === 'function') new ResizeObserver(() => frDraw()).observe($('frStageBox'));
}

/* ---------- strumenti in basso, come Canva ----------
   Una striscia di strumenti (icona + nome) che cambia con l'elemento scelto; ogni strumento apre
   un pannellino con poche opzioni. Senza niente scelto: aggiungi elementi e impostazioni della pagina. */
const FR_SWATCHES = ['#ffffff', '#000000', '#c9a45c', '#8d8b86', '#ff2d55'];
const FR_SVG = {
  text:'<path d="M5 6V4h14v2M12 4v16M9 20h6"/>',
  photo:'<rect x="3" y="5" width="18" height="14" rx="2"/><circle cx="9" cy="10" r="1.6"/><path d="M21 16l-5-5-9 8"/>',
  logo:'<path d="M12 3l2.4 4.9 5.4.8-3.9 3.8.9 5.4L12 15.4 7.2 17.9l.9-5.4L4.2 8.7l5.4-.8z"/>',
  rect:'<rect x="4" y="6" width="16" height="12" rx="1.5"/>',
  shade:'<rect x="4" y="4" width="16" height="16" rx="2"/><path d="M4 14h16M4 17h16" opacity=".6"/>',
  bg:'<path d="M5 13l6-8 7 7-6 6a2 2 0 0 1-2.8 0L5 13.8"/><path d="M19 15s2 2.2 2 3.5a2 2 0 0 1-4 0c0-1.3 2-3.5 2-3.5z"/>',
  fmt:'<rect x="6" y="3" width="12" height="18" rx="2"/>',
  layers:'<path d="M12 3l9 5-9 5-9-5z"/><path d="M3 13l9 5 9-5"/>',
  caption:'<path d="M4 5h16v11H9l-5 4z"/>',
  tpl:'<path d="M6 3h12v18l-6-4-6 4z"/>',
  edit:'<path d="M4 20l1.2-4.6L15.8 4.8a2 2 0 0 1 2.8 0l.6.6a2 2 0 0 1 0 2.8L8.6 18.8z"/>',
  format:'<path d="M4 6h16M4 10h10M4 14h16M4 18h10"/>',
  fx:'<path d="M12 3v4M12 17v4M3 12h4M17 12h4M5.6 5.6l2.8 2.8M15.6 15.6l2.8 2.8M5.6 18.4l2.8-2.8M15.6 8.4l2.8-2.8"/>',
  opacity:'<circle cx="12" cy="12" r="8"/><path d="M12 4v16M12 4a8 8 0 0 1 0 16" fill="currentColor"/>',
  pos:'<rect x="8" y="8" width="12" height="12" rx="1.5"/><path d="M4 16V5a1 1 0 0 1 1-1h11"/>',
  replace:'<path d="M20 11a8 8 0 0 0-14-5l-2 2M4 4v4h4M4 13a8 8 0 0 0 14 5l2-2M20 20v-4h-4"/>',
  adjust:'<path d="M4 7h10M18 7h2M4 17h4M12 17h8"/><circle cx="16" cy="7" r="2"/><circle cx="10" cy="17" r="2"/>',
  filter:'<circle cx="12" cy="12" r="8"/><path d="M12 4a8 8 0 0 0 0 16z" fill="currentColor"/>',
  shape:'<path d="M5 19L19 5M9 5H5v4M15 19h4v-4"/>',
  done:'<path d="M5 12.5l4.5 4.5L19 7.5"/>',
  erase:'<path d="M8.5 19.5L3.8 14.8a1.6 1.6 0 0 1 0-2.3l8.7-8.7a1.6 1.6 0 0 1 2.3 0l5.4 5.4a1.6 1.6 0 0 1 0 2.3L13 19.5z"/><path d="M8.5 19.5H20M9 9.5l5.5 5.5"/>',
  cutout:'<circle cx="12" cy="8" r="3.2"/><path d="M5.5 20c.6-3.6 3.2-5.6 6.5-5.6s5.9 2 6.5 5.6"/><path d="M3 3l2 2M21 3l-2 2" opacity=".7"/><path d="M3 12h1.5M19.5 12H21"/>',
  dup:'<rect x="8" y="8" width="12" height="12" rx="2"/><path d="M16 8V6a2 2 0 0 0-2-2H6a2 2 0 0 0-2 2v8a2 2 0 0 0 2 2h2"/>',
  del:'<path d="M4 7h16M10 11v6M14 11v6M6 7l1 13h10l1-13M9 7V4h6v3"/>',
  eye:'<path d="M2.5 12S6 5.5 12 5.5 21.5 12 21.5 12 18 18.5 12 18.5 2.5 12 2.5 12z"/><circle cx="12" cy="12" r="3"/>',
  eyeoff:'<path d="M4 4l16 16M9.9 5.8A9.6 9.6 0 0 1 12 5.5c6 0 9.5 6.5 9.5 6.5a17 17 0 0 1-3 3.6M6.5 7.6A17 17 0 0 0 2.5 12S6 18.5 12 18.5a9 9 0 0 0 4-.9M9.9 9.9a3 3 0 0 0 4.2 4.2"/>',
  grip:'<path d="M5 8h14M5 12h14M5 16h14"/>'
};
const FR_TOOLS = {
  page:[['tpl', 'Modelli', 'tpl'], '|', ['add-text', 'Testo', 'text'], ['add-photo', 'Foto', 'photo'], ['add-logo', 'Logo', 'logo'], ['add-rect', 'Forma', 'rect'],
    ['add-shade', 'Sfumatura', 'shade'], '|', ['bg', 'Sfondo', 'bg'], ['fmt', 'Formato', 'fmt'], ['layers', 'Livelli', 'layers'],
    ['caption', 'Didascalia', 'caption']],
  text:[['edit', 'Modifica', 'edit'], ['font', 'Font', null], ['color', 'Colore', null], ['format', 'Formato', 'format'],
    ['fx', 'Effetti', 'fx'], ['opacity', 'Trasparenza', 'opacity'], ['pos', 'Posizione', 'pos']],
  photo:[['replace', 'Sostituisci', 'replace'], ['cutout', 'Rimuovi sfondo', 'cutout'], ['erase', 'Gomma', 'erase'], ['filter', 'Filtri', 'filter'], ['adjust', 'Regola', 'adjust'], ['fx', 'Effetti', 'fx'],
    ['opacity', 'Trasparenza', 'opacity'], ['pos', 'Posizione', 'pos']],
  logo:[['color', 'Colore', null], ['fx', 'Effetti', 'fx'], ['opacity', 'Trasparenza', 'opacity'], ['pos', 'Posizione', 'pos']],
  rect:[['color', 'Colore', null], ['shape', 'Angoli', 'shape'], ['fx', 'Effetti', 'fx'], ['opacity', 'Trasparenza', 'opacity'], ['pos', 'Posizione', 'pos']],
  shade:[['shade', 'Sfumatura', 'shade'], ['color', 'Colore', null], ['pos', 'Posizione', 'pos']]
};

function frSvg(name) {
  return `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">${FR_SVG[name] || ''}</svg>`;
}

function frSelect(id, fromCanvas) {
  if (fr.sel === id) return;
  if (fr.erasing) return;
  fr.sel = id;
  fr.tool = ''; fr.brush = null;
  if (fromCanvas) haptic('select');
  frLayers();
  frPanel();
  frDraw();
}

function frLayerName(l) {
  if (l.type === 'text') return (l.text || 'Testo').split('\n')[0].slice(0, 22) || 'Testo';
  if (l.type === 'photo') return fr.images[l.id] ? 'Foto' : 'Foto da inserire';
  return FR_TYPE_NAMES[l.type] || l.type;
}

// Striscia degli strumenti (e barretta sopra l'elemento).
function frLayers() {
  const bar = $('frTools');
  const emptyTip = 'Tocca la pagina per scegliere una foto.';
  if (fr.doc && !fr.doc.layers.length) showToastSafe(emptyTip, 0);
  else if ($('frStatus').textContent === emptyTip) showToastSafe('');
  bar.innerHTML = '';
  const l = frLayer(fr.sel);
  if (l) {
    const done = document.createElement('button');
    done.type = 'button'; done.className = 'fr-done'; done.setAttribute('aria-label', 'Fine');
    done.innerHTML = frSvg('done');
    done.addEventListener('click', () => { haptic('select'); frSelect(''); });
    bar.appendChild(done);
  }
  (FR_TOOLS[l ? l.type : 'page']).forEach(t => {
    if (t === '|') { const s = document.createElement('span'); s.className = 'fr-tsep'; bar.appendChild(s); return; }
    const [key, label, icon] = t;
    const b = document.createElement('button');
    b.type = 'button'; b.className = 'fr-tool' + (fr.tool === key ? ' on' : '');
    let ico = icon ? frSvg(icon) : '';
    if (key === 'font') ico = `<span class="fr-aa" style="font-family:'FR ${l.font}',sans-serif">Aa</span>`;
    if (key === 'color') {
      const col = l.color === 'auto' ? 'conic-gradient(#fff 0 50%,#000 0)' : l.color;
      ico = `<span class="fr-dot" style="background:${col}"></span>`;
    }
    let text = label;
    if (key === 'cutout') {
      if (fr.cutBusy[l.id]) { b.className += ' busy'; text = 'Attendi…'; }
      else if (l.cutout && fr.cuts[l.id]) { b.className += ' on'; text = 'Sfondo tolto'; }
    }
    b.innerHTML = `<span class="fr-ti">${ico}</span><small></small>`;
    b.querySelector('small').textContent = text;
    b.addEventListener('click', () => frTool(key));
    bar.appendChild(b);
  });
  frFloatButtons();
}

function frFloatButtons() {
  const f = $('frFloat');
  f.innerHTML = '';
  const l = frLayer(fr.sel);
  if (!l) { f.hidden = true; return; }
  const add = (icon, label, fn) => {
    const b = document.createElement('button');
    b.type = 'button'; b.setAttribute('aria-label', label); b.title = label;
    b.innerHTML = frSvg(icon);
    b.addEventListener('pointerdown', e => e.stopPropagation());
    b.addEventListener('click', () => { haptic('select'); fn(); });
    f.appendChild(b);
  };
  if (l.type === 'text') add('edit', 'Modifica il testo', () => frTool('edit', true));
  if (l.type === 'photo') add('replace', 'Sostituisci la foto', () => { frPick(l.id); });
  add('dup', 'Duplica', () => frDuplicate(l));
  add('del', 'Elimina', () => frDelete(l));
}

function frTool(key, open) {
  haptic('select');
  const l = frLayer(fr.sel);
  if (key.startsWith('add-')) { frAdd(key.slice(4)); return; }
  if (key === 'layers') { frSheet(); return; }
  if (key === 'tpl') { frTplSheet(); return; }
  if (key === 'replace') { frPick(l.id); return; }
  if (key === 'cutout') { frCutoutToggle(l); return; }
  if (key === 'erase' && !fr.images[l.id]) { frPick(l.id); return; }
  if (fr.erasing) return;
  fr.tool = fr.tool === key && !open ? '' : key;
  fr.brush = fr.tool === 'erase' ? {id:l.id, strokes:[]} : null;
  frLayers();
  frPanel();
  frDraw();
  if (key === 'edit' && fr.tool) setTimeout(() => { const t = $('frPanel').querySelector('textarea'); if (t) { t.focus(); t.select(); } }, 60);
  if (key === 'font') FR_FONTS.forEach(f => frFont(f[0]));
}

// Livelli, come in Canva: in cima quello davanti; anteprima, occhio, maniglia per trascinare.
function frSheet() {
  const sheet = $('frSheet'), body = $('frSheetBody');
  body.innerHTML = '';
  $('frSheetTitle').textContent = 'Livelli';
  const layers = [...fr.doc.layers].reverse();
  if (!layers.length) {
    const p = document.createElement('p'); p.className = 'hint'; p.textContent = 'Ancora niente: aggiungi un testo o una foto.'; body.appendChild(p);
  } else {
    const tip = document.createElement('p');
    tip.className = 'hint fr-ltip';
    tip.textContent = 'In cima c\'è quello davanti. Tieni premuto ≡ e trascina per cambiare l\'ordine.';
    body.appendChild(tip);
  }
  const list = document.createElement('div');
  list.className = 'fr-llist';
  layers.forEach(l => {
    const r = document.createElement('div');
    r.className = 'fr-lrow' + (l.id === fr.sel ? ' on' : '') + (l.hidden ? ' off' : '');
    r.dataset.id = l.id;
    r.setAttribute('role', 'button');
    const thumb = document.createElement('canvas');
    thumb.className = 'fr-lthumb';
    const txt = document.createElement('span');
    txt.className = 'fr-ltxt';
    txt.innerHTML = '<b></b><small></small>';
    txt.querySelector('b').textContent = frLayerName(l);
    const kind = FR_TYPE_NAMES[l.type] || '';
    txt.querySelector('small').textContent = kind === frLayerName(l) ? '' : kind;
    const eye = document.createElement('button');
    eye.type = 'button'; eye.className = 'fr-lbtn';
    const setEye = () => { eye.innerHTML = frSvg(l.hidden ? 'eyeoff' : 'eye'); eye.setAttribute('aria-label', l.hidden ? 'Mostra' : 'Nascondi'); };
    setEye();
    eye.addEventListener('click', e => {
      e.stopPropagation(); haptic('select');
      l.hidden = !l.hidden; setEye(); r.classList.toggle('off', !!l.hidden);
      if (l.hidden && fr.sel === l.id) { fr.sel = ''; fr.tool = ''; fr.brush = null; frLayers(); frPanel(); }
      frDraw();
    });
    const grip = document.createElement('span');
    grip.className = 'fr-lgrip'; grip.setAttribute('aria-label', 'Trascina per spostare');
    grip.innerHTML = frSvg('grip');
    grip.addEventListener('pointerdown', e => frLayerDrag(e, r, list));
    grip.addEventListener('click', e => e.stopPropagation());
    const del = document.createElement('button');
    del.type = 'button'; del.className = 'fr-lbtn fr-ldel'; del.setAttribute('aria-label', 'Elimina');
    del.innerHTML = frSvg('del');
    del.addEventListener('click', e => { e.stopPropagation(); haptic('select'); frDelete(l); frSheet(); });
    r.append(thumb, txt, eye, del, grip);
    r.addEventListener('click', () => {
      if (l.hidden) { l.hidden = false; frDraw(); }
      frSheetClose(); frSelect(l.id);
    });
    list.appendChild(r);
    frLayerThumb(thumb, l);
  });
  body.appendChild(list);
  sheet.hidden = false;
  requestAnimationFrame(() => sheet.classList.add('open'));
}

// Anteprima di un livello da solo, ingrandito su quell'elemento (la sfumatura: tutta la pagina), sulla scacchiera.
function frLayerThumb(canvas, l) {
  const S = 40, dpr = 2;
  canvas.width = S * dpr; canvas.height = S * dpr;
  canvas.style.width = `${S}px`; canvas.style.height = `${S}px`;
  let cx = fr.doc.w / 2, cy = fr.doc.h / 2, size = Math.max(fr.doc.w, fr.doc.h);
  if (l.type !== 'shade') {
    try { const g = frGeom(l); cx = l.x; cy = l.y; size = Math.max(g.w, g.h) * 1.08; } catch (_) {}
  }
  const ctx = canvas.getContext('2d');
  const keep = [fr.k, fr.editing];
  fr.k = S * dpr / Math.max(1, size); fr.editing = true;
  ctx.setTransform(fr.k, 0, 0, fr.k, S * dpr / 2 - cx * fr.k, S * dpr / 2 - cy * fr.k);
  try { frDrawLayer(ctx, l); } catch (_) {}
  [fr.k, fr.editing] = keep;
}

// Trascina un livello nell'elenco: le altre righe si spostano, al rilascio cambia l'ordine.
function frLayerDrag(e, row, list) {
  e.preventDefault(); e.stopPropagation();
  const grip = e.currentTarget;
  const rows = [...list.children], from = rows.indexOf(row);
  const step = rows.length > 1 ? rows[1].offsetTop - rows[0].offsetTop : row.offsetHeight;
  const y0 = e.clientY;
  let to = from;
  grip.setPointerCapture(e.pointerId);
  row.classList.add('drag');
  haptic('select');
  const move = ev => {
    const dy = Math.max(-from * step - 6, Math.min((rows.length - 1 - from) * step + 6, ev.clientY - y0));
    row.style.transform = `translateY(${dy}px)`;
    const nt = Math.max(0, Math.min(rows.length - 1, from + Math.round(dy / step)));
    if (nt === to) return;
    to = nt; haptic('select');
    rows.forEach((r, i) => {
      if (r === row) return;
      const s = from < to && i > from && i <= to ? -step : from > to && i < from && i >= to ? step : 0;
      r.style.transform = s ? `translateY(${s}px)` : '';
    });
  };
  const up = () => {
    grip.removeEventListener('pointermove', move);
    grip.removeEventListener('pointerup', up);
    grip.removeEventListener('pointercancel', up);
    row.classList.remove('drag');
    rows.forEach(r => { r.style.transform = ''; });
    if (to === from) return;
    const ids = rows.map(r => r.dataset.id);
    ids.splice(to, 0, ids.splice(from, 1)[0]);
    const byId = Object.fromEntries(fr.doc.layers.map(l => [l.id, l]));
    fr.doc.layers = ids.reverse().map(id => byId[id]);
    haptic('success');
    frLayers(); frDraw(); frSheet();
  };
  grip.addEventListener('pointermove', move);
  grip.addEventListener('pointerup', up);
  grip.addEventListener('pointercancel', up);
}

function frSheetClose() {
  const sheet = $('frSheet');
  sheet.classList.remove('open');
  setTimeout(() => { if (!sheet.classList.contains('open')) sheet.hidden = true; }, 220);
}

// Controlli: costruiti da una lista, ognuno legge e scrive un campo del livello (anche annidato: 'glow.on').
function frGet(o, path) { return path.split('.').reduce((a, k) => a && a[k], o); }
function frSet(o, path, v) { const ks = path.split('.'); const last = ks.pop(); ks.reduce((a, k) => a[k], o)[last] = v; }

function frControl(target, c) {
  const row = document.createElement(c.type === 'range' ? 'label' : 'div');
  row.className = 'fr-row' + (c.wide ? ' wide' : '') + (c.sub ? ' sub' : '');
  const name = document.createElement('span');
  name.textContent = c.label;
  row.appendChild(name);
  const v = frGet(target, c.key);
  let input;
  const changed = val => {
    frSet(target, c.key, val);
    if (c.after) c.after(val);
    frDraw();
    if (c.rebuild) frPanel();
    if (c.key === 'color' || c.key === 'text') frLayers();
  };
  if (c.type === 'range') {
    input = document.createElement('input');
    input.type = 'range'; input.min = c.min; input.max = c.max; input.step = c.step || 1; input.value = v;
    const out = document.createElement('em');
    out.textContent = c.fmt ? c.fmt(v) : Math.round(v);
    input.addEventListener('input', () => { const n = Number(input.value); out.textContent = c.fmt ? c.fmt(n) : Math.round(n); changed(n); });
    row.append(input, out);
    return row;
  }
  if (c.type === 'color') {
    // colori veloci + il selettore per tutti gli altri
    input = document.createElement('div');
    input.className = 'fr-sws';
    const list = c.auto ? ['auto', ...FR_SWATCHES] : FR_SWATCHES;
    const pick = document.createElement('input');
    pick.type = 'color'; pick.className = 'fr-sw-pick'; pick.setAttribute('aria-label', 'Altro colore');
    pick.value = /^#[0-9a-f]{6}$/i.test(v) ? v : '#ffffff';
    const mark = () => input.querySelectorAll('.fr-swc').forEach(b => b.classList.toggle('on', b.dataset.c === frGet(target, c.key)));
    list.forEach(col => {
      const b = document.createElement('button');
      b.type = 'button'; b.className = 'fr-swc' + (col === 'auto' ? ' auto' : ''); b.dataset.c = col;
      b.setAttribute('aria-label', col === 'auto' ? 'Automatico' : col);
      if (col === 'auto') b.textContent = 'A'; else b.style.background = col;
      b.addEventListener('click', e => { e.preventDefault(); haptic('select'); changed(col); mark(); });
      input.appendChild(b);
    });
    pick.addEventListener('input', () => { changed(pick.value); mark(); });
    input.appendChild(pick);
    mark();
  } else if (c.type === 'toggle') {
    input = document.createElement('button');
    input.type = 'button';
    input.className = 'fr-sw' + (v ? ' on' : '');
    input.setAttribute('role', 'switch');
    input.setAttribute('aria-checked', v ? 'true' : 'false');
    input.addEventListener('click', e => { e.preventDefault(); haptic('select'); changed(!frGet(target, c.key)); frPanel(); });
  } else if (c.type === 'seg') {
    input = document.createElement('div');
    input.className = 'fr-seg';
    c.options.forEach(([val, text]) => {
      const b = document.createElement('button');
      b.type = 'button'; b.textContent = text; b.className = val === v ? 'on' : '';
      b.addEventListener('click', () => { haptic('select'); changed(val); input.querySelectorAll('button').forEach(x => x.classList.toggle('on', x === b)); });
      input.appendChild(b);
    });
  } else if (c.type === 'textarea') {
    input = document.createElement('textarea');
    input.rows = c.rows || 2; input.value = v || ''; input.maxLength = c.max || 300;
    if (c.placeholder) input.placeholder = c.placeholder;
    input.addEventListener('input', () => changed(input.value));
  }
  input.classList.add('fr-in');
  row.appendChild(input);
  return row;
}

function frCard(target, controls) {
  const g = document.createElement('div');
  g.className = 'fr-card';
  controls.filter(Boolean).forEach(c => g.appendChild(c instanceof Node ? c : frControl(target, c)));
  return g;
}

function frButton(text, fn, cls='btn') {
  const b = document.createElement('button');
  b.type = 'button'; b.className = cls; b.textContent = text;
  b.addEventListener('click', fn);
  return b;
}

function frEffectControls(l) {
  return [
    {key:'glow.on', label:'Bagliore', type:'toggle'},
    l.glow.on && {key:'glow.color', label:'Colore', type:'color', sub:true},
    l.glow.on && {key:'glow.strength', label:'Intensità', type:'range', min:5, max:100, sub:true},
    l.glow.on && {key:'glow.blur', label:'Ampiezza', type:'range', min:1, max:120, sub:true},
    {key:'shadow.on', label:'Ombra', type:'toggle'},
    l.shadow.on && {key:'shadow.strength', label:'Intensità', type:'range', min:5, max:100, sub:true},
    l.shadow.on && {key:'shadow.blur', label:'Morbidezza', type:'range', min:0, max:120, sub:true},
    l.shadow.on && {key:'shadow.dy', label:'Distanza', type:'range', min:0, max:80, sub:true},
    ...(l.type === 'text' ? [{key:'stroke.on', label:'Contorno', type:'toggle'},
      l.stroke.on && {key:'stroke.color', label:'Colore', type:'color', sub:true},
      l.stroke.on && {key:'stroke.width', label:'Spessore', type:'range', min:1, max:40, sub:true}] : []),
  ];
}

// Pannellino dello strumento aperto (sopra la striscia).
function frPanel() {
  const box = $('frPanel');
  box.innerHTML = '';
  const l = frLayer(fr.sel), t = fr.tool;
  box.hidden = !t;
  if (!t) return;
  const put = el => box.appendChild(el);
  if (!l) {
    if (t === 'bg') put(frCard(fr.doc, [{key:'bg', label:'Sfondo', type:'color'}]));
    else if (t === 'fmt') {
      const holder = {_fmt:(FR_FORMATS.find(f => f[1] === fr.doc.w && f[2] === fr.doc.h) || FR_FORMATS[0])[0]};
      put(frCard(holder, [{key:'_fmt', label:'Formato', type:'seg', options:FR_FORMATS.map(f => [f[0], f[0]]), after:v => frFormat(v)}]));
    } else if (t === 'caption') put(frCard(fr.doc, [{key:'caption', label:'Testo del post (facoltativo)', type:'textarea', rows:3, max:900, wide:true, placeholder:'Scrivi la didascalia…'}]));
    return;
  }
  if (t === 'edit') put(frCard(l, [{key:'text', label:'', type:'textarea', wide:true, rows:2, placeholder:'Scrivi…'}]));
  else if (t === 'font') {
    const list = document.createElement('div');
    list.className = 'fr-fonts';
    FR_FONTS.forEach(([name]) => {
      const b = document.createElement('button');
      b.type = 'button'; b.className = 'fr-font' + (l.font === name ? ' on' : '');
      b.style.fontFamily = `'FR ${name}', sans-serif`;
      b.textContent = name;
      b.addEventListener('click', () => { haptic('select'); l.font = name; frFont(name); frDraw(); frLayers(); list.querySelectorAll('.fr-font').forEach(x => x.classList.toggle('on', x === b)); });
      list.appendChild(b);
    });
    put(list);
  } else if (t === 'color') put(frCard(l, [{key:'color', label:'Colore', type:'color', auto:l.type === 'logo'}]));
  else if (t === 'format') put(frCard(l, [
    {key:'align', label:'Allinea', type:'seg', options:[['left', 'Sinistra'], ['center', 'Centro'], ['right', 'Destra']]},
    {key:'upper', label:'Maiuscolo', type:'toggle'},
    {key:'spacing', label:'Spaziatura', type:'range', min:-20, max:80},
    {key:'line', label:'Interlinea', type:'range', min:60, max:200},
    {key:'fit', label:'Largh. max', type:'range', min:0, max:fr.doc.w, step:10, fmt:n => n ? Math.round(n) : 'libera'},
  ]));
  else if (t === 'fx') put(frCard(l, frEffectControls(l)));
  else if (t === 'opacity') put(frCard(l, [{key:'opacity', label:'Trasparenza', type:'range', min:0, max:100, fmt:n => `${Math.round(n)}%`}]));
  else if (t === 'filter') put(frCard(l, [{key:'bw', label:'Bianco e nero', type:'toggle'}, {key:'sharpen', label:'Più nitida', type:'toggle'}]));
  else if (t === 'adjust') put(frCard(l, [
    {key:'bright', label:'Luminosità', type:'range', min:-60, max:60},
    {key:'contrast', label:'Contrasto', type:'range', min:-60, max:80},
    {key:'blur', label:'Sfocatura', type:'range', min:0, max:40},
  ]));
  else if (t === 'erase') {
    const tip = document.createElement('p');
    tip.className = 'hint fr-note';
    tip.textContent = fr.erasing ? 'Cancello e ricostruisco il dietro… ci vuole qualche secondo.'
      : 'Togli la persona con un tocco, oppure passa il dito su quello che vuoi far sparire e tocca Cancella.';
    put(tip);
    const quick = frButton(fr.erasing ? 'Attendi…' : 'Togli la persona (un tocco)', () => frErase(l, true), 'btn fr-save fr-quick');
    quick.disabled = fr.erasing;
    put(quick);
    put(frCard(fr, [{key:'brushSize', label:'Pennello', type:'range', min:12, max:110}]));
    const row = document.createElement('div');
    row.className = 'fr-arrange';
    const n = fr.brush ? fr.brush.strokes.length : 0;
    [['Annulla tratto', () => { fr.brush.strokes.pop(); frDraw(); frPanel(); }, !n || fr.erasing],
      ['Foto originale', () => frEraseUndo(l), !(fr.undo[l.id] || []).length || fr.erasing]]
      .forEach(([text, fn, off]) => { const b = frButton(text, () => { haptic('select'); fn(); }, 'fr-act'); b.disabled = off; row.appendChild(b); });
    put(row);
    const go = frButton(fr.erasing ? 'Cancello…' : 'Cancella', () => frErase(l), 'btn fr-save');
    go.disabled = !n || fr.erasing;
    put(go);
  }
  else if (t === 'shape') put(frCard(l, [{key:'radius', label:'Angoli', type:'range', min:0, max:400}]));
  else if (t === 'shade') put(frCard(l, [
    {key:'dir', label:'Da', type:'seg', options:[['bottom', 'Basso'], ['top', 'Alto'], ['left', 'Sx'], ['right', 'Dx']]},
    {key:'from', label:'Parte da', type:'range', min:0, max:95},
    {key:'strength', label:'Intensità', type:'range', min:0, max:100},
  ]));
  else if (t === 'pos') {
    const row = document.createElement('div');
    row.className = 'fr-arrange';
    const i = fr.doc.layers.indexOf(l);
    [['Avanti', () => frMove(l, 1), i === fr.doc.layers.length - 1], ['Indietro', () => frMove(l, -1), i === 0],
      ['Centra', () => { l.x = fr.doc.w / 2; l.y = fr.doc.h / 2; frDraw(); }, l.type === 'shade'],
      ['Raddrizza', () => { l.rot = 0; frDraw(); }, l.type === 'shade' || !l.rot], ['Livelli', () => frSheet(), false],
      ...(l.type === 'logo' ? [['Al suo posto', () => { frLogoHome(l); frDraw(); }, false]] : []),
      ['Duplica', () => frDuplicate(l), false], ['Elimina', () => frDelete(l), false]]
      .forEach(([text, fn, off]) => { const b = frButton(text, () => { haptic('select'); fn(); frPanel(); }, 'fr-act' + (text === 'Elimina' ? ' danger' : '')); b.disabled = off; row.appendChild(b); });
    put(row);
  }
}

function frAdd(type) {
  haptic('select');
  if (type === 'photo') { frPick('new'); return; }    // il livello nasce solo con una foto vera
  const had = type === 'logo' && fr.doc.layers.find(x => x.type === 'logo');
  if (had) {                                          // il logo è uno: lo rimetto al suo posto e lo scelgo
    had.hidden = false; frLogoHome(had);
    fr.sel = had.id; fr.tool = '';
    frLayers(); frPanel(); frDraw();
    return;
  }
  const l = frNew(type);
  fr.doc.layers.push(l);
  if (type === 'text') frFont(l.font);
  if (type === 'logo') frLogo().then(() => { frLogoHome(l); frDraw(); }).catch(() => {});
  fr.sel = l.id; fr.tool = type === 'text' ? 'edit' : '';
  frLayers(); frPanel(); frDraw();
  if (type === 'text') setTimeout(() => { const ta = $('frPanel').querySelector('textarea'); if (ta) { ta.focus(); ta.select(); } }, 60);
}

function frMove(l, dir) {
  const a = fr.doc.layers, i = a.indexOf(l), j = i + dir;
  if (j < 0 || j >= a.length) return;
  [a[i], a[j]] = [a[j], a[i]];
  frLayers(); frDraw();
}

function frDuplicate(l) {
  const c = {...frClone(l), id:frId(), x:l.x + 40, y:l.y + 40};
  if (fr.images[l.id]) fr.images[c.id] = fr.images[l.id];
  if (fr.cuts[l.id]) fr.cuts[c.id] = fr.cuts[l.id];
  fr.doc.layers.splice(fr.doc.layers.indexOf(l) + 1, 0, c);
  fr.sel = c.id; fr.tool = ''; fr.brush = null;
  frLayers(); frPanel(); frDraw();
}

function frDelete(l) {
  fr.doc.layers = fr.doc.layers.filter(x => x !== l);
  delete fr.images[l.id]; delete fr.cuts[l.id]; delete fr.undo[l.id]; delete fr.cache[l.id];
  fr.sel = ''; fr.tool = ''; fr.brush = null;
  frLayers(); frPanel(); frDraw();
}

function frFormat(name) {
  const f = FR_FORMATS.find(x => x[0] === name);
  if (!f) return;
  const kx = f[1] / fr.doc.w, ky = f[2] / fr.doc.h;
  fr.doc.layers.forEach(l => { l.x *= kx; l.y *= ky; });
  fr.doc.w = f[1]; fr.doc.h = f[2];
  fr.doc.layers.forEach(l => { if (l.type === 'logo') frLogoHome(l); });   // il logo resta al suo posto
  frDraw();
}

// Apre la galleria. target: id del livello foto, 'new' = livello nuovo; tpl = modello da aprire con questa foto.
// Se non scegli niente non succede niente: nessun posto vuoto.
function frPick(target, tpl='') {
  fr.photoFor = target || 'new'; fr.pickTpl = tpl;
  $('frFile').click();
}

async function frPhotoPicked(file) {
  const target = fr.photoFor, tpl = fr.pickTpl;
  fr.photoFor = ''; fr.pickTpl = '';
  if (!file) return;
  let img;
  try { img = await frReadPhoto(file); } catch (_) { showError('Foto non leggibile.'); $('frFile').value = ''; return; }
  $('frFile').value = '';
  if (tpl) { frApplyTpl(tpl, img); return; }
  // la foto va nel livello scelto, altrimenti in un livello nuovo (la prima fa da sfondo, le altre sopra)
  let l = target !== 'new' ? frLayer(target) : null;
  if (!l) {
    l = frNew('photo');
    if (fr.doc.layers.some(x => x.type === 'photo')) fr.doc.layers.push(l); else fr.doc.layers.unshift(l);
  }
  try {
    fr.images[l.id] = img;
    delete fr.cuts[l.id]; delete fr.undo[l.id]; delete fr.cache[l.id];
    fr.sel = l.id;
    haptic('success');
    if (l.cutout) frCutout(l);              // modello con la foto senza sfondo: lo tolgo anche da questa
  } catch (_) { showError('Foto non leggibile.'); }
  frLayers(); frPanel(); frDraw(); renderSteps();
}

/* ---------- gomma ----------
   Come in HALF/END/FULL quando si sposta la persona: il servizio cancella la zona e ricostruisce
   il dietro (LaMa). La maschera è disegnata alla misura della foto, con la stessa posizione,
   zoom e rotazione del livello: quello che si vede sotto il dito è quello che sparisce. */
async function frErase(l, subject=false) {
  const src = fr.images[l.id];
  const painted = !!(fr.brush && fr.brush.id === l.id && fr.brush.strokes.length);
  if (!src || (!subject && !painted) || fr.erasing) return;
  if (!directBase || !session) { showError('Sessione vecchia. Riavvia ImageGen dal workflow.'); return; }
  const [w] = frPhotoSize(l);
  const m = document.createElement('canvas');
  m.width = src.width; m.height = src.height;
  const ctx = m.getContext('2d');
  ctx.fillStyle = '#000'; ctx.fillRect(0, 0, m.width, m.height);
  const s = src.width / w;
  ctx.setTransform(1, 0, 0, 1, 0, 0);
  ctx.translate(m.width / 2, m.height / 2);
  ctx.scale(s, s);
  ctx.rotate(-l.rot * Math.PI / 180);
  ctx.translate(-l.x, -l.y);
  ctx.strokeStyle = ctx.fillStyle = '#fff';
  ctx.lineCap = ctx.lineJoin = 'round';
  for (const st of painted ? fr.brush.strokes : []) {
    ctx.lineWidth = st.r * 2;
    ctx.beginPath();
    if (st.pts.length === 1) { ctx.arc(st.pts[0][0], st.pts[0][1], st.r, 0, Math.PI * 2); ctx.fill(); continue; }
    st.pts.forEach(([x, y], i) => (i ? ctx.lineTo(x, y) : ctx.moveTo(x, y)));
    ctx.stroke();
  }
  fr.erasing = true;
  haptic('select');
  frPanel(); frLayers();
  showToastSafe(subject ? 'Cerco la persona e la tolgo… ci vuole un po\'.' : 'Cancello… ci vuole qualche secondo.', 0);
  try {
    const send = async (blob, type) => {
      const r = await netFetch(`${directBase}/upload`, {method:'POST', headers:{'Content-Type':type, 'X-ImageGEN-Session':session}, body:blob}, 60000);
      const a = await r.json().catch(() => ({}));
      if (!r.ok || !a.ok) throw new Error(a.error || 'Caricamento non riuscito.');
      return a.photo_id;
    };
    const photoId = await send(await new Promise(r => src.toBlob(r, 'image/jpeg', 0.95)), 'image/jpeg');
    const maskId = painted ? await send(await new Promise(r => m.toBlob(r, 'image/png')), 'image/png') : '';
    if (subject) await frWaitCutout(photoId, () => fr.images[l.id] !== src);   // scontorno pronto prima (richieste brevi)
    // lavoro in background sul servizio: la stessa richiesta breve ripetuta finché arriva l'immagine
    const body = JSON.stringify({v:1, session, photo_id:photoId, mask_id:maskId, subject});
    const t0 = performance.now();
    let a = {};
    for (;;) {
      if (fr.images[l.id] !== src) return;
      const r = await netFetch(`${directBase}/erase`, {method:'POST', headers:{'Content-Type':'application/json', 'X-ImageGEN-Session':session}, body},
        20000, 1).catch(() => null);
      a = r ? await r.json().catch(() => ({})) : {};
      if (r && !r.ok && r.status < 500) throw new Error(a.error || 'Cancellazione non riuscita.');
      if (a.state === 'ready' && a.image) break;
      if (a.state === 'error') throw new Error(a.error || 'Cancellazione non riuscita.');
      if (performance.now() - t0 > 420000) throw new Error('La cancellazione sta impiegando troppo. Riprova.');
      await new Promise(resolve => setTimeout(resolve, 1500));
    }
    const bmp = await createImageBitmap(await (await fetch(a.image)).blob());
    if (fr.images[l.id] !== src) return;
    const c = document.createElement('canvas');
    c.width = src.width; c.height = src.height;
    c.getContext('2d').drawImage(bmp, 0, 0, c.width, c.height);
    (fr.undo[l.id] = fr.undo[l.id] || []).push(src);
    fr.images[l.id] = c;
    delete fr.cuts[l.id]; delete fr.cache[l.id];
    if (fr.brush && painted) fr.brush.strokes = [];
    haptic('success');
    showToastSafe(subject ? 'Persona tolta.' : 'Fatto.');
    if (l.cutout) { l.cutout = false; frCutout(l); }       // lo sfondo tolto va rifatto sulla foto nuova
  } catch (err) {
    showToastSafe('');
    showError((err && err.message) || 'Cancellazione non riuscita.');
  } finally {
    fr.erasing = false;
    frLayers(); frPanel(); frDraw();
  }
}

function frEraseUndo(l) {
  const stack = fr.undo[l.id];
  if (!stack || !stack.length) return;
  fr.images[l.id] = stack.pop();
  delete fr.cuts[l.id]; delete fr.cache[l.id];
  if (l.cutout) { l.cutout = false; frCutout(l); }
  frLayers(); frPanel(); frDraw();
}

/* ---------- rimuovi sfondo ----------
   Stesso scontorno delle altre grafiche (gira sul servizio): carico la foto, chiedo lo stato con
   richieste brevi e scarico il PNG trasparente, riportato alle misure della foto: posizione,
   zoom ed effetti restano uguali. Si può riaccendere/spegnere senza rifarlo. */
function frCutoutToggle(l) {
  if (!fr.images[l.id]) { frPick(l.id); return; }
  if (fr.cutBusy[l.id]) return;
  if (l.cutout && fr.cuts[l.id]) l.cutout = false;
  else if (fr.cuts[l.id]) l.cutout = true;
  else { frCutout(l); return; }
  delete fr.cache[l.id];
  frLayers(); frDraw();
}

// Aspetta lo scontorno sul servizio con richieste brevi (una sola lunga attraverso il tunnel cade).
// true = pronto, false = non serve più (stale()).
async function frWaitCutout(photoId, stale) {
  const q = `session=${encodeURIComponent(session)}&id=${photoId}`;
  const t0 = performance.now();
  for (;;) {
    if (stale()) return false;
    const r = await netFetch(`${directBase}/cutout_state?${q}&start=1`, {}, 10000, 1).catch(() => null);
    const b = r ? await r.json().catch(() => ({})) : {};
    if (r && r.ok && b.ok) {
      if (b.state === 'ready') return true;
      if (b.state === 'error') throw new Error(b.error || 'Scontorno non riuscito.');
    } else if (r && r.status === 404) return true;
    if (performance.now() - t0 > 300000) throw new Error('Lo scontorno sta impiegando troppo. Riprova.');
    await new Promise(resolve => setTimeout(resolve, 1200));
  }
}

async function frCutout(l) {
  const src = fr.images[l.id];
  if (!src || fr.cutBusy[l.id]) return;
  if (!directBase || !session) { showError('Sessione vecchia. Riavvia ImageGen dal workflow.'); return; }
  fr.cutBusy[l.id] = true;
  l.cutout = true;
  frLayers();
  showToastSafe('Tolgo lo sfondo… ci vuole qualche secondo.', 0);
  try {
    const blob = await new Promise(resolve => src.toBlob(resolve, 'image/jpeg', 0.93));
    const up = await netFetch(`${directBase}/upload`, {method:'POST', headers:{'Content-Type':'image/jpeg', 'X-ImageGEN-Session':session}, body:blob}, 60000);
    const a = await up.json().catch(() => ({}));
    if (!up.ok || !a.ok) throw new Error(a.error || 'Caricamento non riuscito.');
    const q = `session=${encodeURIComponent(session)}&id=${a.photo_id}`;
    if (!await frWaitCutout(a.photo_id, () => fr.images[l.id] !== src)) return;   // nel frattempo la foto è cambiata
    const r = await netFetch(`${directBase}/cutout?${q}`, {}, 60000, 5, true);
    if (!r.ok) throw new Error('Scontorno non riuscito.');
    const bmp = await createImageBitmap(await r.blob());
    if (fr.images[l.id] !== src) return;
    const c = document.createElement('canvas');
    c.width = src.width; c.height = src.height;
    c.getContext('2d').drawImage(bmp, 0, 0, c.width, c.height);
    fr.cuts[l.id] = c;
    delete fr.cache[l.id];
    haptic('success');
    showToastSafe('Sfondo tolto.');
  } catch (err) {
    l.cutout = false;
    showToastSafe('');
    showError((err && err.message) || 'Scontorno non riuscito.');
  } finally {
    delete fr.cutBusy[l.id];
    frLayers(); frPanel(); frDraw();
  }
}

/* ---------- modelli ---------- */
async function frTemplatesCall(body) {
  const r = await netFetch(`${directBase}/templates`, {
    method:'POST', headers:{'Content-Type':'application/json', 'X-ImageGEN-Session':session}, body:JSON.stringify({v:1, session, ...body})
  }, 30000, 2);
  const a = await r.json().catch(() => ({}));
  if (!r.ok || !a.ok) throw new Error(a.error || 'Modelli non disponibili.');
  fr.templates = a.templates || [];
  return fr.templates;
}

function frDocForTemplate() {
  const d = frClone(fr.doc);
  d.layers.forEach(l => { delete l._rx; delete l._ry; });
  delete d.caption;                // la didascalia cambia ogni volta
  return d;
}

function frSaveTemplate(asNew) {
  const doSave = name => {
    name = String(name || '').trim();
    if (!name) return;
    const id = !asNew && fr.tplId ? fr.tplId : Math.random().toString(36).slice(2, 12).padEnd(8, '0');
    frTemplatesCall({action:'save', template:{id, name, doc:frDocForTemplate()}})
      .then(() => { fr.tplId = id; fr.tplName = name; haptic('success'); if (!$('frSheet').hidden) frTplSheet(); showToastSafe('Modello salvato.'); })
      .catch(err => showError(err.message));
  };
  if (!asNew && fr.tplId) { doSave(fr.tplName); return; }
  frAskName('Nome del modello', '', doSave);
}

function frAskName(title, value, done) {
  const name = window.prompt(title, value || '');
  if (name !== null) done(name);
}

function showToastSafe(text, ms=2200) {
  const s = $('frStatus');
  if (!s) return;
  s.textContent = text;
  clearTimeout(showToastSafe.t);
  if (ms) showToastSafe.t = setTimeout(() => { s.textContent = ''; }, ms);
}

function frOpenDoc(doc, tpl) {
  fr.doc = frClone(doc);
  fr.doc.caption = fr.doc.caption || '';
  fr.doc.layers.forEach(l => { l.id = frId(); });         // id nuovi: le foto vanno rimesse
  fr.images = {}; fr.cuts = {}; fr.cutBusy = {}; fr.undo = {}; fr.brush = null; fr.cache = {};
  fr.sel = ''; fr.tool = '';
  fr.tplId = tpl ? tpl.id : '';
  fr.tplName = tpl ? tpl.name : '';
  fr.exportKey = ''; fr.exportId = '';
  fr.doc.layers.forEach(l => { if (l.type === 'text') frFont(l.font); });
  frLogo();
}

function frTplDoc(choice) {
  if (choice === 'new') return frBlank();
  const t = (fr.templates || []).find(x => x.id === choice);
  return t ? t.doc : null;
}

// Apre un modello con la foto: la prima foto del modello prende questa, i posti foto senza foto spariscono.
function frApplyTpl(choice, img) {
  haptic('select');
  if (choice === 'new') frOpenDoc(frBlank());
  else {
    const t = (fr.templates || []).find(x => x.id === choice);
    if (!t) return;
    frOpenDoc(t.doc, t);
  }
  fr.choice = choice;
  const first = fr.doc.layers.find(l => l.type === 'photo');
  if (first && img) fr.images[first.id] = img;
  fr.doc.layers = fr.doc.layers.filter(l => l.type !== 'photo' || fr.images[l.id]);
  fr.sel = '';
  if (first && img && first.cutout) frCutout(first);
  frSheetClose();
  frLayers(); frPanel(); frDraw(); renderSteps();
}

function frChoose(choice) {
  const doc = frTplDoc(choice);
  if (!doc) return;
  const photo = fr.doc && fr.doc.layers.find(l => l.type === 'photo' && fr.images[l.id]);
  const img = photo ? fr.images[photo.id] : null;
  // il modello vuole una foto e non ce n'è ancora: prima la galleria (se annulli, resta tutto com'è)
  if (!img && doc.layers.some(l => l.type === 'photo')) { frPick('', choice); return; }
  if (fr.doc && fr.doc.layers.length) askConfirm('Aprire il modello? Testi e livelli di adesso si perdono (la foto resta).', () => frApplyTpl(choice, img));
  else frApplyTpl(choice, img);
}

// Modelli, dentro l'editor: salva la pagina, apri un modello, elimina quelli salvati.
function frTplSheet() {
  const sheet = $('frSheet'), body = $('frSheetBody');
  body.innerHTML = '';
  $('frSheetTitle').textContent = 'Modelli';
  const save = frButton(fr.tplId ? `Salva "${fr.tplName}"` : 'Salva questa pagina come modello', () => frSaveTemplate(), 'btn fr-save');
  save.disabled = !fr.doc.layers.length;
  body.appendChild(save);
  if (fr.tplId) body.appendChild(frButton('Salva come nuovo modello', () => frSaveTemplate(true), 'link-btn fr-save2'));
  const tip = document.createElement('p');
  tip.className = 'hint fr-ltip fr-tpltip';
  tip.textContent = 'Tocca un modello per aprirlo: tornano testi, stili e posizioni; la foto che hai messo resta.';
  const box = document.createElement('div');
  box.id = 'frTplList'; box.className = 'fr-tpls';
  body.append(tip, box);
  frTplRender();
  sheet.hidden = false;
  requestAnimationFrame(() => sheet.classList.add('open'));
  if (fr.templates === null && directBase && session)
    frTemplatesCall({action:'list'}).then(frTplRender).catch(() => { fr.templates = []; frTplRender(); });
}

function frTplRender() {
  const box = $('frTplList');
  if (!box) return;
  box.innerHTML = '';
  const rows = [['new', 'Nuova pagina vuota', 'Parti da zero']];
  (fr.templates || []).forEach(t => rows.push([t.id, t.name, 'Modello salvato', t]));
  rows.forEach(([id, title, sub, t]) => {
    const b = document.createElement('div');
    b.className = 'fr-tpl' + (fr.choice === id ? ' selected' : '');
    b.setAttribute('role', 'button');
    b.tabIndex = 0;
    const thumb = document.createElement('canvas');
    thumb.className = 'fr-thumb';
    const txt = document.createElement('div');
    txt.className = 'fr-tpl-txt';
    txt.innerHTML = '<b></b><small></small>';
    txt.querySelector('b').textContent = title;
    txt.querySelector('small').textContent = sub;
    b.append(thumb, txt);
    if (t) {
      const del = document.createElement('button');
      del.type = 'button'; del.className = 'link-btn fr-del'; del.textContent = 'Elimina';
      del.addEventListener('click', e => {
        e.stopPropagation();
        askConfirm(`Eliminare il modello "${t.name}"?`, () => frTemplatesCall({action:'delete', id:t.id})
          .then(() => { if (fr.tplId === t.id) { fr.tplId = ''; fr.tplName = ''; } haptic('success'); frTplSheet(); })
          .catch(err => showError(err.message)));
      });
      b.appendChild(del);
    }
    b.addEventListener('click', () => frChoose(id));
    box.appendChild(b);
    frThumb(thumb, id === 'new' ? frBlank() : t.doc);
  });
  if (fr.templates === null) {
    const s = document.createElement('p');
    s.className = 'hint'; s.textContent = 'Carico i modelli salvati…';
    box.appendChild(s);
  }
}

function frThumb(canvas, doc) {
  const keep = {doc:fr.doc, images:fr.images, cache:fr.cache, sel:fr.sel};
  fr.doc = frClone(doc); fr.images = {}; fr.cache = {}; fr.sel = '';
  const w = 72, h = Math.round(w * doc.h / doc.w);
  canvas.width = w * 2; canvas.height = h * 2;
  canvas.style.width = `${w}px`; canvas.style.height = `${h}px`;
  try { frRender(canvas, canvas.width / doc.w, false); } catch (_) {}
  Object.assign(fr, keep);
  // i font arrivano dopo: ridisegna l'anteprima del modello
  doc.layers.forEach(l => { if (l.type === 'text') frFont(l.font).then(ok => { if (ok && canvas.isConnected) frThumbLater(canvas, doc); }); });
}
function frThumbLater(canvas, doc) { clearTimeout(canvas._t); canvas._t = setTimeout(() => frThumb(canvas, doc), 60); }

function frOpenEditor() {
  if (!fr.doc) {                                     // i modelli si scelgono da dentro (Modelli)
    frOpenDoc(frBlank()); fr.choice = 'new';
    frPick('new');                                    // per prima cosa la foto (annulli = pagina vuota)
  }
  if (fr.templates === null && directBase && session) frTemplatesCall({action:'list'}).catch(() => { fr.templates = []; });
  frLayers(); frPanel(); frDraw();
}

/* ---------- passi, anteprima, invio ---------- */
function frValidate(step) {
  if (step === 'fredit') {
    const empty = fr.doc && fr.doc.layers.find(l => l.type === 'photo' && !l.hidden && !fr.images[l.id]);
    if (empty) { frSelect(empty.id); showError('Inserisci la foto (o elimina il livello vuoto).'); return false; }
    if (!fr.doc || !fr.doc.layers.length) { showError('Aggiungi almeno un livello.'); return false; }
    if (fr.doc.layers.some(l => fr.cutBusy[l.id])) { showError('Aspetta: sto ancora togliendo lo sfondo.'); return false; }
    if (fr.erasing) { showError('Aspetta: sto ancora cancellando.'); return false; }
  }
  return true;
}

function frStepValue(step) {
  if (step === 'fredit') return fr.doc ? `${fr.doc.layers.length} livelli` : '';
  return null;
}

// Disegna la pagina a piena risoluzione e la carica (una volta sola se non cambia nulla).
async function frExport() {
  if (!frValidate('fredit')) throw new Error($('error').textContent || 'Pagina non pronta.');
  await Promise.all([...new Set(fr.doc.layers.filter(l => l.type === 'text').map(l => l.font))].map(frFont));
  if (fr.doc.layers.some(l => l.type === 'logo')) await frLogo();
  const key = JSON.stringify(fr.doc) + Object.keys(fr.images).map(k => `${k}:${fr.images[k].width}:${fr.cuts[k] ? 1 : 0}`).join(',');
  if (key === fr.exportKey && fr.exportId) return;
  const c = document.createElement('canvas');
  c.width = fr.doc.w; c.height = fr.doc.h;
  frRender(c, 1, false);
  const blob = await new Promise(resolve => c.toBlob(resolve, 'image/jpeg', 0.95));
  if (!blob) throw new Error('Immagine non creata.');
  const r = await netFetch(`${directBase}/upload`, {method:'POST', headers:{'Content-Type':'image/jpeg', 'X-ImageGEN-Session':session}, body:blob}, 60000);
  const a = await r.json().catch(() => ({}));
  if (!r.ok || !a.ok) throw new Error(a.error || 'Caricamento non riuscito.');
  fr.exportKey = key; fr.exportId = a.photo_id;
}

function frPayload() {
  if (!fr.exportId) throw new Error('Apri l’anteprima.');
  return {v:1, action:'render', session, data:{kind:'free', photo_id:fr.exportId, title:fr.tplName || '',
    caption:String(fr.doc.caption || '').trim()}};
}

function frReset() {
  Object.assign(fr, {doc:null, sel:'', tool:'', dragging:'', tplId:'', tplName:'', images:{}, cuts:{}, cutBusy:{}, undo:{}, brush:null, erasing:false, cache:{}, exportKey:'', exportId:'', choice:''});
  if ($('frSheet') && !$('frSheet').hidden) frSheetClose();
}

function initFreeEditor() {
  initFreeCanvas();
  $('frFile').addEventListener('change', e => frPhotoPicked(e.target.files && e.target.files[0]));
  document.body.appendChild($('frSheet'));          // sopra a tutto, anche alla barra in basso
  $('frSheet').addEventListener('click', e => { if (e.target === $('frSheet')) frSheetClose(); });
  $('frSheetClose').addEventListener('click', frSheetClose);
}

initFreeEditor();
