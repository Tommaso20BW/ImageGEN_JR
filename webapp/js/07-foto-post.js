/* Mini App ImageGen JR. File caricati in ordine da index.html: l'ordine conta. */
/* ---------- Starting XI: foto ---------- */
// La foto resta solo in memoria (qui e nel workflow) per questa sessione.
// x/y: spostamento del centro in frazione della pagina; zoom >= 1 = "riempi la pagina".
// Stessi calcoli di graphics/starting_xi.py (photo_box), così l'anteprima coincide.
const DESIGN_W = 1080, DESIGN_H = 1440;
const OVERLAY_NAMES = {xi:'starting_xi', md:'matchday', jr:'jr'};
const photoState = {id:'', w:0, h:0, url:'', x:0, y:0, zoom:1, uploading:false};
// STORIE IG: foto facoltativa sotto il testo (nessun editor: il servizio la adatta da solo).
const igb = {id:'', url:'', uploading:false};
let igColor = 'black';     // colore del testo (tavolozza in 11-invii.js)
function igRefresh() {
  $('igThumb').hidden = !igb.url;
  $('igThumb').style.backgroundImage = igb.url ? `url("${igb.url}")` : '';
  $('igClear').hidden = !igb.id;
  $('igPick').textContent = igb.id ? 'Cambia foto' : 'Scegli foto';
  const n = $('igText').value.length;
  $('igCount').textContent = `${n} / 500`;
  $('igHint').textContent = igb.uploading ? 'Caricamento foto…' : '';
  renderSteps();
}
function igClearPhoto() {
  if (igb.url) { try { URL.revokeObjectURL(igb.url); } catch (_) {} }
  igb.id = ''; igb.url = ''; igb.uploading = false;
  igRefresh();
}
async function uploadIgPhoto(file) {
  if (!file) return;
  clearError();
  if (!directBase || !session) { showError('Sessione vecchia. Riavvia ImageGen dal workflow.'); return; }
  igb.uploading = true; igRefresh();
  try {
    const {blob} = await preparePhoto(file);
    const response = await netFetch(`${directBase}/upload`,{
      method:'POST', headers:{'Content-Type':'image/jpeg','X-ImageGEN-Session':session}, body:blob
    }, 60000);
    const body = await response.json().catch(() => ({}));
    if (!response.ok || !body.ok) throw new Error(body.error || 'Caricamento non riuscito.');
    if (igb.url) { try { URL.revokeObjectURL(igb.url); } catch (_) {} }
    igb.id = body.photo_id; igb.url = URL.createObjectURL(blob);
    haptic('success');
  } catch (err) {
    showError(err && err.message ? err.message : 'Caricamento non riuscito.');
  } finally {
    igb.uploading = false; igRefresh();
  }
}

function clearPhoto() {
  if (photoState.url) { try { URL.revokeObjectURL(photoState.url); } catch (_) {} }
  Object.assign(photoState,{id:'', w:0, h:0, url:'', x:0, y:0, zoom:1, uploading:false});
  $('photoImg').hidden = true;
  $('photoImg').removeAttribute('src');
  $('photoEmpty').hidden = false;
  $('photoSummary').textContent = '';
}

// Riquadro foto grande quanto lo spazio libero sotto il titolo: niente scorrimento,
// così trascinando la foto la pagina resta ferma.
// Pagina della foto: 1080x1440 (3:4); solo la Classica del Post può avere un altro formato.
function photoDims() {
  return kind === 'jr' && jrb.style === 'classic' ? ratioDims(jrb.ratio) : [DESIGN_W, DESIGN_H];
}

function fitPhotoFrame() {
  const frame = $('photoFrame'), stage = $('stage');
  if (!frame.offsetParent) return;
  const free = stage.getBoundingClientRect().bottom - frame.getBoundingClientRect().top - 34;
  const [pw, ph] = photoDims();
  frame.style.aspectRatio = `${pw} / ${ph}`;
  const width = Math.max(200, Math.min(frame.parentElement.clientWidth, free * pw / ph));
  frame.style.maxWidth = 'none';
  frame.style.width = `${Math.floor(width)}px`;
}

function layoutPhoto() {
  fitPhotoFrame();
  if (!photoState.w) return;
  const [PW, PH] = photoDims();
  const frameW = $('photoFrame').clientWidth || 1;
  const k = frameW / PW;
  const cover = Math.max(PW / photoState.w, PH / photoState.h);
  photoState.zoom = Math.min(4, Math.max(1, photoState.zoom));
  const w = photoState.w * cover * photoState.zoom, h = photoState.h * cover * photoState.zoom;
  let left = (PW - w) / 2 + photoState.x * PW;
  let top = (PH - h) / 2 + photoState.y * PH;
  left = Math.min(0, Math.max(PW - w, left));
  top = Math.min(0, Math.max(PH - h, top));
  photoState.x = (left - (PW - w) / 2) / PW;
  photoState.y = (top - (PH - h) / 2) / PH;
  const img = $('photoImg');
  img.style.left = `${left * k}px`; img.style.top = `${top * k}px`;
  img.style.width = `${w * k}px`; img.style.height = `${h * k}px`;
}

/* ---------- Sagome fisse ----------
   Sopra la foto, semitrasparente: la sagoma della grafica (immagine fissa del servizio,
   /overlay, una per grafica e maglia/competizione: tools/placeholders.py). Dietro la foto:
   lo sfondo della pagina (/pagebg). Si scaricano in anticipo e compaiono nello stesso momento. */
const editorImages = {};          // url -> Promise: true quando è scaricata e pronta
function fetchEditorImage(url) {
  if (!editorImages[url]) editorImages[url] = new Promise(resolve => {
    const im = new Image();
    im.onload = () => Promise.resolve(im.decode ? im.decode() : null).catch(() => {}).then(() => resolve(true));
    im.onerror = () => { delete editorImages[url]; resolve(false); };
    im.src = url;
  });
  return editorImages[url];
}

function editorImageUrls() {
  if (!directBase || !session || (kind !== 'md' && kind !== 'xi')) return null;
  const q = `session=${encodeURIComponent(session)}&kit=${encodeURIComponent(kit || 'home')}`
    + `&name=${kind === 'md' ? 'matchday' : 'starting_xi'}`;
  return {overlay:`${directBase}/overlay?${q}`, bg:`${directBase}/pagebg?${q}`};
}

// Appena si conosce la maglia (o la competizione) sagoma e sfondo partono in background.
function preloadEditorImages() {
  const urls = editorImageUrls();
  if (urls) { fetchEditorImage(urls.overlay); fetchEditorImage(urls.bg); }
  const phaseUrl = phaseOverlayUrl();
  if (phaseUrl) fetchEditorImage(phaseUrl);
}

let editorShown = '';
async function updatePhotoOverlay() {
  const overlay = $('photoOverlay'), frame = $('photoFrame');
  if (!directBase || !session) return;
  overlay.classList.add('ghost');
  // La sagoma è sempre 3:4, larga come la pagina e ancorata in alto: in un altro formato viene
  // tagliata (o lascia vuoto sotto) e il logo resta in alto a destra senza deformarsi.
  overlay.style.height = kind === 'jr' ? 'auto' : '';
  if (kind === 'jr') {
    editorShown = '';
    frame.style.backgroundImage = '';
    overlay.style.visibility = '';
    jrLogoSrc(overlay,'black');
    return;
  }
  if (isQuoteKind(kind)) { editorShown = ''; frame.style.backgroundImage = ''; iqGhost(overlay); return; }
  const urls = editorImageUrls();
  if (!urls || editorShown === urls.overlay) return;
  const key = editorShown = urls.overlay;
  // Niente sagoma o sfondo di un'altra maglia nel frattempo: compaiono solo insieme.
  overlay.style.visibility = 'hidden';
  frame.style.backgroundImage = '';
  await Promise.all([fetchEditorImage(urls.overlay), fetchEditorImage(urls.bg)]);
  if (editorShown !== key) return;
  overlay.src = urls.overlay;
  try { await overlay.decode(); } catch (_) {}
  if (editorShown !== key) return;
  frame.style.backgroundImage = `url("${urls.bg}")`;
  overlay.style.visibility = '';
}

