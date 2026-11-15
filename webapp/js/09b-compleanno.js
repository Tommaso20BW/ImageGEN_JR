/* ---------- Compleanno ----------
   Passi: Giocatore (lista con ricerca) → Foto (le sue pose con la maglia home in quadretti, divise
   in Matchday, Starting e Goal, o Saved per i portieri) → Dati (nome sulla striscia, data di nascita
   ed età) → Posizione (trascina il giocatore, due dita per lo zoom). La data arriva da sola (asset o Wikidata) insieme alle foto; si può sempre correggere. */
const BD_GROUPS = [['matchday','Matchday'],['starting','Starting'],['goal','Goal'],['saved','Saved']];
// Un solo Compleanno, due tipi: Rosa attuale (pose degli asset) o Ex giocatore (foto caricata).
const BD_MODES = [['now','Rosa attuale'],['old','Ex giocatore']];
// manual: giocatore non in elenco, aggiunto a mano con una foto caricata (scontornata dal servizio).
// births: date di nascita della rosa (nome -> AAAA-MM-GG) per ordinare l'elenco dal prossimo compleanno.
const bd = {mode:'now', manual:false, player:'', photos:[], photo:'', loading:false, key:'', birth:'', page:null,
  frame:{x:0, y:0, zoom:1}, ghostKey:'', ghostUrl:'', births:null, birthsBusy:false};

// Giorni al prossimo compleanno (0 = oggi); Infinity se la data non c'è.
function bdDaysTo(iso) {
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(iso || '');
  if (!m) return Infinity;
  const today = new Date(); today.setHours(0,0,0,0);
  let next = new Date(today.getFullYear(), Number(m[2]) - 1, Number(m[3]));
  if (next < today) next = new Date(today.getFullYear() + 1, Number(m[2]) - 1, Number(m[3]));
  return Math.round((next - today) / 864e5);
}
// Data del compleanno (gg.mm) e quanto manca, per l'elenco: [data, mancano] o null.
function bdWhen(iso) {
  const n = bdDaysTo(iso);
  if (n === Infinity) return null;
  return [`${iso.slice(8,10)}.${iso.slice(5,7)}`, n === 0 ? 'Oggi' : n === 1 ? 'Domani' : `${n} gg`];
}
async function bdLoadBirths() {
  if (bd.births || bd.birthsBusy || !directBase || !session) return;
  bd.birthsBusy = true;
  try {
    const response = await netFetch(`${directBase}/bdaybirths`,{
      method:'POST', headers:{'Content-Type':'application/json','X-ImageGEN-Session':session},
      body:JSON.stringify({v:1, session})
    }, 20000, 2);
    const body = await response.json().catch(() => ({}));
    if (response.ok && body.ok) { bd.births = body.births || {}; bdRender(); }
  } catch (_) {
  } finally {
    bd.birthsBusy = false;
  }
}

function bdAge(iso) {
  const m = /^(\d{4})-\d{2}-\d{2}$/.exec(iso || '');
  return m ? String(new Date().getFullYear() - Number(m[1])) : '';
}
function bdSetBirth(iso) {
  $('bdBirth').value = iso || '';
  $('bdAge').value = bdAge(iso);
}
function bdPhotoOf(id) { return bd.photos.find(p => p.id === id); }

/* Ex giocatore (grafica 'bdold' del servizio): Nome → Foto (caricata e scontornata dal servizio)
   → Posizione (stesso editor: trascina, due dita per lo zoom). */
const bdo = {id:'', thumb:'', height:0, page:null, loading:false};
const bdOld = () => kind === 'bday' && bd.mode === 'old';
// Foto caricata dall'utente: Ex giocatore, o giocatore della rosa aggiunto a mano.
const bdUploaded = () => bdOld() || (kind === 'bday' && bd.manual);
function bdClearUpload() {
  Object.assign(bdo,{id:'', thumb:'', height:0, page:null, loading:false});
  $('bdoPreview').hidden = true;
  $('bdoStatus').textContent = '';
}
// Testi della schermata Foto caricata: diversi per Ex giocatore e giocatore aggiunto a mano.
function bdoTexts() {
  const old = bd.mode === 'old';
  $('bdoEyebrow').textContent = old ? 'Compleanno · Ex giocatore' : 'Compleanno · Rosa attuale';
  $('bdoLead').textContent = old ? "Carica la foto del giocatore: scontorno e filtro d'epoca li fa l'app."
    : "Carica la foto del giocatore: lo scontorno lo fa l'app.";
}
function bdSetMode(v) {
  if (v !== bd.mode) { bd.mode = v; bd.frame = {x:0, y:0, zoom:1}; bd.ghostKey = ''; bdClearUpload(); }
  bdoTexts();
  buildFlow();
  renderSteps();
}
// Giocatore non in elenco: si salta la scelta delle pose e si carica la foto.
function bdManualStart() {
  haptic('select');
  clearError();
  if (!bd.manual) {
    Object.assign(bd,{manual:true, player:'', photos:[], photo:'', key:'', birth:'', frame:{x:0, y:0, zoom:1}, ghostKey:''});
    $('bdName').value = '';
    bdSetBirth('');
    bdClearUpload();
  }
  bdoTexts();
  buildFlow();
  bdRender();
  renderSteps();
  nextField(true);
}
// Persona e pagina dell'editor: posa degli asset o foto caricata e scontornata.
function bdCur() { return bdUploaded() ? (bdo.id ? {id:bdo.id, thumb:bdo.thumb, height:bdo.height} : null) : bdPhotoOf(bd.photo); }
function bdCurPage() { return bdUploaded() ? bdo.page : bd.page; }

