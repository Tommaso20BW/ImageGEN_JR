/* ---------- Compleanno ----------
   Passi: Giocatore (lista con ricerca) → Foto (le sue pose con la maglia home in quadretti, divise
   in Matchday, Starting e Goal, o Saved per i portieri) → Dati (nome sulla striscia, data di nascita
   ed età) → Posizione (trascina il giocatore, due dita per lo zoom). La data arriva da sola (asset o Wikidata) insieme alle foto; si può sempre correggere. */
const BD_GROUPS = [['matchday','Matchday'],['starting','Starting'],['goal','Goal'],['saved','Saved']];
const bd = {player:'', photos:[], photo:'', loading:false, key:'', birth:'', page:null,
  frame:{x:0, y:0, zoom:1}, ghostKey:'', ghostUrl:''};

function bdAge(iso) {
  const m = /^(\d{4})-\d{2}-\d{2}$/.exec(iso || '');
  return m ? String(new Date().getFullYear() - Number(m[1])) : '';
}
function bdSetBirth(iso) {
  $('bdBirth').value = iso || '';
  $('bdAge').value = bdAge(iso);
}
function bdPhotoOf(id) { return bd.photos.find(p => p.id === id); }

function bdRender() {
  const q = $('bdPlayerSearch').value;
  const matches = playersLoaded ? searchItems(players,q) : [];
  const chosen = players.find(p => p.name === bd.player);
  $('bdPlayerSummary').textContent = bd.loading ? 'Caricamento foto…'
    : !playersLoaded ? 'Caricamento giocatori…' : !matches.length ? 'Nessun risultato.'
    : chosen ? `Selezionato: ${surnameOf(chosen)}` : '';
  renderResults('bdPlayerList',matches,bd.player,item => surnameOf(item),item => { bdPick(item.name); },null,Infinity);
}

function bdPick(name) {
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
  if (step === 'bdplayer') {
    if (!bd.player) { showError('Scegli il giocatore.'); return false; }
    if (!bd.photos.length) { if (!bd.loading) bdLoad(); showError('Attendi le foto del giocatore.'); return false; }
  }
  if (step === 'bdphoto' && !bdPhotoOf(bd.photo)) { showError('Tocca una foto.'); return false; }
  if (step === 'bdinfo') {
    if (!$('bdName').value.trim()) { showError('Scrivi il nome.'); return false; }
    if (!/^\d{4}-\d{2}-\d{2}$/.test($('bdBirth').value)) { showError('Scrivi la data di nascita.'); return false; }
  }
  return true;
}

function bdStepValue(step) {
  if (step === 'bdplayer') { const p = players.find(x => x.name === bd.player); return p ? surnameOf(p) : ''; }
  if (step === 'bdphoto') {
    const p = bdPhotoOf(bd.photo);
    return p ? labelOf(BD_GROUPS,p.group) : '';
  }
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
  if (!bd.player) throw new Error('Scegli il giocatore.');
  if (!bdPhotoOf(bd.photo)) throw new Error('Scegli la foto.');
  const name = $('bdName').value.trim(), birth = $('bdBirth').value;
  if (!name) throw new Error('Scrivi il nome.');
  if (!birth) throw new Error('Scrivi la data di nascita.');
  return {v:1, action:'render', session, data:{kind:'bday', player:bd.player, photo:bd.photo, name, birth,
    age:$('bdAge').value.trim(), frame:{...bd.frame}}};
}

function bdReset() {
  Object.assign(bd,{player:'', photos:[], photo:'', loading:false, key:'', birth:'', frame:{x:0, y:0, zoom:1}});
  ['bdPlayerSearch','bdName','bdBirth','bdAge'].forEach(id => { $(id).value = ''; });
}

function initBirthday() {
  initBirthdayEditor();
  $('bdPlayerSearch').addEventListener('input',() => bdRender());
  $('bdBirth').addEventListener('change',() => { $('bdAge').value = bdAge($('bdBirth').value); renderSteps(); });
  ['bdName','bdAge'].forEach(id => $(id).addEventListener('input',() => renderSteps()));
}

/* --- Posizione: il poster senza giocatore (sagoma del servizio) e sopra la sagoma del giocatore,
   tagliata alla striscia del nome come nella grafica. Stesse misure della pagina 1500x2000. */
function bdLayout() {
  const frame = $('bdFrame'), img = $('bdPlayer'), page = bd.page, p = bdPhotoOf(bd.photo);
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
  try { body = JSON.stringify(bdPayload()); } catch (_) { return; }
  const key = body.replace(/"frame":\{[^}]*\}/, '').replace(/"photo":"[^"]*"/, '');
  const ghost = $('bdGhost');
  if (key === bd.ghostKey && bd.ghostUrl) { ghost.src = bd.ghostUrl; ghost.hidden = false; return; }
  bd.ghostKey = key;
  ghost.hidden = true;
  $('bdPosHint').textContent = 'Preparo il poster…';
  try {
    const response = await netFetch(`${directBase}/ghost`, {
      method:'POST', headers:{'Content-Type':'application/json','X-ImageGEN-Session':session}, body
    }, 60000, 2);
    if (!response.ok || bd.ghostKey !== key) return;
    const url = URL.createObjectURL(await response.blob());
    if (bd.ghostUrl) { try { URL.revokeObjectURL(bd.ghostUrl); } catch (_) {} }
    bd.ghostUrl = url;
    ghost.src = url;
    ghost.hidden = false;
  } catch (_) {
  } finally {
    if (bd.ghostKey === key) $('bdPosHint').textContent = 'Il giocatore finisce sotto la striscia del nome.';
  }
}

function bdOpenPos() {
  const p = bdPhotoOf(bd.photo), img = $('bdPlayer');
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