// Riduce la foto a max 2560 px (lato lungo) in JPEG: qualità piena per la grafica,
// invio veloce dal telefono.
async function preparePhoto(file, keepAlpha=false) {
  let source;
  try { source = await createImageBitmap(file,{imageOrientation:'from-image'}); }
  catch (_) {
    source = await new Promise((resolve,reject) => {
      const im = new Image(); im.onload = () => resolve(im); im.onerror = reject;
      im.src = URL.createObjectURL(file);
    });
  }
  const sw = source.width, sh = source.height;
  const scale = Math.min(1, 2048 / Math.max(sw,sh));
  const canvas = document.createElement('canvas');
  canvas.width = Math.round(sw * scale); canvas.height = Math.round(sh * scale);
  const ctx = canvas.getContext('2d');
  ctx.drawImage(source,0,0,canvas.width,canvas.height);
  // Persona già scontornata (PNG trasparente): resta PNG, la trasparenza non si perde.
  let type = 'image/jpeg';
  if (keepAlpha) {
    const px = ctx.getImageData(0,0,canvas.width,canvas.height).data;
    for (let i = 3; i < px.length; i += 4) if (px[i] < 250) { type = 'image/png'; break; }
  }
  const blob = await new Promise(resolve => canvas.toBlob(resolve,type,0.88));
  if (!blob) throw new Error('Foto non leggibile.');
  return {blob, w:canvas.width, h:canvas.height, type};
}

async function uploadPhoto(file) {
  if (!file) return;
  clearError();
  if (!directBase || !session) { showError('Sessione vecchia. Riavvia ImageGen dal workflow.'); return; }
  photoState.uploading = true;
  $('photoSummary').textContent = 'Caricamento foto…';
  try {
    // Matchday / Starting XI: foto con sfondo trasparente, lo sfondo lo mette la grafica.
    const {blob,w,h,type} = await preparePhoto(file, kind === 'md' || kind === 'xi');
    const response = await netFetch(`${directBase}/upload`,{
      method:'POST', headers:{'Content-Type':type,'X-ImageGEN-Session':session}, body:blob
    }, 60000);
    const body = await response.json().catch(() => ({}));
    if (!response.ok || !body.ok) throw new Error(body.error || 'Caricamento non riuscito.');
    clearPhoto();
    Object.assign(photoState,{id:body.photo_id, w, h, url:URL.createObjectURL(blob)});
    $('photoImg').src = photoState.url;
    $('photoImg').hidden = false;
    $('photoEmpty').hidden = true;
    $('photoSummary').textContent = '';
    layoutPhoto();
    haptic('success');
    updatePhotoOverlay();
  } catch (err) {
    photoState.uploading = false;
    $('photoSummary').textContent = '';
    showError(err && err.message ? err.message : 'Caricamento non riuscito.');
  } finally {
    photoState.uploading = false;
    renderSteps();
  }
}

/* ---------- Aggancio al centro (come Canva) ----------
   Trascinando, quando il centro della foto arriva a meno di 8 px (sullo schermo)
   dal centro della pagina si ferma esattamente lì: linea rosa e piccola vibrazione.
   Continuando a trascinare si sgancia. o._rx/_ry = posizione "vera" del dito. */
const SNAP_PX = 8;
function snapMove(o, dx, dy, thrX, thrY, cx=0, cy=0) {
  if (o._rx === undefined) { o._rx = o.x; o._ry = o.y; }
  o._rx += dx; o._ry += dy;
  const sx = Math.abs(o._rx - cx) < thrX, sy = Math.abs(o._ry - cy) < thrY;
  o.x = sx ? cx : o._rx;
  o.y = sy ? cy : o._ry;
  return [sx, sy];
}
// Dopo i limiti della foto (che deve coprire la pagina): il dito riparte da lì.
function snapSync(o, [sx, sy]) { if (!sx) o._rx = o.x; if (!sy) o._ry = o.y; }
function snapEnd(o) { if (o) { delete o._rx; delete o._ry; } }
function snapShow(frame, [sx, sy]) {
  if ((sx && !frame.classList.contains('snap-x')) || (sy && !frame.classList.contains('snap-y'))) haptic('select');
  frame.classList.toggle('snap-x', sx);
  frame.classList.toggle('snap-y', sy);
}
function snapClear(frame) { frame.classList.remove('snap-x','snap-y'); }

function initPhotoEditor() {
  const frame = $('photoFrame');
  const pointers = new Map();
  let last = null;
  const snapshot = () => {
    const pts = [...pointers.values()];
    if (pts.length === 1) return {x:pts[0].x, y:pts[0].y, d:0};
    const [a,b] = pts;
    return {x:(a.x + b.x) / 2, y:(a.y + b.y) / 2, d:Math.hypot(a.x - b.x, a.y - b.y)};
  };
  frame.addEventListener('pointerdown',e => {
    if (!photoState.id) { $('photoFile').click(); return; }
    frame.setPointerCapture(e.pointerId);
    pointers.set(e.pointerId,{x:e.clientX, y:e.clientY});
    last = snapshot();
    frame.classList.add('dragging');
  });
  frame.addEventListener('pointermove',e => {
    if (!pointers.has(e.pointerId) || !last) return;
    pointers.set(e.pointerId,{x:e.clientX, y:e.clientY});
    const now = snapshot();
    const fw = frame.clientWidth, fh = frame.clientHeight;
    const snap = snapMove(photoState, (now.x - last.x) / fw, (now.y - last.y) / fh, SNAP_PX / fw, SNAP_PX / fh);
    if (now.d && last.d) photoState.zoom *= now.d / last.d;
    last = now;
    layoutPhoto();
    snapSync(photoState, snap);
    snapShow(frame, snap);
  });
  const end = e => {
    pointers.delete(e.pointerId);
    last = pointers.size ? snapshot() : null;
    if (!pointers.size) { frame.classList.remove('dragging'); snapEnd(photoState); snapClear(frame); }
  };
  frame.addEventListener('pointerup',end);
  frame.addEventListener('pointercancel',end);
  frame.addEventListener('wheel',e => {
    if (!photoState.id) return;
    e.preventDefault();
    photoState.zoom *= Math.exp(-e.deltaY * 0.0015);
    layoutPhoto();
  },{passive:false});
  $('photoPick').addEventListener('click',() => $('photoFile').click());
  $('xiText').addEventListener('input',() => { clearError(); readXiText(); });
  $('pxiText').addEventListener('input',() => {
    clearError(); readPxiText();
    document.querySelectorAll('.src-row .btn').forEach(b => b.classList.remove('on'));
  });
  document.querySelectorAll('.src-row .btn').forEach(b => b.addEventListener('click',() => loadPxiSource(b)));
  $('photoFile').addEventListener('change',e => { uploadPhoto(e.target.files && e.target.files[0]); e.target.value = ''; });
  window.addEventListener('resize',layoutPhoto);
  // iOS: il dito sulla foto non deve far scorrere la pagina né chiudere la Mini App.
  frame.addEventListener('touchmove',e => e.preventDefault(),{passive:false});
}


/* ---------- FOTO + JR Sfocata (pagina 26 Canva) ---------- */
// Stesse misure di graphics/photo_jr.py: sfondo sfocato 28 px (pagina 1080) e
// ingrandito del 6%, foto nitide con ombra; il riquadro è la pagina in piccolo.
const JRB_BLUR = 36, JRB_ZOOM = 1.1, JRB_W = [.12, 1.4], JRB_FILTER = k => `blur(${JRB_BLUR * k}px) brightness(.78) saturate(1.12)`;

// Miniatura leggera (per anteprima e miniature del collage): le foto vere restano da 2048 px.
async function jrSmall(blob, side = 360) {
  try {
    const bmp = await createImageBitmap(blob);
    const k = Math.min(1, side / Math.max(bmp.width, bmp.height));
    const cv = document.createElement('canvas');
    cv.width = Math.max(1, Math.round(bmp.width * k)); cv.height = Math.max(1, Math.round(bmp.height * k));
    cv.getContext('2d').drawImage(bmp, 0, 0, cv.width, cv.height);
    if (bmp.close) bmp.close();
    const small = await new Promise(resolve => cv.toBlob(resolve, 'image/jpeg', .8));
    return small ? URL.createObjectURL(small) : '';
  } catch (_) { return ''; }
}

function jrRelease() {
  jrb.cards.forEach(c => { try { URL.revokeObjectURL(c.url); if (c.small) URL.revokeObjectURL(c.small); } catch (_) {} });
}