async function bdoUpload(file) {
  if (!file) return;
  clearError();
  if (!directBase || !session) { showError('Sessione vecchia. Riavvia ImageGen dal workflow.'); return; }
  bdo.loading = true;
  $('bdoStatus').textContent = '';
  renderSteps();
  // stessa schermata di caricamento delle altre grafiche, fino a scontorno finito
  showBusy('Scontorno il giocatore…', 'Carico la foto…', 'ppcut');
  const myBusy = busy;
  try {
    const {blob,type} = await preparePhoto(file, true);
    const up = await netFetch(`${directBase}/upload`,{
      method:'POST', headers:{'Content-Type':type,'X-ImageGEN-Session':session}, body:blob
    }, 60000);
    const ub = await up.json().catch(() => ({}));
    if (!up.ok || !ub.ok) throw new Error(ub.error || 'Caricamento non riuscito.');
    if (busy === myBusy) $('busySub').textContent = 'Separo il giocatore dallo sfondo: ci vogliono alcuni secondi.';
    const cut = await netFetch(`${directBase}/bdoldcut`,{
      method:'POST', headers:{'Content-Type':'application/json','X-ImageGEN-Session':session},
      body:JSON.stringify({v:1, session, photo_id:ub.photo_id, mode:bdOld() ? 'old' : 'now'})
    }, 120000);
    const cb = await cut.json().catch(() => ({}));
    if (!cut.ok || !cb.ok) throw new Error(cb.error || 'Scontorno non riuscito.');
    Object.assign(bdo,{id:ub.photo_id, thumb:cb.thumb, height:cb.height, page:cb.page});
    if (busy === myBusy) await finishBusy();
    bd.frame = {x:0, y:0, zoom:1};
    $('bdoPreview').src = cb.thumb;
    $('bdoPreview').hidden = false;
    $('bdoStatus').textContent = 'Fatto: tocca la foto per cambiarla.';
    haptic('success');
    setTimeout(() => { if (flow[flowIndex] === 'bdophoto') nextField(true); }, 250);
  } catch (err) {
    $('bdoStatus').textContent = bdo.id ? 'Tocca la foto per cambiarla.' : '';
    showError(err && err.message ? err.message : 'Caricamento non riuscito.');
  } finally {
    if (busy === myBusy) hideBusy();
    bdo.loading = false;
    $('bdoFile').value = '';
    renderSteps();
  }
}

function bdoPayload() {
  const name = $('bdoName').value.trim();
  if (!name) throw new Error('Scrivi il nome.');
  if (!bdo.id) throw new Error('Carica la foto.');
  return {v:1, action:'render', session, data:{kind:'bdold', name, photo_id:bdo.id, frame:{...bd.frame}}};
}

function bdRender() {
  const q = $('bdPlayerSearch').value;
  let matches = playersLoaded ? searchItems(players,q) : [];
  // dal prossimo compleanno (oggi in cima); chi non ha la data in fondo
  const births = bd.births || {};
  if (bd.births) matches = matches.map((p,i) => [p,i]).sort((a,b) =>
    (bdDaysTo(births[a[0].name]) - bdDaysTo(births[b[0].name])) || (a[1] - b[1])).map(r => r[0]);
  const chosen = players.find(p => p.name === bd.player);
  $('bdPlayerSummary').textContent = bd.loading ? 'Caricamento foto…'
    : !playersLoaded ? 'Caricamento giocatori…' : !matches.length ? 'Nessun risultato.'
    : chosen ? `Selezionato: ${surnameOf(chosen)}` : bd.manual ? 'Aggiunto a mano: carica la sua foto.' : '';
  renderResults('bdPlayerList',matches,bd.player,item => surnameOf(item),item => { bdPick(item.name); },null,Infinity);
  // data e giorni che mancano: a parte, piccoli e grigi a destra del nome
  for (const row of $('bdPlayerList').children) {
    let tag = row.querySelector('.bd-when');
    if (!tag) {
      tag = document.createElement('span');
      tag.className = 'bd-when';
      row.insertBefore(tag,row.querySelector('.tick'));
    }
    const when = bdWhen(births[row.dataset.name]);
    tag.innerHTML = '';
    if (when) {
      const d = document.createElement('b'), n = document.createElement('small');
      d.textContent = when[0];
      n.textContent = when[1];
      if (when[1] === 'Oggi') n.className = 'today';
      tag.append(d, n);
    }
  }
}