// Un solo selettore: la nuova scelta sostituisce la precedente. Nessuna anteprima.
async function addJrPhotos(files) {
  clearError();
  if (!directBase || !session) { showError('Sessione vecchia. Riavvia ImageGen dal workflow.'); return; }
  const all = [...files];
  if (!all.length) return;
  const limit = jrLimit();
  const list = all.slice(0, limit);
  if (all.length > limit) showError(`Massimo ${limit} foto: ho preso le prime ${limit}.`);
  jrRelease();
  jrb.cards = []; jrb.bg = ''; jrb.sel = -1; jrb.order = null; jrb.tpls = null; jrb.tpl = 0; jrb.swap = -1; jrb.csel = -1;
  jrb.uploading = list.length;
  renderJrPicker();
  const done = new Array(list.length).fill(null);
  let next = 0;
  const worker = async () => {
    while (next < list.length) {
      const i = next++;
      try {
        const {blob,w,h} = await preparePhoto(list[i]);
        const response = await netFetch(`${directBase}/upload`,{
          method:'POST', headers:{'Content-Type':'image/jpeg','X-ImageGEN-Session':session}, body:blob
        }, 60000);
        const body = await response.json().catch(() => ({}));
        if (!response.ok || !body.ok) throw new Error(body.error || 'Caricamento non riuscito.');
        done[i] = {id:body.photo_id, w0:w, h0:h, url:URL.createObjectURL(blob), small:await jrSmall(blob), x:.5, y:.5, w:0, base:0, placed:false};
      } catch (err) {
        showError(err && err.message ? err.message : 'Caricamento non riuscito.');
      } finally {
        jrb.uploading--;
        renderJrPicker();
      }
    }
  };
  await Promise.all([worker(), worker(), worker()]);
  const seen = new Set();
  jrb.cards = done.filter(c => c && !seen.has(c.id) && seen.add(c.id));     // stesso ordine di scelta, senza doppioni
  if (jrb.cards.length) haptic('success');
  jrb.bg = jrb.cards.length === 1 ? jrb.cards[0].id : '';
  buildFlow();
  renderJrPicker();
  renderSteps();
}

function renderJrPicker() {
  const style = jrb.style;
  $('jrPhotosLead').textContent = style === 'collage'
    ? `Scegli da ${jrMin()} a ${jrLimit()} foto in una volta sola. Il layout lo scegli dopo.`
    : `Scegli da 1 a ${jrLimit()} foto in una volta sola.`;
  const n = jrb.cards.length;
  $('jrPick').disabled = jrb.uploading > 0;
  $('jrPick').textContent = jrb.uploading ? 'Caricamento…' : n ? 'Cambia le foto' : 'Scegli le foto';
  $('jrPhotosHint').textContent = jrb.uploading ? `${jrb.uploading} ancora da caricare…`
    : n ? `${n} foto pronte` : '';
}

function renderJrBg() {
  const box = $('jrBgTiles');
  box.innerHTML = '';
  jrb.cards.forEach((c,i) => {
    const tile = document.createElement('button');
    tile.type = 'button';
    tile.className = 'jr-tile' + (c.id === jrb.bg ? ' selected' : '');
    tile.setAttribute('role','radio');
    tile.setAttribute('aria-checked',c.id === jrb.bg ? 'true' : 'false');
    tile.innerHTML = `<img alt="Foto ${i + 1}"><span class="n">${i + 1}</span>`;
    tile.querySelector('img').src = c.url;
    tile.addEventListener('click',() => { haptic('select'); jrb.bg = c.id; renderJrBg(); renderSteps(); });
    box.appendChild(tile);
  });
}

// Disposizione automatica: 1 foto grande al centro; da 2 a 4 sfalsate e sovrapposte in parte.
// box = ingombro massimo di una foto in pixel pagina; la foto ci sta dentro con le sue proporzioni.
function jrbAutoLayout() {
  if (jrb.cards.every(c => c.placed)) return;
  const n = Math.min(4, jrb.cards.length);
  const L = [null,
    {box:[940,1200], at:[[.5,.5]]},
    {box:[660,820],  at:[[.36,.35],[.64,.65]]},
    {box:[540,600],  at:[[.3,.25],[.7,.5],[.3,.75]]},
    {box:[480,520],  at:[[.28,.24],[.72,.34],[.28,.64],[.72,.76]]}][n];
  jrb.cards.forEach((c,i) => {
    const [x,y] = L.at[Math.min(i, L.at.length - 1)];
    const w = Math.min(L.box[0], L.box[1] * c.w0 / c.h0) / 1080;
    Object.assign(c,{x, y, w, base:w, placed:true});
  });
  jrb.sel = -1;
}

// Riquadro grande quanto lo spazio libero (come l'editor foto): calcolato solo
// all'apertura e quando cambia la finestra, non a ogni tocco.
function fitJrbFrame() {
  const frame = $('jrbFrame');
  if (!frame.offsetParent) return;
  const free = $('stage').getBoundingClientRect().bottom - frame.getBoundingClientRect().top - 90;
  frame.style.maxWidth = 'none';
  frame.style.width = `${Math.floor(Math.max(200, Math.min(frame.parentElement.clientWidth, free * .75)))}px`;
}

function renderJrb() {
  const frame = $('jrbFrame');
  if (!frame.offsetParent) return;
  const k = frame.clientWidth / 1080;
  frame.style.setProperty('--k', k);
  const bg = jrb.cards.find(c => c.id === jrb.bg) || jrb.cards[0];
  const img = $('jrbBg');
  if (bg) {
    const cover = Math.max(1080 / bg.w0, 1440 / bg.h0) * JRB_ZOOM;
    const bw = bg.w0 * cover, bh = bg.h0 * cover;
    if (img.getAttribute('src') !== bg.url) img.src = bg.url;
    Object.assign(img.style,{left:`${(1080 - bw) / 2 * k}px`, top:`${(1440 - bh) / 2 * k}px`,
      width:`${bw * k}px`, height:`${bh * k}px`, filter:JRB_FILTER(k)});
  }
  const box = $('jrbCards');
  if (box.children.length !== jrb.cards.length || [...box.children].some((el,i) => el.dataset.id !== jrb.cards[i].id)) {
    box.innerHTML = '';
    jrb.cards.forEach(c => {
      const el = document.createElement('img');
      el.className = 'card';
      el.alt = '';
      el.draggable = false;
      el.dataset.id = c.id;
      el.src = c.url;
      box.appendChild(el);
    });
  }
  [...box.children].forEach((el,i) => {
    const c = jrb.cards[i];
    const w = c.w * 1080, h = w * c.h0 / c.w0;
    Object.assign(el.style,{left:`${(c.x * 1080 - w / 2) * k}px`, top:`${(c.y * 1440 - h / 2) * k}px`,
      width:`${w * k}px`, height:`${h * k}px`});
    el.classList.toggle('sel', i === jrb.sel);
  });
  jrLogoSrc($('jrbOverlay'),'white');
  const sel = jrb.cards[jrb.sel];
  $('jrbScale').textContent = sel ? `${Math.round(sel.w / sel.base * 100)}%` : '—';
  $('jrbMinus').disabled = !sel || sel.w <= JRB_W[0] + 1e-6;
  $('jrbPlus').disabled = !sel || sel.w >= JRB_W[1] - 1e-6;
  $('jrbHint').textContent = sel
    ? 'Trascina per spostarla; due dita o − + per la grandezza.'
    : 'Tocca una foto: trascinala per spostarla, due dita o − + per la grandezza.';
}

function jrbScale(factor) {
  const c = jrb.cards[jrb.sel];
  if (!c) return;
  c.w = Math.min(JRB_W[1], Math.max(JRB_W[0], c.w * factor));
  renderJrb();
}

function initJrBlur() {
  $('jrPick').addEventListener('click',() => { if (!jrb.uploading) $('jrFiles').click(); });
  $('jrFiles').addEventListener('change',e => { addJrPhotos(e.target.files || []); e.target.value = ''; });
  $('jrbMinus').addEventListener('click',() => { haptic('select'); jrbScale(1 / 1.05); });
  $('jrbPlus').addEventListener('click',() => { haptic('select'); jrbScale(1.05); });
  const frame = $('jrbFrame');
  const pointers = new Map();
  let last = null;
  const snap = () => {
    const pts = [...pointers.values()];
    if (pts.length === 1) return {x:pts[0].x, y:pts[0].y, d:0};
    const [a,b] = pts;
    return {x:(a.x + b.x) / 2, y:(a.y + b.y) / 2, d:Math.hypot(a.x - b.x, a.y - b.y)};
  };
  frame.addEventListener('pointerdown',e => {
    const el = e.target.closest('.card');
    if (!pointers.size) {
      if (el) {
        // La foto toccata va in primo piano e diventa quella selezionata.
        const i = jrb.cards.findIndex(c => c.id === el.dataset.id);
        if (i >= 0) { const [c] = jrb.cards.splice(i,1); jrb.cards.push(c); jrb.sel = jrb.cards.length - 1; haptic('select'); }
      } else if (jrb.sel >= 0) {
        jrb.sel = -1;
      }
      renderJrb();
    }
    if (jrb.sel < 0) return;
    frame.setPointerCapture(e.pointerId);
    pointers.set(e.pointerId,{x:e.clientX, y:e.clientY});
    last = snap();
  });
  frame.addEventListener('pointermove',e => {
    if (!pointers.has(e.pointerId) || !last) return;
    pointers.set(e.pointerId,{x:e.clientX, y:e.clientY});
    const now = snap();
    const c = jrb.cards[jrb.sel];
    if (c) {
      const fw = frame.clientWidth, fh = frame.clientHeight;
      const hit = snapMove(c, (now.x - last.x) / fw, (now.y - last.y) / fh, SNAP_PX / fw, SNAP_PX / fh, .5, .5);
      c.x = Math.min(1.5, Math.max(-.5, c.x));
      c.y = Math.min(1.5, Math.max(-.5, c.y));
      if (now.d && last.d) c.w = Math.min(JRB_W[1], Math.max(JRB_W[0], c.w * now.d / last.d));
      snapSync(c, hit);
      snapShow(frame, hit);
    }
    last = now;
    renderJrb();
  });
  const end = e => {
    pointers.delete(e.pointerId);
    last = pointers.size ? snap() : null;
    if (!pointers.size) { jrb.cards.forEach(snapEnd); snapClear(frame); }
  };
  frame.addEventListener('pointerup',end);
  frame.addEventListener('pointercancel',end);
  frame.addEventListener('wheel',e => {
    if (jrb.sel < 0) return;
    e.preventDefault();
    jrbScale(Math.exp(-e.deltaY * 0.0015));
  },{passive:false});
  frame.addEventListener('touchmove',e => e.preventDefault(),{passive:false});
  window.addEventListener('resize',() => { if ($('jrbFrame').offsetParent) { fitJrbFrame(); renderJrb(); } });
}


/* ---------- FOTO + JR: colore del logo (pronti, esadecimale, sfumature) ----------
   Nero, bianco e oro sono i PNG Canva del servizio. Tutto il resto ricolora la stessa sagoma:
   il servizio con una maschera (graphics/photo_jr.py), qui nell'anteprima con un canvas. */
const JRC_SOLID = (id,label,hex) => ({id, label, spec:{type:'solid', hex}});
const JRC_GOLD = {type:'gradient', angle:135, stops:[{c:'#f9e79a',p:0},{c:'#d7a92f',p:50},{c:'#9a7016',p:100}]};
const JRC_PRESETS = [
  {id:'black', label:'Nero', raster:true, css:'#111113', seed:{type:'solid', hex:'#111113'}},
  {id:'white', label:'Bianco', raster:true, css:'#ffffff', seed:{type:'solid', hex:'#ffffff'}},
  {id:'gold', label:'Oro', raster:true, seed:JRC_GOLD},
  {id:'silver', label:'Argento', spec:{type:'gradient', angle:135, stops:[{c:'#f4f6f8',p:0},{c:'#a9b0b9',p:35},{c:'#ffffff',p:55},{c:'#7f8791',p:100}]}},
  {id:'bronze', label:'Bronzo', spec:{type:'gradient', angle:135, stops:[{c:'#f0c49a',p:0},{c:'#c97b30',p:38},{c:'#e9a468',p:58},{c:'#7e4219',p:100}]}},
  JRC_SOLID('red','Rosso','#e11d2e'), JRC_SOLID('orange','Arancio','#ff7a00'), JRC_SOLID('yellow','Giallo','#ffd60a'),
  JRC_SOLID('green','Verde','#16c172'), JRC_SOLID('teal','Turchese','#00c2c7'), JRC_SOLID('sky','Azzurro','#2aa8ff'),
  JRC_SOLID('blue','Blu','#2457ff'), JRC_SOLID('violet','Viola','#8b3dff'), JRC_SOLID('pink','Rosa','#ff3d9a')
];
const jrc = {mode:'solid', c:['#ff3366','#ffcc33'], a:135, sel:0, h:345, t:.5, key:'', token:0};