function bdPick(name) {
  if (bd.manual) { bd.manual = false; bdClearUpload(); buildFlow(); }
  if (name !== bd.player) {
    Object.assign(bd,{player:name, photos:[], photo:'', key:'', birth:''});
    $('bdName').value = '';
    bdSetBirth('');
  }
  bdRender();
  bdLoad(true);
}

// Pose e data di nascita del giocatore scelto. advance: appena arrivano si passa alle foto.
async function bdLoad(advance=false) {
  if (!bd.player) return;
  if (bd.key === bd.player && bd.photos.length) { if (advance && flow[flowIndex] === 'bdplayer') nextField(true); return; }
  clearError();
  if (!directBase || !session) { showError('Sessione vecchia. Riavvia ImageGen dal workflow.'); return; }
  const key = bd.player;
  bd.loading = true; bdRender(); renderSteps();
  try {
    const response = await netFetch(`${directBase}/bdayphotos`,{
      method:'POST', headers:{'Content-Type':'application/json','X-ImageGEN-Session':session},
      body:JSON.stringify({v:1, session, player:key})
    }, 30000, 2);
    const body = await response.json().catch(() => ({}));
    if (!response.ok || !body.ok) throw new Error(body.error || 'Foto del giocatore non disponibili.');
    if (key !== bd.player) return;          // scelta cambiata mentre arrivava: vale l'ultima
    bd.photos = body.photos || [];
    bd.page = body.page || null;
    bd.key = key;
    bd.birth = body.birth || '';
    if (!$('bdName').value.trim()) $('bdName').value = body.name || key.toUpperCase();
    if (!$('bdBirth').value) bdSetBirth(bd.birth);
    haptic('success');
    if (advance && flow[flowIndex] === 'bdplayer') setTimeout(() => nextField(true), 180);
  } catch (err) {
    if (key === bd.player) { bd.player = ''; showError(err && err.message ? err.message : 'Foto del giocatore non disponibili.'); }
  } finally {
    if (key === bd.player || !bd.loading) bd.loading = false;
    bdRender(); renderSteps();
  }
}

function bdPhotosRender() {
  const box = $('bdPhotos');
  box.innerHTML = '';
  const chosen = players.find(p => p.name === bd.player);
  $('bdPhotoLead').textContent = chosen ? `Tocca la foto di ${surnameOf(chosen)} da mettere nel poster.` : 'Scegli prima il giocatore.';
  BD_GROUPS.forEach(([group,label]) => {
    const rows = bd.photos.filter(p => p.group === group);
    if (!rows.length) return;
    const head = document.createElement('div');
    head.className = 'bd-group';
    head.textContent = label;
    box.appendChild(head);
    const grid = document.createElement('div');
    grid.className = 'iq-grid';
    rows.forEach(p => {
      const b = document.createElement('button');
      b.type = 'button';
      b.className = 'iq-ph bd-ph' + (p.id === bd.photo ? ' on' : '');
      b.style.backgroundImage = `url("${p.thumb}")`;
      b.setAttribute('aria-label',label);
      b.addEventListener('click',() => {
        haptic('select');
        if (bd.photo !== p.id) bd.frame = {x:0, y:0, zoom:1};
        bd.photo = p.id;
        bdPhotosRender();
        renderSteps();
        setTimeout(() => { if (flow[flowIndex] === 'bdphoto') nextField(true); }, 180);
      });
      grid.appendChild(b);
    });
    box.appendChild(grid);
  });
}

function bdValidate(step) {
  if (step === 'bdplayer' && !bd.manual) {
    if (!bd.player) { showError('Scegli il giocatore.'); return false; }
    if (!bd.photos.length) { if (!bd.loading) bdLoad(); showError('Attendi le foto del giocatore.'); return false; }
  }
  if (step === 'bdphoto' && !bdPhotoOf(bd.photo)) { showError('Tocca una foto.'); return false; }
  if (step === 'bdoname' && !$('bdoName').value.trim()) { showError('Scrivi il nome.'); return false; }
  if (step === 'bdophoto' && !bdo.id) { showError(bdo.loading ? 'Attendi lo scontorno.' : 'Carica la foto.'); return false; }
  if (step === 'bdinfo') {
    if (!$('bdName').value.trim()) { showError('Scrivi il nome.'); return false; }
    if (!/^\d{4}-\d{2}-\d{2}$/.test($('bdBirth').value)) { showError('Scrivi la data di nascita.'); return false; }
  }
  return true;
}

function bdStepValue(step) {
  if (step === 'bdplayer') {
    if (bd.manual) return 'Aggiunto a mano';
    const p = players.find(x => x.name === bd.player); return p ? surnameOf(p) : '';
  }
  if (step === 'bdphoto') {
    const p = bdPhotoOf(bd.photo);
    return p ? labelOf(BD_GROUPS,p.group) : '';
  }
  if (step === 'bdmode') return labelOf(BD_MODES,bd.mode);
  if (step === 'bdoname') return $('bdoName').value.trim().toUpperCase();
  if (step === 'bdophoto') return bdo.loading ? 'Scontorno…' : bdo.id ? 'Caricata' : '';
  if (step === 'bdpos') {
    const f = bd.frame;
    return f.x || f.y || f.zoom !== 1 ? `Zoom ${Math.round(f.zoom * 100)}%` : 'Automatica';
  }
  if (step === 'bdinfo') {
    const d = $('bdBirth').value, a = $('bdAge').value.trim();
    return d ? `${d.slice(8,10)}.${d.slice(5,7)}.${d.slice(0,4)}${a ? ` · ${a} anni` : ''}` : '';
  }
  return null;
}

function bdPayload() {
  const name = $('bdName').value.trim(), birth = $('bdBirth').value;
  if (bd.manual) {
    if (!bdo.id) throw new Error('Carica la foto.');
    if (!name) throw new Error('Scrivi il nome.');
    if (!birth) throw new Error('Scrivi la data di nascita.');
    return {v:1, action:'render', session, data:{kind:'bday', photo_id:bdo.id, name, birth,
      age:$('bdAge').value.trim(), frame:{...bd.frame}}};
  }
  if (!bd.player) throw new Error('Scegli il giocatore.');
  if (!bdPhotoOf(bd.photo)) throw new Error('Scegli la foto.');
  if (!name) throw new Error('Scrivi il nome.');
  if (!birth) throw new Error('Scrivi la data di nascita.');
  return {v:1, action:'render', session, data:{kind:'bday', player:bd.player, photo:bd.photo, name, birth,
    age:$('bdAge').value.trim(), frame:{...bd.frame}}};
}

function bdReset() {
  Object.assign(bd,{mode:'now', manual:false, player:'', photos:[], photo:'', loading:false, key:'', birth:'', frame:{x:0, y:0, zoom:1}});
  ['bdPlayerSearch','bdName','bdBirth','bdAge','bdoName'].forEach(id => { $(id).value = ''; });
  bdClearUpload();
  bdoTexts();
}

function initBirthday() {
  initBirthdayEditor();
  $('bdPlayerSearch').addEventListener('input',() => bdRender());
  $('bdBirth').addEventListener('change',() => { $('bdAge').value = bdAge($('bdBirth').value); renderSteps(); });
  ['bdName','bdAge','bdoName'].forEach(id => $(id).addEventListener('input',() => renderSteps()));
  $('bdoFile').addEventListener('change',e => bdoUpload(e.target.files && e.target.files[0]));
  $('bdManual').addEventListener('click',bdManualStart);
}

/* --- Posizione: il poster senza giocatore (sagoma del servizio) e sopra la sagoma del giocatore,
   tagliata alla striscia del nome come nella grafica. Stesse misure della pagina 1500x2000. */
function bdLayout() {
  const frame = $('bdFrame'), img = $('bdPlayer'), page = bdCurPage(), p = bdCur();
  if (!frame.offsetParent || !page || !p) return;
  const stage = $('stage');
  const free = stage.getBoundingClientRect().bottom - frame.getBoundingClientRect().top - 34;
  frame.style.width = `${Math.floor(Math.max(200, Math.min(frame.parentElement.clientWidth, free * page.w / page.h)))}px`;
  const [zmin, zmax] = page.zoom || [0.4, 2.5];
  const f = bd.frame;
  f.zoom = Math.min(zmax, Math.max(zmin, f.zoom));
  f.x = Math.min(0.6, Math.max(-0.6, f.x));
  f.y = Math.min(0.6, Math.max(-0.6, f.y));
  const k = frame.clientWidth / page.w;
  const h = p.height * f.zoom, w = h * ((img.naturalWidth || 3) / (img.naturalHeight || 4));
  img.style.width = `${w * k}px`;
  img.style.height = `${h * k}px`;
  img.style.left = `${(page.cx + f.x * page.w - w / 2) * k}px`;
  img.style.top = `${(page.foot + f.y * page.h - h) * k}px`;
  $('bdClip').style.height = `${page.cut / page.h * 100}%`;
}