const jrcClamp = (v,a=0,b=1) => Math.min(b, Math.max(a, v));
// "#abc", "abc", "AABBCC" -> "#aabbcc"; altrimenti ''
function jrcHexNorm(raw) {
  let v = String(raw || '').trim().replace(/^#/,'').toLowerCase();
  if (/^[0-9a-f]{3}$/.test(v)) v = v.split('').map(c => c + c).join('');
  return /^[0-9a-f]{6}$/.test(v) ? `#${v}` : '';
}
const jrcRgb = hex => [1,3,5].map(i => parseInt(hex.slice(i,i + 2),16));
const jrcToHex = rgb => '#' + rgb.map(v => Math.round(jrcClamp(v,0,255)).toString(16).padStart(2,'0')).join('');
function jrcHsvToRgb(h,s,v) {
  const f = n => { const k = (n + h / 60) % 6; return v - v * s * Math.max(0, Math.min(k, 4 - k, 1)); };
  return [f(5) * 255, f(3) * 255, f(1) * 255];
}
function jrcRgbToHsv(r,g,b) {
  r /= 255; g /= 255; b /= 255;
  const mx = Math.max(r,g,b), d = mx - Math.min(r,g,b);
  let h = 0;
  if (d) h = mx === r ? ((g - b) / d + 6) % 6 : mx === g ? (b - r) / d + 2 : (r - g) / d + 4;
  return [h * 60, mx ? d / mx : 0, mx];
}
const jrcSorted = stops => stops.map(s => ({c:s.c, p:s.p})).sort((a,b) => a.p - b.p);
function jrcCss(spec, angle) {
  if (spec.type === 'solid') return spec.hex;
  const list = jrcSorted(spec.stops).map(s => `${s.c} ${s.p}%`).join(',');
  return `linear-gradient(${angle == null ? spec.angle : angle}deg,${list})`;
}
const jrcIsRaster = c => typeof c === 'string' && c !== '';
const jrcIsCustom = c => c && typeof c === 'object' && !c.id;
const jrcSpecOf = c => c && typeof c === 'object' ? {type:c.type, hex:c.hex, angle:c.angle, stops:c.stops} : null;

function jrColorLabel() {
  if (!jrColor) return '';
  if (jrcIsRaster(jrColor)) return labelOf(JR_COLORS,jrColor);
  if (jrColor.id) return (JRC_PRESETS.find(p => p.id === jrColor.id) || {label:jrColor.id}).label;
  return jrColor.type === 'solid' ? jrColor.hex.toUpperCase() : 'Sfumatura';
}

/* --- logo ricolorato nell'anteprima --- */
const jrLogo = {raw:{}, box:null, full:new Map(), crop:new Map()};   // raw: sagome 540x720 (editor); raw['hi:'+nome]: originali a piena risoluzione (anteprime colore)
const jrOverlayUrl = (name, hires) => `${directBase}/overlay?session=${encodeURIComponent(session)}&name=jr&kit=${encodeURIComponent(name)}${hires ? '&hires=1' : ''}`;

function jrRaw(name, hires) {          // sagoma del servizio come ImageBitmap (una volta sola); hires = livello originale
  if (!directBase || !session) return Promise.resolve(null);
  const id = hires ? 'hi:' + name : name;
  if (!jrLogo.raw[id]) {
    jrLogo.raw[id] = (async () => {
      try {
        const response = await netFetch(jrOverlayUrl(name,hires),{},hires ? 40000 : 20000,2);
        if (!response.ok) throw new Error('overlay');
        return await createImageBitmap(await response.blob());
      } catch (_) { delete jrLogo.raw[id]; return null; }
    })();
  }
  return jrLogo.raw[id];
}

function jrAlphaBox(bmp) {             // rettangolo che contiene il logo
  const cv = document.createElement('canvas');
  cv.width = bmp.width; cv.height = bmp.height;
  const cx = cv.getContext('2d',{willReadFrequently:true});
  cx.drawImage(bmp,0,0);
  const d = cx.getImageData(0,0,cv.width,cv.height).data;
  let x0 = cv.width, y0 = cv.height, x1 = -1, y1 = -1;
  for (let y = 0; y < cv.height; y++) for (let x = 0; x < cv.width; x++) {
    if (d[(y * cv.width + x) * 4 + 3] > 8) { if (x < x0) x0 = x; if (x > x1) x1 = x; if (y < y0) y0 = y; if (y > y1) y1 = y; }
  }
  return x1 < 0 ? {x:0, y:0, w:cv.width, h:cv.height} : {x:x0, y:y0, w:x1 - x0 + 1, h:y1 - y0 + 1};
}

// Come il linear-gradient CSS: l'angolo 0 va verso l'alto, 90 verso destra.
function jrGradLine(angle, x, y, w, h) {
  const a = angle * Math.PI / 180, sx = Math.sin(a), sy = -Math.cos(a);
  const len = Math.abs(w * sx) + Math.abs(h * sy), cx = x + w / 2, cy = y + h / 2;
  return [cx - sx * len / 2, cy - sy * len / 2, cx + sx * len / 2, cy + sy * len / 2];
}

// PNG (blob URL) del logo nel colore scelto. crop: solo il logo (per le anteprime); altrimenti tutta la pagina.
async function jrLogoUrl(color, crop) {
  const cache = crop ? jrLogo.crop : jrLogo.full;
  const key = JSON.stringify(jrcIsRaster(color) ? color : jrcSpecOf(color));
  if (cache.has(key)) return cache.get(key);
  const black = await jrRaw('black',crop);
  const src = jrcIsRaster(color) ? await jrRaw(color,crop) : black;
  if (!black || !src) return '';
  const bk = crop ? 'crop' : 'full';          // il riquadro dipende dalla risoluzione della sagoma
  const box = jrLogo[bk + 'Box'] || (jrLogo[bk + 'Box'] = jrAlphaBox(black));
  const pad = crop ? 12 : 0, sc = 1;          // anteprima: sagoma originale, nessun ingrandimento
  const x0 = crop ? Math.max(0, box.x - pad) : 0, y0 = crop ? Math.max(0, box.y - pad) : 0;
  const x1 = crop ? Math.min(src.width, box.x + box.w + pad) : src.width, y1 = crop ? Math.min(src.height, box.y + box.h + pad) : src.height;
  const cv = document.createElement('canvas');
  cv.width = Math.round((x1 - x0) * sc); cv.height = Math.round((y1 - y0) * sc);
  const cx = cv.getContext('2d');
  cx.scale(sc,sc);
  cx.drawImage(src,-x0,-y0);
  if (!jrcIsRaster(color)) {
    cx.globalCompositeOperation = 'source-in';
    if (color.type === 'solid') cx.fillStyle = color.hex;
    else {
      const [ax,ay,bx,by] = jrGradLine(color.angle, box.x - x0, box.y - y0, box.w, box.h);
      const g = cx.createLinearGradient(ax,ay,bx,by);
      jrcSorted(color.stops).forEach(s => g.addColorStop(s.p / 100, s.c));
      cx.fillStyle = g;
    }
    cx.fillRect(0,0,x1 - x0,y1 - y0);
  }
  const blob = await new Promise(resolve => cv.toBlob(resolve,'image/png'));
  if (!blob) return '';
  const url = URL.createObjectURL(blob);
  cache.set(key,url);
  while (cache.size > (crop ? 24 : 10)) {        // le più vecchie si buttano
    const [oldKey,oldUrl] = cache.entries().next().value;
    cache.delete(oldKey);
    try { URL.revokeObjectURL(oldUrl); } catch (_) {}
  }
  return url;
}

// Mette sul <img> il logo nel colore scelto (anteprime dell'editor).
function jrLogoSrc(img, fallback = 'white') {
  if (!img || !directBase || !session) return;
  const color = jrColor || fallback;
  if (jrcIsRaster(color)) {
    img.dataset.jrk = '';
    const url = jrOverlayUrl(color);
    if (img.getAttribute('src') !== url) img.src = url;
    return;
  }
  const key = JSON.stringify(jrcSpecOf(color));
  img.dataset.jrk = key;
  jrLogoUrl(color,false).then(url => { if (url && img.dataset.jrk === key) img.src = url; });
}

/* --- schermata colore: elenco con la spunta + popup "Personalizzato" (cursori Colore e Luce) --- */
const jrcHsvHex = (h,sat,v) => jrcToHex(jrcHsvToRgb(h,sat,v));
const jrcLumHex = (h,t) => t < .5 ? jrcHsvHex(h,1,t * 2) : jrcHsvHex(h,(1 - t) * 2,1);   // Luce: nero -> colore -> bianco
function jrcFromHex(hex) {
  const [h,sat,v] = jrcRgbToHsv(...jrcRgb(hex));
  if (sat && v) jrc.h = h;
  jrc.t = v < .999 ? v / 2 : .5 + (1 - sat) / 2;
}
const jrcSpec = () => jrc.mode === 'solid' ? {type:'solid', hex:jrc.c[0]}
  : {type:'gradient', angle:jrc.a, stops:[{c:jrc.c[0],p:0},{c:jrc.c[1],p:100}]};

let jrcRaf = 0;
function jrcChanged() {                  // un ritocco al colore personalizzato: applica e ridisegna
  jrColor = jrcSpec();
  jrcPaint(); jrcRenderCar();
  if (!jrcRaf) jrcRaf = requestAnimationFrame(() => { jrcRaf = 0; jrcPreview(); renderSteps(); });
}

function jrcPaint() {                    // aggiorna il popup Personalizzato
  const cur = jrc.c[jrc.sel], grad = jrc.mode === 'gradient';
  $('jrcHue').firstElementChild.style.cssText = `left:${jrc.h / 360 * 100}%;background:hsl(${jrc.h},100%,50%)`;
  $('jrcLum').style.background = `linear-gradient(90deg,#000,hsl(${jrc.h},100%,50%),#fff)`;
  $('jrcLum').firstElementChild.style.cssText = `left:${jrc.t * 100}%;background:${cur}`;
  if (document.activeElement !== $('jrcHex')) { $('jrcHex').value = cur.slice(1).toUpperCase(); $('jrcHexBox').classList.remove('bad'); }
  $('jrcSolid').classList.toggle('on',!grad); $('jrcGradBtn').classList.toggle('on',grad);
  $('jrcEnds').hidden = !grad;
  document.querySelectorAll('.jrc-end').forEach(b => {
    const i = Number(b.dataset.e);
    b.classList.toggle('on',i === jrc.sel);
    b.querySelector('i').style.background = jrc.c[i];
  });
}

async function jrcPreview() {
  const tiles = [...document.querySelectorAll('.jrc-tile')];
  const mine = ++jrc.token;
  let url = '';
  if (jrColor) { try { url = await jrLogoUrl(jrColor,true); } catch (_) { url = ''; } }
  if (mine !== jrc.token) return;
  tiles.forEach(tile => {
    let img = tile.querySelector('img');
    if (!url) { if (img) img.remove(); return; }
    if (!img) { img = document.createElement('img'); img.alt = ''; tile.prepend(img); }
    img.src = url;
  });
}

const jrcCur = () => jrcIsRaster(jrColor) ? jrColor : jrColor && jrColor.id || '';
const JRC_CLASSIC = 5;                   // Nero, Bianco, Oro, Argento, Bronzo; poi i colori

function jrcRenderCar() {
  const cur = jrcCur(), custom = jrcIsCustom(jrColor);
  const lists = [$('jrcListA'), $('jrcListB')];
  if (lists[0].dataset.built !== '1') {
    lists[0].dataset.built = '1';
    lists.forEach(l => { l.innerHTML = ''; });
    JRC_PRESETS.forEach((p,i) => {
      const b = document.createElement('button');
      b.type = 'button'; b.className = 'ios-row jrc-it'; b.dataset.id = p.id;
      b.setAttribute('role','radio');
      b.innerHTML = '<i class="jrc-dot"></i><span></span>';
      b.firstChild.style.background = p.css || jrcCss(p.spec || p.seed,135);
      b.lastChild.textContent = p.label;
      b.addEventListener('click',() => jrcPick(p));
      lists[i < JRC_CLASSIC ? 0 : 1].appendChild(b);
    });
  }
  lists.forEach(l => [...l.children].forEach(b => {
    const on = b.dataset.id === cur;
    b.classList.toggle('on',on);
    b.setAttribute('aria-checked',on ? 'true' : 'false');
  }));
  $('jrcCu').classList.toggle('on',custom);
  $('jrcCuSw').classList.toggle('jrc-rainbow',!custom);
  $('jrcCuSw').style.background = custom ? jrcCss(jrColor,135) : '';
  $('jrcCuV').textContent = custom ? jrColorLabel() : '';
}

function jrcPick(p) {                    // un colore pronto
  if (jrcCur() === p.id && !jrcIsCustom(jrColor)) return;
  haptic('select');
  jrColor = p.raster ? p.id : {id:p.id, ...p.spec};
  renderJrColor(); renderSteps();
}

function renderJrColor() {
  jrcRenderCar();
  const key = JSON.stringify(jrColor || '');
  if (key !== jrc.key) { jrc.key = key; jrcPreview(); }
}

function jrcOpenSheet() {                // si parte dal colore in uso: lo si ritocca, non si riparte da zero
  haptic('select');
  const spec = jrcIsRaster(jrColor) ? (JRC_PRESETS.find(p => p.id === jrColor) || {}).seed : jrColor ? jrcSpecOf(jrColor) : null;
  if (spec) {
    if (spec.type === 'solid') { jrc.mode = 'solid'; jrc.c[0] = spec.hex; }
    else { const st = jrcSorted(spec.stops); jrc.mode = 'gradient'; jrc.a = spec.angle; jrc.c = [st[0].c, st[st.length - 1].c]; }
    jrc.sel = 0;
  }
  jrcFromHex(jrc.c[jrc.sel]);
  if (!jrColor) jrcChanged(); else jrcPaint();
  $('jrcOv').classList.add('open');
}
function jrcCloseSheet() { $('jrcOv').classList.remove('open'); }

function initJrColor() {
  $('jrcCu').addEventListener('click',jrcOpenSheet);
  $('jrcDone').addEventListener('click',jrcCloseSheet);
  $('jrcOv').addEventListener('click',e => { if (e.target.id === 'jrcOv') jrcCloseSheet(); });
  document.addEventListener('keydown',e => { if (e.key === 'Escape') jrcCloseSheet(); });

  // cursori Colore e Luce
  const drag = (el, fn) => {
    el.addEventListener('pointerdown',e => {
      e.preventDefault();
      el.setPointerCapture(e.pointerId);
      const r = el.getBoundingClientRect();
      const move = ev => fn(jrcClamp((ev.clientX - r.left) / r.width));
      move(e);
      const up = () => { el.removeEventListener('pointermove',move); el.removeEventListener('pointerup',up); el.removeEventListener('pointercancel',up); };
      el.addEventListener('pointermove',move); el.addEventListener('pointerup',up); el.addEventListener('pointercancel',up);
    });
  };
  const setColor = () => { jrc.c[jrc.sel] = jrcLumHex(jrc.h,jrc.t); jrcChanged(); };
  drag($('jrcHue'),x => { jrc.h = x * 359.999; setColor(); });
  drag($('jrcLum'),x => { jrc.t = x; setColor(); });

  const hexIn = $('jrcHex');
  hexIn.addEventListener('input',() => {
    const raw = hexIn.value.trim().replace(/^#/,'');
    if (/^[0-9a-fA-F]{6}$/.test(raw)) { $('jrcHexBox').classList.remove('bad'); jrc.c[jrc.sel] = jrcHexNorm(raw); jrcFromHex(jrc.c[jrc.sel]); jrcChanged(); }
    else $('jrcHexBox').classList.toggle('bad',raw.length > 0 && !/^[0-9a-fA-F]{0,6}$/.test(raw) || raw.length >= 6);
  });
  const hexDone = () => {
    const hex = jrcHexNorm(hexIn.value);
    if (hex) { jrc.c[jrc.sel] = hex; jrcFromHex(hex); jrcChanged(); }
    hexIn.value = jrc.c[jrc.sel].slice(1).toUpperCase();
    $('jrcHexBox').classList.remove('bad');
    jrcPaint();
  };
  hexIn.addEventListener('blur',hexDone);
  hexIn.addEventListener('keydown',e => { if (e.key === 'Enter') { e.preventDefault(); hexIn.blur(); } });
  hexIn.addEventListener('paste',() => setTimeout(() => hexIn.dispatchEvent(new Event('input')),0));

  $('jrcSolid').addEventListener('click',() => {
    if (jrc.mode === 'solid') return;
    haptic('select');
    jrc.mode = 'solid'; jrc.sel = 0; jrcFromHex(jrc.c[0]); jrcChanged();
  });
  $('jrcGradBtn').addEventListener('click',() => {
    if (jrc.mode === 'gradient') return;
    haptic('select');
    const [h,sat] = jrcRgbToHsv(...jrcRgb(jrc.c[0]));     // seconda tinta: stesso colore, tono spostato
    jrc.c[1] = jrcHsvHex((h + 40) % 360,jrcClamp(sat,.35,1),1);
    jrc.mode = 'gradient'; jrc.sel = 0; jrcFromHex(jrc.c[0]); jrcChanged();
  });
  document.querySelectorAll('.jrc-end').forEach(b => b.addEventListener('click',() => {
    jrc.sel = Number(b.dataset.e); jrcFromHex(jrc.c[jrc.sel]); jrcPaint();
  }));
  $('jrcRev').addEventListener('click',() => {
    haptic('select');
    jrc.c.reverse(); jrcFromHex(jrc.c[jrc.sel]); jrcChanged();
  });
}

/* ---------- FOTO + JR Collage: layout automatici a riquadri (stile Canva) ---------- */
// Pagina 1080x1440, fondo bianco, bordo 10 e linee di 5 px (come il collage di esempio):
// stesse misure di graphics/photo_jr.py. Il logo JR sta sopra la foto in alto a destra.
// I layout si ricavano da alberi di divisioni (colonne/righe) con un generatore a caso ma
// con seme fisso: ogni numero di foto dà sempre gli stessi layout. I peggiori (riquadri
// troppo stretti o troppo piccoli) si scartano, poi si ordinano dal più equilibrato.
const COL_W = 1080, COL_H = 1440, COL_M = 10, COL_G = 5, COL_MAX_TPL = 15;
function colRng(seed) {
  let a = seed >>> 0;
  return () => {
    a = (a + 0x6D2B79F5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

// nodo = {n, dir:'v'|'h', w:[pesi], kids:[nodi]} oppure {n:1}. 'v' = colonne affiancate, 'h' = righe.
function colTree(n, rng) {
  if (n === 1) return {n:1};
  const k = n >= 3 && rng() < .35 ? 3 : 2;
  const parts = Array(k).fill(1);
  for (let r = n - k; r > 0; r--) parts[Math.floor(rng() * k)]++;
  const w = parts.slice();
  if (rng() < .4) w[Math.floor(rng() * k)] *= 1.6;           // un riquadro "protagonista" più grande
  return {n, dir:rng() < .5 ? 'v' : 'h', w, kids:parts.map(q => colTree(q, rng))};
}

// Righe (o colonne) con lo stesso numero di foto, o quasi: griglie regolari.
function colRows(parts, dir) {
  return {n:parts.reduce((a,b) => a + b, 0), dir, w:parts.map(() => 1),
          kids:parts.map(q => q === 1 ? {n:1} : {n:q, dir:dir === 'h' ? 'v' : 'h', w:Array(q).fill(1), kids:Array.from({length:q},() => ({n:1}))})};
}

function colPlace(node, r, out) {
  if (!node.kids) { out.push(r); return; }
  const k = node.kids.length, horiz = node.dir === 'v';
  const total = (horiz ? r.w : r.h) - COL_G * (k - 1), sum = node.w.reduce((a,b) => a + b, 0);
  let pos = horiz ? r.x : r.y;
  node.kids.forEach((kid,i) => {
    const size = total * node.w[i] / sum;
    colPlace(kid, horiz ? {x:pos, y:r.y, w:size, h:r.h} : {x:r.x, y:pos, w:r.w, h:size}, out);
    pos += size + COL_G;
  });
}

function colScore(cells) {
  let pen = 0, amin = Infinity, amax = 0;
  for (const c of cells) {
    if (c.w < 190 || c.h < 190) return Infinity;
    pen += Math.max(0, Math.abs(Math.log(c.w / c.h / .9)) - .7) * 3;        // proporzioni estreme
    amin = Math.min(amin, c.w * c.h); amax = Math.max(amax, c.w * c.h);
  }
  if (amax / amin > 5) return Infinity;
  return pen + Math.log(amax / amin) * .4;
}

function colTemplates(n) {
  const rect = {x:COL_M, y:COL_M, w:COL_W - 2 * COL_M, h:COL_H - 2 * COL_M};     // bordo uguale su tutti i lati
  const trees = [];
  // griglie regolari: righe (e colonne) il più possibile uguali
  for (let rows = 2; rows <= Math.min(4, n); rows++) {
    const base = Math.floor(n / rows), extra = n % rows, parts = Array(rows).fill(base);
    for (let i = 0; i < extra; i++) parts[i]++;
    if (Math.max(...parts) > 4) continue;
    const variants = new Set([parts.join(','), [...parts].reverse().join(',')]);
    variants.forEach(v => { const q = v.split(',').map(Number); trees.push(colRows(q,'h'), colRows(q,'v')); });
  }
  if (n === 2) trees.push(colRows([1,1],'h'), colRows([1,1],'v'));
  const rng = colRng(1000 + n);
  for (let i = 0; i < 500; i++) trees.push(colTree(n, rng));
  const seen = new Set(), found = [];
  for (const t of trees) {
    const px = []; colPlace(t, rect, px);
    if (px.length !== n) continue;
    const sc = colScore(px);
    if (!isFinite(sc)) continue;
    const sig = px.map(c => [c.x,c.y,c.w,c.h].map(Math.round).join(':')).sort().join('|');
    if (seen.has(sig)) continue;
    seen.add(sig);
    found.push({sc, px});
  }
  found.sort((a,b) => a.sc - b.sc);
  return found.slice(0, COL_MAX_TPL).map((f,i) => ({
    id:i, px:f.px,
    cells:f.px.map(c => ({x:c.x / COL_W, y:c.y / COL_H, w:c.w / COL_W, h:c.h / COL_H}))
  }));
}

// Foto -> riquadro: ogni foto va dove si ritaglia meno (si guardano le proporzioni).
// A parità, resta l'ordine di scelta.
function colAssign(px, cards) {
  const n = px.length, INF = 1e9;
  const cost = px.map((c,i) => cards.map((p,j) => Math.abs(Math.log((c.w / c.h) / (p.w0 / p.h0))) + .03 * Math.abs(i - j)));
  const dp = new Array(1 << n).fill(INF), from = new Array(1 << n).fill(-1);
  dp[0] = 0;
  for (let mask = 0; mask < (1 << n); mask++) {
    if (dp[mask] >= INF) continue;
    let i = 0; for (let m = mask; m; m &= m - 1) i++;
    if (i >= n) continue;
    for (let j = 0; j < n; j++) {
      if (mask >> j & 1) continue;
      const nm = mask | (1 << j), v = dp[mask] + cost[i][j];
      if (v < dp[nm]) { dp[nm] = v; from[nm] = j; }
    }
  }
  const order = new Array(n);
  let mask = (1 << n) - 1;
  for (let i = n - 1; i >= 0; i--) { const j = from[mask]; order[i] = j; mask ^= 1 << j; }
  return order;                                    // order[riquadro] = indice della foto
}

function jrTemplates() {
  if (!jrb.tpls || jrb.tpls.n !== jrb.cards.length) {
    jrb.tpls = {n:jrb.cards.length, list:jrb.cards.length >= 2 ? colTemplates(jrb.cards.length) : []};
    jrb.tpl = 0; jrb.order = null; jrb.swap = -1; jrb.csel = -1;
  }
  return jrb.tpls.list;
}

function jrOrder() {
  const t = jrTemplates()[jrb.tpl];
  if (!t) return [];
  if (!jrb.order) jrb.order = colAssign(t.px, jrb.cards);
  return jrb.order;
}

// Ritaglio della foto nel riquadro: zoom (1 = riempie il riquadro) e posizione cpx/cpy (0 = allineata a
// sinistra/in alto, 1 = a destra/in basso). Sta sulla foto, quindi la segue se la si scambia o si cambia layout.
const COL_ZOOM = [1, 6], COL_DEF = [.5, .38];
function colCrop(card) {
  if (card.cz == null) { card.cpx = COL_DEF[0]; card.cpy = COL_DEF[1]; card.cz = 1; }
  return card;
}
// Foto dentro il riquadro, in % del riquadro (stessi calcoli di photo_jr.collage_crop).
function colImgBox(card, cell) {
  colCrop(card);
  const k = (card.w0 / card.h0) / ((cell.w * COL_W) / (cell.h * COL_H));
  const w = 100 * card.cz * Math.max(1, k), h = 100 * card.cz * Math.max(1, 1 / k);
  return {l:(100 - w) * card.cpx, t:(100 - h) * card.cpy, w, h};
}
function colImgStyle(card, cell) {
  const b = colImgBox(card, cell);
  return `left:${b.l.toFixed(3)}%;top:${b.t.toFixed(3)}%;width:${b.w.toFixed(3)}%;height:${b.h.toFixed(3)}%`;
}

function jrCollageCells() {
  const t = jrTemplates()[jrb.tpl];
  if (!t) return [];
  const order = jrOrder();
  return t.cells.map((c,i) => {
    const card = colCrop(jrb.cards[order[i]]);
    return {photo_id:card.id, x:+c.x.toFixed(5), y:+c.y.toFixed(5), w:+c.w.toFixed(5), h:+c.h.toFixed(5),
      px:+card.cpx.toFixed(5), py:+card.cpy.toFixed(5), z:+card.cz.toFixed(4)};
  });
}

function colCellsHtml(t, order, sel) {
  return t.cells.map((c,i) => {
    const card = jrb.cards[order[i]];
    return `<div class="col-cell${i === sel ? ' sel' : ''}" data-i="${i}" style="left:${c.x * 100}%;top:${c.y * 100}%;width:${c.w * 100}%;height:${c.h * 100}%"><img alt="" draggable="false" src="${card.small || card.url}" style="${colImgStyle(card,c)}"></div>`;
  }).join('');
}

function colSelIdx() {
  const t = jrTemplates()[jrb.tpl];
  return t && Number.isInteger(jrb.csel) && jrb.csel >= 0 && jrb.csel < t.cells.length ? jrb.csel : -1;
}
const colCellAt = i => jrTemplates()[jrb.tpl].cells[i];
const colCardAt = i => jrb.cards[jrOrder()[i]];

function colPaint(i) {
  const img = $('colBig').querySelector(`.col-cell[data-i="${i}"] img`);
  if (img) img.style.cssText = colImgStyle(colCardAt(i), colCellAt(i));
}

// Zoom tenendo ferma la parte di foto sotto il punto (ax, ay) del riquadro (0-1): il centro, il pizzico, il mouse.
function colZoomTo(i, z, ax = .5, ay = .5) {
  const card = colCrop(colCardAt(i)), cell = colCellAt(i);
  const b0 = colImgBox(card, cell);
  const u = (ax * 100 - b0.l) / b0.w, v = (ay * 100 - b0.t) / b0.h;
  card.cz = Math.min(COL_ZOOM[1], Math.max(COL_ZOOM[0], z));
  const b1 = colImgBox(card, cell);
  if (b1.w - 100 > 1e-6) card.cpx = jrcClamp((ax * 100 - u * b1.w) / (100 - b1.w));
  if (b1.h - 100 > 1e-6) card.cpy = jrcClamp((ay * 100 - v * b1.h) / (100 - b1.h));
  colPaint(i);
}

function colPan(i, dx, dy, rect) {
  const card = colCrop(colCardAt(i)), b = colImgBox(card, colCellAt(i));
  if (b.w - 100 > 1e-6) card.cpx = jrcClamp((b.l + dx / rect.width * 100) / (100 - b.w));
  if (b.h - 100 > 1e-6) card.cpy = jrcClamp((b.t + dy / rect.height * 100) / (100 - b.h));
  colPaint(i);
}

// Anteprima grande quanto lo spazio libero: titolo, anteprima, frase e pulsante layout stanno in una sola pagina.
function fitColBig() {
  const big = $('colBig');
  if (!big.offsetParent) return;
  const free = $('stage').getBoundingClientRect().bottom - big.getBoundingClientRect().top - 132;
  big.style.width = `${Math.floor(Math.max(180, Math.min(big.parentElement.clientWidth, free * .75, 420)))}px`;
}

function colUpdateUi() {
  const i = colSelIdx();
  $('colBig').querySelectorAll('.col-cell').forEach(el => el.classList.toggle('sel',Number(el.dataset.i) === i));
  $('colHint').textContent = i >= 0 ? 'Trascina o pizzica · tocca un’altra foto per scambiare'
    : 'Tocca una foto per ritoccarla o scambiarla.';
}

// Mini collage schematico (come il mini campo dei moduli): un rettangolo per riquadro.
function colMini(t) {
  const r = t.cells.map(c => `<rect class="lc" x="${(c.x * 100 + 1.2).toFixed(2)}" y="${(c.y * 133.3 + 1.2).toFixed(2)}" width="${Math.max(1,c.w * 100 - 2.4).toFixed(2)}" height="${Math.max(1,c.h * 133.3 - 2.4).toFixed(2)}" rx="1.5"/>`).join('');
  return `<svg viewBox="0 0 100 133.3" aria-hidden="true">${r}</svg>`;
}

// Scelta del layout: un pulsante col layout attuale, che apre il foglio con tutti i layout (come i moduli del Probabile XI).
function renderColGrid() {
  const list = jrTemplates(), box = $('colGrid');
  if (!list.length) { box.innerHTML = ''; return; }
  box.innerHTML = `<button type="button" class="mod-btn">${colMini(list[jrb.tpl])}<span><b>Layout ${jrb.tpl + 1}</b><small>tocca per cambiare</small></span><i>▾</i></button>`;
  box.firstChild.addEventListener('click',openColSheet);
}

function openColSheet() {
  haptic('select');
  const list = jrTemplates(), sh = $('modSh');
  sh.innerHTML = `<div class="mod-bar"></div><div class="mod-top"><b>Layout</b><button type="button" id="colShClose">Chiudi</button></div>`
    + `<div class="mod-grid">${list.map((t,i) => `<button type="button" class="mod-tile${i === jrb.tpl ? ' on' : ''}" data-i="${i}">${colMini(t)}<span>${i + 1}</span></button>`).join('')}</div>`;
  $('colShClose').addEventListener('click',closeModSheet);
  sh.querySelectorAll('.mod-tile').forEach(b => b.addEventListener('click',() => {
    const i = Number(b.dataset.i);
    closeModSheet();
    if (i === jrb.tpl) return;
    haptic('select');
    jrb.tpl = i; jrb.order = null; jrb.swap = -1; jrb.csel = -1;
    renderJrLayout(); renderSteps();
  }));
  $('modOv').classList.add('open');
}

function renderJrLayout(reset = false) {
  const list = jrTemplates();
  const big = $('colBig'), grid = $('colGrid');
  if (reset) { jrb.swap = -1; jrb.csel = -1; }
  if (!list.length) { big.innerHTML = ''; grid.innerHTML = ''; colUpdateUi(); return; }
  const t = list[jrb.tpl], order = jrOrder();
  big.style.setProperty('--k', (big.clientWidth || 300) / COL_W);
  big.innerHTML = colCellsHtml(t, order, colSelIdx()) + '<img class="overlay" alt="">';
  jrLogoSrc(big.querySelector('.overlay'),'white');
  colUpdateUi();
  renderColGrid();
}

function initJrCollage() {
  const big = $('colBig');
  const ptrs = new Map();
  let g = null, wheelTimer = 0;
  const snap = () => {
    const pts = [...ptrs.values()];
    if (pts.length === 1) return {x:pts[0].x, y:pts[0].y, d:0};
    const [a,b] = pts;
    return {x:(a.x + b.x) / 2, y:(a.y + b.y) / 2, d:Math.hypot(a.x - b.x, a.y - b.y)};
  };
  const select = i => { if (colSelIdx() !== i) { haptic('select'); jrb.csel = i; colUpdateUi(); } };

  // Tocca un riquadro per sceglierlo; poi trascina per spostare la foto, pizzica (o rotella) per lo zoom.
  big.addEventListener('pointerdown',e => {
    const el = e.target.closest('.col-cell');
    if (!ptrs.size) {
      if (!el) { g = null; if (jrb.csel >= 0) { jrb.csel = -1; colUpdateUi(); } return; }
      const i = Number(el.dataset.i);
      const cur = colSelIdx();
      g = {i, el, swapTap:cur >= 0 && cur !== i, from:cur, x0:e.clientX, y0:e.clientY, dirty:false};
      if (!g.swapTap) select(i);
    }
    if (!g) return;
    ptrs.set(e.pointerId,{x:e.clientX, y:e.clientY});
    if (!g.swapTap) { try { big.setPointerCapture(e.pointerId); } catch (_) {} }
    g.last = snap();
  });
  big.addEventListener('pointermove',e => {
    if (!g || g.swapTap || !ptrs.has(e.pointerId)) return;
    ptrs.set(e.pointerId,{x:e.clientX, y:e.clientY});
    const now = snap(), rect = g.el.getBoundingClientRect();
    colPan(g.i, now.x - g.last.x, now.y - g.last.y, rect);
    if (now.d && g.last.d) {
      colZoomTo(g.i, colCardAt(g.i).cz * now.d / g.last.d, (now.x - rect.left) / rect.width, (now.y - rect.top) / rect.height);
    }
    g.last = now; g.dirty = true;
    colUpdateUi();
  });
  const end = e => {
    if (!ptrs.delete(e.pointerId) || !g) return;
    if (g.swapTap) {
      // Con una foto scelta, un tocco su un'altra la scambia; se invece si trascina, si sceglie quella.
      if (e.type === 'pointerup') {
        const a = g.from, b = g.i;
        if (Math.hypot(e.clientX - g.x0, e.clientY - g.y0) < 10) {
          const o = jrOrder().slice(); [o[a], o[b]] = [o[b], o[a]]; jrb.order = o; haptic('success');
        } else { haptic('select'); }
        jrb.csel = b; g = null;
        renderJrLayout();
      } else if (!ptrs.size) g = null;
      return;
    }
    if (ptrs.size) { g.last = snap(); return; }
    if (g.dirty) renderColGrid();
    g = null;
  };
  big.addEventListener('pointerup',end);
  big.addEventListener('pointercancel',end);
  big.addEventListener('wheel',e => {
    const el = e.target.closest('.col-cell');
    if (!el) return;
    e.preventDefault();
    const i = Number(el.dataset.i), r = el.getBoundingClientRect();
    select(i);
    colZoomTo(i, colCardAt(i).cz * Math.exp(-e.deltaY * .0015), (e.clientX - r.left) / r.width, (e.clientY - r.top) / r.height);
    colUpdateUi();
    clearTimeout(wheelTimer); wheelTimer = setTimeout(renderColGrid,250);
  },{passive:false});
  // Doppio tocco: ingrandisce sul punto toccato, o rimette la foto com'era.
  big.addEventListener('dblclick',e => {
    const el = e.target.closest('.col-cell');
    if (!el) return;
    const i = Number(el.dataset.i), r = el.getBoundingClientRect(), card = colCrop(colCardAt(i));
    select(i);
    if (card.cz > 1.05) { card.cz = 1; card.cpx = COL_DEF[0]; card.cpy = COL_DEF[1]; colPaint(i); }
    else colZoomTo(i, 2.2, (e.clientX - r.left) / r.width, (e.clientY - r.top) / r.height);
    colUpdateUi(); renderColGrid();
  });

  window.addEventListener('resize',() => { if ($('colBig').offsetParent) { fitColBig(); renderJrLayout(); } });
}