async function bdGhost() {
  let body;
  try { body = JSON.stringify(bdOld() ? bdoPayload() : bdPayload()); } catch (_) { return; }
  const key = body.replace(/"frame":\{[^}]*\}/, '').replace(/"photo(_id)?":"[^"]*"/, '');
  const ghost = $('bdGhost');
  if (key === bd.ghostKey && bd.ghostUrl) { ghost.src = bd.ghostUrl; ghost.hidden = false; return; }
  bd.ghostKey = key;
  ghost.hidden = true;
  $('bdPosHint').textContent = 'Preparo il poster…';
  let real = false;
  showReadyGhost(ghost, () => real || bd.ghostKey !== key, () => { ghost.hidden = false; });
  try {
    const response = await netFetch(`${directBase}/ghost`, {
      method:'POST', headers:{'Content-Type':'application/json','X-ImageGEN-Session':session}, body
    }, 60000, 2);
    if (!response.ok || bd.ghostKey !== key) return;
    const url = URL.createObjectURL(await response.blob());
    if (bd.ghostUrl) { try { URL.revokeObjectURL(bd.ghostUrl); } catch (_) {} }
    bd.ghostUrl = url;
    real = true;
    ghost.src = url;
    ghost.hidden = false;
  } catch (_) {
  } finally {
    if (bd.ghostKey === key) $('bdPosHint').textContent = bdOld() ? 'Il giocatore sta davanti a HAPPY BIRTHDAY.' : 'Il giocatore finisce sotto la striscia del nome.';
  }
}

function bdOpenPos() {
  const p = bdCur(), img = $('bdPlayer');
  $('bdFrame').classList.toggle('old', bdOld());
  if (p && img.dataset.src !== p.id) {
    img.dataset.src = p.id;
    img.onload = () => bdLayout();
    img.src = p.thumb;
  }
  requestAnimationFrame(bdLayout);
  bdGhost();
}

function initBirthdayEditor() {
  const frame = $('bdFrame');
  const pointers = new Map();
  let last = null;
  const snapshot = () => {
    const pts = [...pointers.values()];
    if (pts.length === 1) return {x:pts[0].x, y:pts[0].y, d:0};
    const [a,b] = pts;
    return {x:(a.x + b.x) / 2, y:(a.y + b.y) / 2, d:Math.hypot(a.x - b.x, a.y - b.y)};
  };
  frame.addEventListener('pointerdown',e => {
    frame.setPointerCapture(e.pointerId);
    pointers.set(e.pointerId,{x:e.clientX, y:e.clientY});
    last = snapshot();
    frame.classList.add('dragging');
  });
  frame.addEventListener('pointermove',e => {
    if (!pointers.has(e.pointerId) || !last) return;
    pointers.set(e.pointerId,{x:e.clientX, y:e.clientY});
    const now = snapshot();
    bd.frame.x += (now.x - last.x) / frame.clientWidth;
    bd.frame.y += (now.y - last.y) / frame.clientHeight;
    if (now.d && last.d) bd.frame.zoom *= now.d / last.d;
    last = now;
    bdLayout();
  });
  const end = e => {
    pointers.delete(e.pointerId);
    last = pointers.size ? snapshot() : null;
    if (!pointers.size) { frame.classList.remove('dragging'); renderSteps(); }
  };
  frame.addEventListener('pointerup',end);
  frame.addEventListener('pointercancel',end);
  frame.addEventListener('wheel',e => {
    e.preventDefault();
    bd.frame.zoom *= Math.exp(-e.deltaY * 0.0015);
    bdLayout();
    renderSteps();
  },{passive:false});
  frame.addEventListener('touchmove',e => e.preventDefault(),{passive:false});
  $('bdPosReset').addEventListener('click',() => { haptic('select'); bd.frame = {x:0, y:0, zoom:1}; bdLayout(); renderSteps(); });
  window.addEventListener('resize',bdLayout);
}

// Caricato prima di 10-avvio.js (che disegna già i passi): si collega da solo, la pagina c'è già.
initBirthday();
