/* Mini App ImageGen JR. File caricati in ordine da index.html: l'ordine conta. */
/* ---------- Barra in alto stile Apple ---------- */
// Passaggi fatti di una sola scelta: si va avanti toccando la riga, quindi niente "Fine".
const NAV_AUTO = new Set(['tablecomp','tableview','competition','side','kit','jrratio','jrstyle','calmonth','pose','moment','mdpick','sentlist','igsent','iqpick']);
function syncNav() {
  const home = document.body.classList.contains('home-mode');
  const screenName = previewMode ? 'preview' : (home ? 'home' : flow[flowIndex]);
  document.body.classList.toggle('preview-mode', !!previewMode);
  const screen = document.querySelector(`[data-screen="${screenName}"]`);
  const h1 = screen && screen.querySelector('h1');
  $('navTitle').textContent = home ? '' : (previewMode ? 'Anteprima' : (h1 ? h1.textContent.trim() : stepTitle(screenName)));
  const req = currentRequest();
  const opp = selectedTeam ? displayTeamName(selectedTeam.name) : '';
  $('navSub').textContent = home || !req ? '' : (LIVE ? '' : req.title + (opp ? ` · ${opp}` : ''));
  const back = $('backButton');
  $('closeWorkflowButton').hidden = !home;
  $('navBack').hidden = home || LIVE && !previewMode && flowIndex === 0;
  $('navBack').disabled = back.disabled;
  $('navBackText').textContent = !home && !previewMode && flowIndex === 0 && !LIVE ? 'Home' : '';
  const next = $('nextButton');
  const busyLabel = /…/.test(next.textContent) ? next.textContent.replace(/[›✓]/g, '').trim() : '';
  $('navDone').hidden = home || !!previewMode || NAV_AUTO.has(screenName);
  $('navDone').disabled = next.disabled;
  // Ultimo passaggio: niente "Fine" in alto, tasto giallo "Anteprima" in basso (come "Invia").
  const lastStep = !home && !previewMode && isLastStep() && !NAV_AUTO.has(screenName);
  document.body.classList.toggle('last-step', lastStep);
  if (lastStep) $('navDone').hidden = true;
  $('navDone').textContent = busyLabel || 'Fine';
  document.querySelectorAll('textarea.field-input').forEach(el => { if (el.offsetParent) fitTextarea(el); });
  document.querySelectorAll('#navTools .nav-tools-g').forEach(g => g.classList.toggle('on', g.dataset.for === screenName && !home));
}

// I campi di testo lunghi si allungano col contenuto (anche quando il testo arriva da Gazzetta/Sky o dal sito).
function fitTextarea(el) {
  el.style.height = 'auto';                                   // nascosto: resta l'altezza minima
  if (el.offsetParent) el.style.height = el.scrollHeight + 2 + 'px';
}
function initTextareas() {
  document.querySelectorAll('textarea.field-input').forEach(el => {
    el.addEventListener('input', () => fitTextarea(el));
    const desc = Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype, 'value');
    Object.defineProperty(el, 'value', {get() { return desc.get.call(this); },
      set(v) { desc.set.call(this, v); requestAnimationFrame(() => fitTextarea(el)); }});
  });
}

function initNav() {
  initTextareas();
  document.querySelectorAll('.ios-in[type=date], .ios-in[type=time]').forEach(el =>
    el.addEventListener('click', () => { try { el.showPicker(); } catch (_) {} }));
  // Icone e tasti in alto delle schermate (A mano, Scegli foto, Modifica, Svuota…) vanno nella barra.
  document.querySelectorAll('[data-screen] .photo-head, [data-screen] .cal-head').forEach(head => {
    const group = document.createElement('span');
    group.className = 'nav-tools-g';
    group.dataset.for = head.closest('[data-screen]').dataset.screen;
    [...head.children].filter(el => el.tagName !== 'H1' && !el.classList.contains('eyebrow')).forEach(el => group.appendChild(el));
    if (group.children.length) $('navTools').appendChild(group);
  });
  $('navBack').addEventListener('click', () => $('backButton').click());
  $('navDone').addEventListener('click', () => $('nextButton').click());
  const watch = new MutationObserver(syncNav);
  ['nextButton', 'backButton'].forEach(id => watch.observe($(id), {attributes:true, childList:true, characterData:true, subtree:true}));
  syncNav();
}

/* ---------- Impostazioni › Squadre e loghi ---------- */
// Correzioni salvate dal servizio nel repo degli asset (team_overrides/): valgono anche per LiveScore.
// Ogni squadra del catalogo porta: override_key/override (correzioni), aliases_fclogo (nomi originali),
// display_name (nome scelto), logo_custom + logo_fclogo (logo caricato e originale), manual (squadra nuova).
let espnTeams = [];
let espnTeamsJob = null;
let setEdit = null;     // stato del pannello aperto
let setToastTimer = 0;

function setToast(text, warn=false) {
  const el = $('setToast');
  el.textContent = text;
  el.classList.toggle('warn', warn);
  el.classList.add('show');
  clearTimeout(setToastTimer);
  setToastTimer = setTimeout(() => el.classList.remove('show'), warn ? 6000 : 2400);
}

async function loadEspnTeams() {
  if (LIVE || !directBase || !session || espnTeams.length || espnTeamsJob) return espnTeamsJob;
  espnTeamsJob = netFetch(`${directBase}/espnteams?session=${encodeURIComponent(session)}`, {}, 20000)
    .then(r => r.json()).then(body => { if (body && body.ok) espnTeams = body.teams || []; })
    .catch(() => {}).finally(() => {
      espnTeamsJob = null;
      if ($('setOv').classList.contains('open')) { renderSetList(); markSetSeen(); } else updateSetBadge();
    });
  return espnTeamsJob;
}

// Nomi ESPN del calendario Juventus che non portano a nessuna squadra (niente logo).
const unmatchedEspn = () => teamsLoaded ? espnTeams.filter(t => !findTeamByName(t.name)) : [];

// Numerino della ⚙: solo le squadre senza logo mai viste. Aprendo le Impostazioni diventano "viste"
// (ricordate su questo telefono); la lista "Da sistemare" le mostra comunque tutte.
const SET_SEEN_KEY = 'imagegen.settings.seen';
function setSeen() {
  try { return new Set(JSON.parse(localStorage.getItem(SET_SEEN_KEY) || '[]')); } catch (_) { return new Set(); }
}
function markSetSeen() {
  const seen = setSeen();
  unmatchedEspn().forEach(x => seen.add(norm(x.name)));
  try { localStorage.setItem(SET_SEEN_KEY, JSON.stringify([...seen].slice(-300))); } catch (_) {}
  updateSetBadge();
}

function updateSetBadge() {
  const seen = setSeen();
  const n = unmatchedEspn().filter(x => !seen.has(norm(x.name))).length;
  const b = $('setBadge');
  b.hidden = !n;
  b.textContent = n > 9 ? '9+' : String(n);
}

function openSettings() {
  haptic('select');
  $('setQ').value = '';
  loadTeamNames();
  $('setOv').classList.add('open');
  renderSetList();
  markSetSeen();
  loadEspnTeams();
}
const closeSettings = () => { closeSetSheet(); $('setOv').classList.remove('open'); };

// Riga dell'elenco: logo (o cerchio vuoto per i nomi ESPN senza squadra), nome e una riga grigia.
function setRow(team, title, sub) {
  const b = document.createElement('button');
  b.type = 'button';
  b.className = 'set-row';
  b.innerHTML = `${team ? '<span class="logo"></span>' : '<span class="set-ph"></span>'}<div><div class="t"></div><div class="s"></div></div><span class="chev">›</span>`;
  if (team) fillLogo(b.querySelector('.logo'), team);
  b.querySelector('.t').textContent = title;
  b.querySelector('.s').textContent = sub;
  return b;
}

const customAliases = team => (team.override && team.override.aliases) || [];
// Cosa hai cambiato, in una riga: "Logo · Nome · 1 nome ESPN".
function changesText(team) {
  if (team.manual) return 'Aggiunta da te';
  const n = customAliases(team).length;
  return [team.logo_custom ? 'Logo' : '', team.display_name ? 'Nome' : '', team.override && team.override.tag ? 'Hashtag' : '',
    n ? `${n} nome ESPN${n > 1 ? ' in più' : ''}` : '']
    .filter(Boolean).join(' · ');
}

// Senza ricerca: solo "Da sistemare" e "Modificate" (se ci sono). Con la ricerca: tutto.
function renderSetList() {
  const box = $('setList');
  box.innerHTML = '';
  const q = $('setQ').value;
  const qn = norm(q);
  const grp = text => { const d = document.createElement('div'); d.className = 'set-grp'; d.textContent = text; box.appendChild(d); };
  const empty = text => { const d = document.createElement('div'); d.className = 'set-empty'; d.textContent = text; box.appendChild(d); };
  const missing = unmatchedEspn().filter(x => !qn || norm(x.name).includes(qn));
  const modified = teams.filter(x => x.override_key);
  const addMissing = () => missing.forEach(x => {
    const r = setRow(null, x.name, 'Senza logo · nome ESPN');
    r.addEventListener('click', () => openFixSheet(x.name));
    box.appendChild(r);
  });
  // Squadre senza logo (solo nome e hashtag di LiveScore): si trovano solo cercando.
  const noLogo = () => (teamNames || []).filter(r => !findTeamByName(r.espn));
  const addNames = list => list.forEach(r => box.appendChild(nmRow(r)));
  const addTeams = list => list.forEach(team => {
    const r = setRow(team, displayTeamName(team.name), team.override_key ? changesText(team) : (customAliases(team)[0] || ''));
    r.addEventListener('click', () => openTeamSheet(team));
    box.appendChild(r);
  });
  if (qn) {
    const found = searchTeams(teams, q);
    const names = noLogo().filter(r => [r.espn, r.name, r.tag].some(v => norm(v).includes(qn))).slice(0, 40);
    if (missing.length) { grp('Da sistemare'); addMissing(); }
    if (found.length) { grp('Squadre'); addTeams(found); }
    if (names.length) { grp('Senza logo'); addNames(names); }
    if (!missing.length && !found.length && !names.length) {
      empty(teamNamesJob ? 'Cerco…' : 'Nessuna squadra trovata.');
      if (!teamNamesJob) {
        const b = setRow(null, `Aggiungi “${q.trim()}”`, 'Nome ESPN nuovo: nome mostrato e hashtag');
        b.classList.add('nm');
        b.addEventListener('click', () => openNameSheet(null, q.trim()));
        box.appendChild(b);
      }
    }
    return;
  }
  const namesMine = noLogo().filter(r => r.custom);
  const emo = setRow(null, 'Emoji squadre', 'Emoji degli avversari nel testo del Matchday');
  emo.classList.add('emo-entry');
  emo.querySelector('.set-ph').outerHTML = '<span class="emo-th emo-vs" style="width:36px;height:36px;font-size:22px">🆚</span>';
  emo.addEventListener('click', openEmoji);
  box.appendChild(emo);
  if (missing.length) { grp('Da sistemare'); addMissing(); }
  else if (espnTeamsJob) empty('Controllo il calendario ESPN…');
  if (modified.length || namesMine.length) { grp('Modificate'); addTeams(modified); addNames(namesMine); }
  if (!missing.length && !modified.length && !namesMine.length && !espnTeamsJob)
    empty('Tutto a posto. Cerca una squadra per cambiarne logo, nome o hashtag.');
}

/* --- pannello: modifica squadra --- */

/* --- pannello: nome ESPN senza squadra --- */


// Logo mostrato ora nel pannello: caricato (anteprima), originale fclogo (dopo "Torna a fclogo") o attuale.

// Posizione dello stemma nel quadrato (percentuali): frame = {x, y, s} come nel servizio.
function frameStyle(frame, aspect) {
  const f = frame || {x:0, y:0, s:1};
  const w = aspect >= 1 ? f.s : f.s * aspect, h = aspect >= 1 ? f.s / aspect : f.s;
  return `left:${(50 + (f.x - w / 2) * 100).toFixed(2)}%;top:${(50 + (f.y - h / 2) * 100).toFixed(2)}%;width:${(w * 100).toFixed(2)}%;height:${(h * 100).toFixed(2)}%`;
}

// Blocco logo: riquadro 1:1 come i PNG fclogo, che è anche l'editor (si trascina quando c'è un logo
// nuovo o "Sposta" su quello salvato) + una riga di icone: carica, cerca su fclogo, link, usa.

function bindEditor(e) {
  const box = $('setEdBox');
  if (!box) return;
  const img = $('setEdImg');
  const paint = () => {
    img.setAttribute('style', `--m:url('${e.preview}');${frameStyle(e.frame, e.aspect)}`);
    $('setEdV').classList.toggle('on', e.frame.x === 0);
    $('setEdH').classList.toggle('on', e.frame.y === 0);
  };
  const snap = v => Math.abs(v) < 0.012 ? 0 : Math.max(-0.5, Math.min(0.5, v));
  const pts = new Map();
  let start = null;
  const begin = () => {
    const p = [...pts.values()];
    start = {x:e.frame.x, y:e.frame.y, s:e.frame.s, cx:p.reduce((a, q) => a + q.x, 0) / p.length, cy:p.reduce((a, q) => a + q.y, 0) / p.length,
             d:p.length > 1 ? Math.hypot(p[0].x - p[1].x, p[0].y - p[1].y) : 0};
  };
  box.addEventListener('pointerdown', ev => { if (ev.target.closest('.set-ed-c')) return; try { box.setPointerCapture(ev.pointerId); } catch (_) {} pts.set(ev.pointerId, {x:ev.clientX, y:ev.clientY}); begin(); });
  box.addEventListener('pointermove', ev => {
    if (!pts.has(ev.pointerId) || !start) return;
    pts.set(ev.pointerId, {x:ev.clientX, y:ev.clientY});
    const p = [...pts.values()], size = box.getBoundingClientRect().width;
    const cx = p.reduce((a, q) => a + q.x, 0) / p.length, cy = p.reduce((a, q) => a + q.y, 0) / p.length;
    e.frame.x = snap(start.x + (cx - start.cx) / size);
    e.frame.y = snap(start.y + (cy - start.cy) / size);
    if (p.length > 1 && start.d) e.frame.s = Math.max(0.3, Math.min(1.1, start.s * Math.hypot(p[0].x - p[1].x, p[0].y - p[1].y) / start.d));
    e.moved = true;
    paint();
  });
  const end = ev => { pts.delete(ev.pointerId); if (pts.size) begin(); else start = null; };
  box.addEventListener('pointerup', end);
  box.addEventListener('pointercancel', end);
  paint();
}





// Nome ESPN senza squadra: selettore piccolo "Nuova squadra | Già nel catalogo".


async function setPost(payload) {
  const r = await netFetch(`${directBase}/settings`, {
    method:'POST', headers:{'Content-Type':'application/json','X-ImageGEN-Session':session},
    body:JSON.stringify({v:1, session, ...payload})
  }, 45000);
  const body = await r.json().catch(() => ({}));
  if (!r.ok || !body.ok) throw new Error(body.error || 'Operazione non riuscita.');
  return body;
}

// Aggiorna l'elenco squadre con la riga rimandata dal servizio (o la toglie se la squadra nuova è stata eliminata).
function applySavedTeam(key, row) {
  const same = t => (key && t.override_key === key) || (row && !row.manual && norm(t.name) === norm(row.name));
  const i = teams.findIndex(same);
  if (row) { if (i >= 0) teams[i] = row; else teams.push(row); }
  else if (i >= 0) teams.splice(i, 1);
  resolveTeamAliases();
  saveCatalogCache();
  updateSetBadge();
  if (selectedTeam && row && norm(selectedTeam.name) === norm(row.name)) selectedTeam = row;
}



/* --- Squadre e loghi: pagine una dentro l'altra (stile Impostazioni Apple) ---
   Pila di pagine sopra l'elenco: team → logo / name / espn; fix → new (→ logo/name/espn) / link.
   Ogni pagina con "Salva" salva subito sul servizio; la squadra nuova si crea con "Crea squadra". */
let setStack = [];      // pagine aperte, l'ultima è quella visibile
let setTeam = null;     // squadra aperta (o bozza della squadra nuova)
let setDraft = null;    // modifiche della pagina Logo / Nome / Nomi ESPN aperta
let setBusy = false;

const SP_ICONS = {
  phone:'<rect x="3" y="3" width="18" height="18" rx="3"/><circle cx="8.5" cy="8.5" r="1.5"/><path d="M21 15l-5-5L5 21"/>',
  search:'<circle cx="11" cy="11" r="7"/><path d="M20 20l-3.5-3.5"/>',
  undo:'<path d="M9 14 4 9l5-5"/><path d="M4 9h10.5a5.5 5.5 0 0 1 0 11H11"/>',
  link:'<path d="M10 13a5 5 0 0 0 7.07 0l3-3a5 5 0 0 0-7.07-7.07l-1.5 1.5"/><path d="M14 11a5 5 0 0 0-7.07 0l-3 3a5 5 0 0 0 7.07 7.07l1.5-1.5"/>',
  lock:'<rect x="5" y="11" width="14" height="10" rx="2"/><path d="M8 11V7a4 4 0 0 1 8 0v4"/>',
  plus:'<path d="M12 5v14M5 12h14"/>',
  target:'<circle cx="12" cy="12" r="8"/><circle cx="12" cy="12" r="2.5"/><path d="M12 1v4M12 19v4M1 12h4M19 12h4"/>',
  move:'<path d="M12 2v20M2 12h20M12 2l-3 3M12 2l3 3M12 22l-3-3M12 22l3-3M2 12l3-3M2 12l3 3M22 12l-3-3M22 12l-3 3"/>',
  chev:'<path d="M15 5l-7 7 7 7"/>'
};
const spIco = (name, size=24) => `<svg width="${size}" height="${size}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${SP_ICONS[name]}</svg>`;
function setEsc(text) { const d = document.createElement('div'); d.textContent = String(text ?? ''); return d.innerHTML; }

// Stato della squadra aperta, ricavato dalla riga del catalogo (con le correzioni già applicate).
function teamState(team) {
  return {
    team, isNew:false, manual:!!team.manual, key:team.override_key || '', base:team.manual ? null : team.name,
    custom:team.display_name || '', nameOrig:team.manual ? team.name : baseDisplayName(team.name),
    locked:team.manual ? [] : [...new Set([team.name, ...(team.aliases_fclogo || team.aliases || [])])],
    aliases:customAliases(team).slice(), hasCustom:!!team.logo_custom,
    tag:(team.override && team.override.tag) || '', tagOrig:baseTagOf(team),
    current:team.logo || '', fclogo:team.logo_custom ? (team.logo_fclogo || '') : (team.manual ? '' : (team.logo || ''))
  };
}
const setShownName = T => T.isNew ? T.custom || T.espn : (T.custom || T.nameOrig);

function openTeamSheet(team) {
  haptic('select');
  setTeam = teamState(team);
  setStack = ['team'];
  renderSetPage();
  // Il pacchetto ha solo miniature: logo nitido dal servizio.
  const T = setTeam;
  setPost({action:'logo_current', name:team.name}).then(r => {
    if (setTeam !== T) return;
    if (r.current) T.current = r.current;
    if (r.fclogo) T.fclogo = r.fclogo;
    renderSetPage();
  }).catch(() => {});
}

function openFixSheet(espnName) {
  haptic('select');
  setTeam = {espn:espnName};
  setStack = ['fix'];
  renderSetPage();
}

function closeSetSheet() {
  setStack = []; setTeam = null; setDraft = null;
  $('setPage').hidden = true;
  $('setPage').innerHTML = '';
}

function spPush(page) {
  haptic('select');
  const T = setTeam;
  if (page === 'logo') setDraft = {logo:'keep', preview:'', aspect:1, frame:null, repos:false, moved:false,
    ...(T.isNew && T.pending ? {logo:T.pending.logo, preview:T.pending.preview, aspect:T.pending.aspect, frame:{...T.pending.frame}} : {})};
  if (page === 'name') setDraft = {name:setShownName(T)};
  if (page === 'tag') setDraft = {tag:T.tag || ''};
  if (page === 'espn') setDraft = {aliases:T.aliases.slice(), adding:false};
  if (page === 'link') setDraft = {q:''};
  setStack.push(page);
  renderSetPage();
}
function spPop() {
  setStack.pop();
  setDraft = null;
  if (!setStack.length) { closeSetSheet(); renderSetList(); return; }
  renderSetPage();
}

function spNav(title, {save=false, cancel=false, saveLabel='Salva', saveOff=false}={}) {
  const left = cancel ? '<button type="button" class="sp-l" data-sp="back">Annulla</button>'
    : `<button type="button" class="sp-l sp-back" data-sp="back">${spIco('chev', 22)}<span>Indietro</span></button>`;
  const right = save ? `<button type="button" class="sp-r" data-sp="save" ${saveOff || setBusy ? 'disabled' : ''}>${setBusy ? '…' : saveLabel}</button>` : '<span></span>';
  return `<div class="sp-nav">${left}<b>${setEsc(title)}</b>${right}</div>`;
}
const spRow = (label, value, page, warn=false) =>
  `<button type="button" class="sp-item" data-go="${page}"><span>${label}</span><span class="sp-v${warn ? ' warn' : ''}">${value}</span><span class="sp-chev">›</span></button>`;
const spLogo = (uri, size) => uri
  ? `<span class="sp-logo" style="width:${size}px;height:${size}px;--m:url('${uri}')"></span>`
  : `<span class="sp-ph" style="width:${size}px;height:${size}px"></span>`;

function renderSetPage() {
  const page = setStack[setStack.length - 1];
  const box = $('setPage');
  if (!page) { box.hidden = true; return; }
  box.hidden = false;
  if (page.startsWith('emo')) { emoRender(page); return; }
  const T = setTeam, D = setDraft;
  let html = '';
  if (page === 'team' || page === 'new') {
    const isNew = page === 'new';
    const logo = isNew ? (T.pending ? T.pending.preview : '') : T.current;
    const nEspn = isNew ? T.aliases.length : T.locked.length + T.aliases.length;
    const sub = isNew ? (T.pending ? 'Pronta da creare' : 'Manca solo il logo')
      : T.manual ? 'Aggiunta da te' : (T.key ? 'Modificata da te' : 'Dal catalogo fclogo');
    html = spNav(isNew ? 'Nuova squadra' : '') + `<div class="sp-body">
      <div class="sp-hero">${isNew && T.pending ? `<span class="sp-sq">${frameLogo(T.pending)}</span>` : spLogo(logo, 92)}<h2>${setEsc(setShownName(T))}</h2><p>${sub}</p></div>
      <div class="sp-list">
        ${spRow('Logo', isNew ? (T.pending ? 'Pronto' : 'Da aggiungere') : (T.hasCustom ? 'Tuo' : 'fclogo'), 'logo', isNew && !T.pending)}
        ${spRow('Nome', setEsc(setShownName(T)), 'name')}
        ${spRow('Hashtag', '#' + setEsc(T.tag || T.tagOrig || ''), 'tag')}
        ${spRow('Nomi ESPN', String(nEspn), 'espn')}
      </div>
      ${isNew ? `<button type="button" class="sp-cta" data-sp="create" ${T.pending && !setBusy ? '' : 'disabled'}>${setBusy ? 'Creo…' : 'Crea squadra'}</button>`
        : T.key ? `<button type="button" class="sp-danger" data-sp="reset">${T.confirmReset ? 'Tocca di nuovo per confermare' : T.manual ? 'Elimina questa squadra' : 'Cancella tutte le personalizzazioni'}</button>` : ''}
      <div id="setErr" class="sp-err"></div></div>`;
  } else if (page === 'logo') {
    const live = !!D.preview;
    const uri = live ? D.preview : (D.logo === null ? T.fclogo : (T.isNew ? '' : T.current));
    const canOrig = !T.isNew && (T.hasCustom || live) && !!T.fclogo;
    const guides = live ? '<div class="set-ed-g safe"></div><div class="set-ed-g v" id="setEdV"></div><div class="set-ed-g h" id="setEdH"></div>' : '';
    const inner = uri ? `<i id="setEdImg" style="--m:url('${uri}');${frameStyle(live ? D.frame : null, live ? D.aspect : 1)}"></i>` : '';
    const corner = live ? `<button type="button" class="set-ed-c" data-sp="center" aria-label="Centra come fclogo">${spIco('target', 20)}</button>`
      : (!T.isNew && T.hasCustom && D.logo !== null ? `<button type="button" class="set-ed-c" data-sp="move" aria-label="Sposta logo">${spIco('move', 20)}</button>` : '');
    const changed = live || (D.logo === null && T.hasCustom);
    html = spNav('Logo', {save:true, cancel:true, saveLabel:T.isNew ? 'Fine' : 'Salva', saveOff:!changed}) + `<div class="sp-body sp-logo-page">
      <div class="sp-stage"><div class="set-ed-box sp-ed${live ? ' live' : ''}${uri ? '' : ' empty'}" id="setEdBox"${uri ? '' : ' data-sp="phone"'}>${guides}${inner}${uri ? '' : `<span class="set-ed-empty">${spIco('phone', 28)}Carica il logo</span>`}${corner}</div></div>
      <p class="sp-hint">${live ? 'Trascina per spostare · due dita per la dimensione' : '&nbsp;'}</p>
      <div class="sp-tiles${canOrig ? '' : ' two'}"><button type="button" class="sp-tile" data-sp="phone">${spIco('phone')}Telefono</button>
        <button type="button" class="sp-tile" data-sp="fcl-open">${spIco('search')}Cerca fclogo</button>
        ${canOrig ? `<button type="button" class="sp-tile" data-sp="orig">${spIco('undo')}Originale</button>` : ''}</div>
      <label class="sp-link">${spIco('link', 20)}<input id="setFcl" type="url" inputmode="url" placeholder="Incolla link fclogo.top" autocomplete="off" spellcheck="false"><button type="button" data-sp="fcl-use">Usa</button></label>
      <div id="setErr" class="sp-err"></div></div>`;
  } else if (page === 'name') {
    const orig = T.isNew ? T.espn : T.nameOrig;
    html = spNav('Nome', {save:true, cancel:true, saveLabel:T.isNew ? 'Fine' : 'Salva'}) + `<div class="sp-body">
      <div class="sp-lbl">Nome mostrato</div>
      <div class="sp-list"><input id="spName" class="sp-field" type="text" maxlength="40" autocomplete="off" autocapitalize="words" spellcheck="false" value="${setEsc(D.name)}" placeholder="${setEsc(orig)}"></div>
      ${T.isNew ? '' : `<p class="sp-note">Originale: <b>${setEsc(orig)}</b></p>
      <div class="sp-list"><button type="button" class="sp-item sp-act" data-sp="name-orig">Ripristina originale</button></div>`}
      <p class="sp-note sp-bottom">Vale per la mini app, le grafiche e LiveScore.</p>
      <div id="setErr" class="sp-err"></div></div>`;
  } else if (page === 'tag') {
    html = spNav('Hashtag', {save:true, cancel:true, saveLabel:T.isNew ? 'Fine' : 'Salva'}) + `<div class="sp-body">
      <div class="sp-lbl">Hashtag</div>
      <div class="sp-list"><label class="sp-item"><span>#</span><input id="spTag" class="sp-field sp-inline" type="text" maxlength="30" autocomplete="off" autocapitalize="off" spellcheck="false" value="${setEsc(D.tag)}" placeholder="${setEsc(T.tagOrig || '')}"></label></div>
      ${T.tagOrig ? `<p class="sp-note">Originale: <b>#${setEsc(T.tagOrig)}</b>. Campo vuoto = originale.</p>` : ''}
      <p class="sp-note sp-bottom">Nei messaggi di LiveScore, es. #Juve${setEsc(D.tag || T.tagOrig || '')}.</p>
      <div id="setErr" class="sp-err"></div></div>`;
  } else if (page === 'espn') {
    html = spNav('Nomi ESPN', {save:true, cancel:true, saveLabel:T.isNew ? 'Fine' : 'Salva'}) + `<div class="sp-body">
      ${T.locked && T.locked.length ? `<div class="sp-lbl">Dal catalogo</div><div class="sp-list">${T.locked.map(a => `<div class="sp-item"><span>${setEsc(a)}</span><span class="sp-v">${spIco('lock', 16)}</span></div>`).join('')}</div>` : ''}
      <div class="sp-lbl">Aggiunti da te</div>
      <div class="sp-list">${D.aliases.map((a, i) => `<div class="sp-item"><span>${setEsc(a)}</span><button type="button" class="sp-rm" data-sp="rm" data-i="${i}" aria-label="Togli ${setEsc(a)}">−</button></div>`).join('')}
        ${D.adding ? `<div class="sp-item"><input id="spAlias" class="sp-field sp-inline" type="text" maxlength="40" placeholder="Nome come lo scrive ESPN" autocomplete="off" spellcheck="false" list="spAliasList"><button type="button" class="sp-add-ok" data-sp="add-ok">Aggiungi</button></div>
          <datalist id="spAliasList">${unmatchedEspn().map(x => `<option value="${setEsc(x.name)}">`).join('')}</datalist>`
          : `<button type="button" class="sp-item sp-act" data-sp="add">Aggiungi nome</button>`}</div>
      <p class="sp-note">Se ESPN scrive la squadra con uno di questi nomi, si usano questo logo e questo nome.</p>
      <div id="setErr" class="sp-err"></div></div>`;
  } else if (page === 'nm') {
    box.innerHTML = nmPage();
    ['nmEspn', 'nmName', 'nmTag'].forEach(id => { const el = $(id); if (el) el.addEventListener('input', () => { D[id.slice(2).toLowerCase()] = el.value; }); });
    return;
  } else if (page === 'fix') {
    html = spNav('') + `<div class="sp-body">
      <div class="sp-hero">${spLogo('', 92)}<h2>${setEsc(T.espn)}</h2><p>Nel calendario ESPN, senza logo</p></div>
      <div class="sp-list">
        <button type="button" class="sp-item sp-big" data-sp="to-new"><span class="sp-ic">${spIco('plus', 22)}</span><span class="sp-two">Crea squadra nuova<small>Logo e nome tuoi</small></span><span class="sp-chev">›</span></button>
        <button type="button" class="sp-item sp-big" data-go="link"><span class="sp-ic">${spIco('link', 22)}</span><span class="sp-two">È già nel catalogo<small>Collegala a una squadra esistente</small></span><span class="sp-chev">›</span></button>
      </div></div>`;
  } else if (page === 'link') {
    const found = norm(D.q) ? searchTeams(teams, D.q).slice(0, 8) : [];
    html = spNav(`Collega ${T.espn}`) + `<div class="sp-body">
      <label class="sp-search">${spIco('search', 20)}<input id="spLinkQ" type="text" placeholder="Cerca la squadra" autocomplete="off" autocapitalize="words" spellcheck="false" value="${setEsc(D.q)}"></label>
      ${found.length ? `<div class="sp-list" id="spLinkList"></div>` : ''}
      <p class="sp-note">Tocca la squadra: d’ora in poi “${setEsc(T.espn)}” di ESPN userà il suo logo e il suo nome.</p>
      <div id="setErr" class="sp-err"></div></div>`;
    box.innerHTML = html;
    const list = $('spLinkList');
    found.forEach(team => {
      const b = document.createElement('button');
      b.type = 'button'; b.className = 'sp-item';
      b.innerHTML = '<span class="logo"></span><span></span><span class="sp-chev">›</span>';
      b.children[1].textContent = displayTeamName(team.name);
      fillLogo(b.firstChild, team);
      b.addEventListener('click', () => spLink(team));
      list.appendChild(b);
    });
    const q = $('spLinkQ');
    q.addEventListener('input', () => { D.q = q.value; const pos = q.selectionStart; renderSetPage(); const n = $('spLinkQ'); n.focus(); n.setSelectionRange(pos, pos); });
    return;
  }
  box.innerHTML = html;
  if (page === 'logo') {
    if (D.preview) bindEditor(D);
    const input = $('setFcl');
    input.addEventListener('paste', () => setTimeout(() => { if (/fclogo\.top\//i.test(input.value)) spUseFclogo(); }, 0));
    input.addEventListener('keydown', ev => { if (ev.key === 'Enter') { ev.preventDefault(); spUseFclogo(); } });
  }
  if (page === 'name') $('spName').addEventListener('input', ev => { D.name = ev.target.value; });
  if (page === 'tag') $('spTag').addEventListener('input', ev => { D.tag = ev.target.value.replace(/^#+/, ''); });
  if (page === 'espn' && D.adding) setTimeout(() => $('spAlias') && $('spAlias').focus(), 30);
}

// Anteprima dello stemma posizionato (bozza della squadra nuova): stesso calcolo del servizio.
function frameLogo(p) {
  return `<i style="--m:url('${p.preview}');${frameStyle(p.frame, p.aspect)}"></i>`;
}

// Salva la squadra aperta cambiando solo `change` (logo, nome o nomi ESPN).
async function spSave(change) {
  const T = setTeam;
  const team = {base:T.base, key:T.key, name:T.custom, aliases:T.aliases, logo:'keep', ...change};
  setBusy = true; renderSetPage();
  try {
    const body = await setPost({action:'team_save', team});
    applySavedTeam(body.key, body.team);
    setBusy = false;
    haptic('success');
    if (body.remote) setToast(change.reset ? 'Personalizzazioni cancellate.' : 'Salvato.');
    else setToast(`Salvato solo per questa sessione: ${body.warning || 'GitHub non raggiungibile'}.`, true);
    return body;
  } catch (ex) {
    setBusy = false; renderSetPage();
    if ($('setErr')) $('setErr').textContent = ex.message || String(ex);
    haptic('error');
    return null;
  }
}

// Dopo un salvataggio: la pagina Squadra mostra la riga aggiornata (o si torna all'elenco se tolta).
function spAfterSave(body) {
  const row = body && body.team;
  if (!row) { closeSetSheet(); renderSetList(); return; }
  const current = setTeam.current;
  setTeam = teamState(row);
  if (!row.logo_custom || !current) setTeam.current = row.logo || current;
  setStack = ['team'];
  setDraft = null;
  renderSetPage();
  renderSetList();
  const T = setTeam;
  setPost({action:'logo_current', name:row.name}).then(r => {
    if (setTeam !== T) return;
    if (r.current) T.current = r.current;
    if (r.fclogo) T.fclogo = r.fclogo;
    renderSetPage();
  }).catch(() => {});
}

async function spLink(team) {
  const T = setTeam;
  haptic('select');
  setTeam = teamState(team);
  setTeam.espn = T.espn;
  const body = await spSave({aliases:[...customAliases(team), T.espn]});
  if (body) { closeSetSheet(); renderSetList(); setToast(`${T.espn} → ${displayTeamName(team.name)}`); }
  else { setTeam = T; renderSetPage(); }
}

async function spLogoFrom(payload) {
  const D = setDraft;
  $('setErr').textContent = payload.fclogo ? 'Prendo il logo da fclogo.top…' : 'Carico il logo…';
  try {
    const prev = await setPost({action:'logo_preview', ...payload});
    if (setDraft !== D) return;
    Object.assign(D, {preview:prev.preview, aspect:prev.aspect || 1, frame:prev.frame || {x:0, y:0, s:0.88},
      logo:prev.photo_id ? `upload:${prev.photo_id}` : D.logo, repos:!!payload.key, moved:false});
    haptic('success');
    renderSetPage();
  } catch (ex) {
    if ($('setErr')) $('setErr').textContent = ex.message || String(ex);
    haptic('error');
  }
}
function spUseFclogo() {
  const link = String(($('setFcl') || {}).value || '').trim();
  if (link) spLogoFrom({fclogo:link});
}
async function spUpload(file) {
  if (!file || !setDraft) return;
  try {
    if (file.size > 8 * 1024 * 1024) throw new Error('Logo troppo grande (max 8 MB).');
    $('setErr').textContent = 'Carico il logo…';
    const up = await netFetch(`${directBase}/upload`, {method:'POST', headers:{'Content-Type':file.type || 'image/png','X-ImageGEN-Session':session}, body:file}, 30000);
    const upBody = await up.json().catch(() => ({}));
    if (!up.ok || !upBody.ok) throw new Error(upBody.error || 'Caricamento non riuscito.');
    await spLogoFrom({photo_id:upBody.photo_id});
  } catch (ex) {
    if ($('setErr')) $('setErr').textContent = ex.message || String(ex);
    haptic('error');
  }
}

async function spOnSave() {
  const page = setStack[setStack.length - 1], T = setTeam, D = setDraft;
  if (page === 'nm') { nmSave(false); return; }
  if (page === 'logo') {
    if (T.isNew) {      // bozza: il logo si salva con "Crea squadra"
      if (D.preview) T.pending = {logo:D.logo, preview:D.preview, aspect:D.aspect, frame:{...D.frame}};
      spPop(); return;
    }
    const change = D.logo === null ? {logo:null} : {logo:D.logo, ...(D.frame && (D.repos || String(D.logo).startsWith('upload:')) ? {logo_frame:D.frame} : {})};
    spAfterSave(await spSave(change));
  } else if (page === 'name') {
    const name = String(D.name || '').trim();
    if (T.isNew) { T.custom = name || T.espn; spPop(); return; }
    spAfterSave(await spSave({name:norm(name) === norm(T.nameOrig) ? '' : name}));
  } else if (page === 'tag') {
    if (T.isNew) { T.tag = D.tag; spPop(); return; }
    spAfterSave(await spSave({tag:D.tag}));
  } else if (page === 'espn') {
    if (T.isNew) { T.aliases = D.aliases.slice(); spPop(); return; }
    spAfterSave(await spSave({aliases:D.aliases}));
  }
}

function initSettings() {
  $('setBtn').addEventListener('click', openSettings);
  $('setBack').addEventListener('click', closeSettings);
  $('setQ').addEventListener('input', renderSetList);
  $('setFile').addEventListener('change', () => { const f = $('setFile').files[0]; $('setFile').value = ''; spUpload(f); });
  $('setPage').addEventListener('click', async ev => {
    const go = ev.target.closest('[data-go]');
    if (go) { spPush(go.dataset.go); return; }
    const btn = ev.target.closest('[data-sp]');
    if (!btn || btn.disabled) return;
    const act = btn.dataset.sp, T = setTeam, D = setDraft;
    if (act !== 'reset' && T && T.confirmReset) T.confirmReset = false;
    if (act === 'back') spPop();
    else if (act === 'save') spOnSave();
    else if (act === 'phone') $('setFile').click();
    else if (act === 'fcl-open') { const url = 'https://fclogo.top/'; if (tg && tg.openLink) tg.openLink(url); else window.open(url, '_blank', 'noopener'); }
    else if (act === 'fcl-use') spUseFclogo();
    else if (act === 'orig') { D.preview = ''; D.repos = false; D.logo = T.hasCustom ? null : 'keep'; renderSetPage(); }
    else if (act === 'center') { D.frame = {x:0, y:0, s:0.88}; D.moved = true; renderSetPage(); }
    else if (act === 'move') spLogoFrom({key:T.key});
    else if (act === 'name-orig') { D.name = T.nameOrig; renderSetPage(); }
    else if (act === 'add') { D.adding = true; renderSetPage(); }
    else if (act === 'add-ok') {
      const v = String(($('spAlias') || {}).value || '').trim();
      if (v && ![...(T.locked || []), ...D.aliases].some(a => norm(a) === norm(v))) D.aliases.push(v);
      D.adding = false; renderSetPage();
    }
    else if (act === 'rm') { D.aliases.splice(Number(btn.dataset.i), 1); renderSetPage(); }
    else if (act === 'to-new') {
      setTeam = {isNew:true, espn:T.espn, custom:'', aliases:[T.espn], locked:[], pending:null, tag:'', tagOrig:baseTagOf({name:T.espn})};
      setStack = ['fix', 'new']; renderSetPage();
    }
    else if (act === 'create') {
      const p = T.pending;
      const body = await spSave({base:null, key:'', name:T.custom || T.espn, aliases:T.aliases, tag:T.tag || '', logo:p.logo, logo_frame:p.frame});
      if (body) spAfterSave(body);
    }
    else if (act === 'nm-logo') { openFixSheet(T.nm.espn); }
    else if (act === 'nm-reset') {
      if (!T.confirmReset) { T.confirmReset = true; renderSetPage(); return; }
      nmSave(true);
    }
    else if (act === 'reset') {
      if (!T.confirmReset) { T.confirmReset = true; renderSetPage(); return; }
      spAfterSave(await spSave({reset:true}));
    }
  });
  $('setPage').addEventListener('keydown', ev => {
    if (ev.key === 'Enter' && ev.target.id === 'spAlias') { ev.preventDefault(); $('setPage').querySelector('[data-sp="add-ok"]').click(); }
  });
}


/* ---------- Impostazioni › Squadre senza logo: nome mostrato e hashtag ----------
   Elenco di LiveScore (data/teams.json) con le modifiche salvate dal servizio in
   team_overrides/names.json (repo degli asset). Le squadre con logo tengono nome e hashtag
   nelle loro correzioni (overrides.json). Valgono per le grafiche e per i messaggi LiveScore. */

// Hashtag originale di una squadra con logo: quello di LiveScore per uno dei suoi nomi ESPN.
function baseTagOf(team) {
  const names = [team.name, ...(team.aliases_fclogo || team.aliases || [])].filter(Boolean).map(norm);
  const row = (teamNames || []).find(r => names.includes(norm(r.espn)));
  return row ? row.base_tag : String(displayTeamName(team.name) || team.name || '').replace(/\s+/g, '');
}
let teamNames = null, teamNamesJob = null;

function loadTeamNames(force = false) {
  if (!directBase || !session) return null;
  if ((teamNames && !force) || teamNamesJob) return teamNamesJob;
  teamNamesJob = setPost({action:'names_list'})
    .then(body => { teamNames = body.teams || []; })
    .catch(err => setToast(err.message || 'Nomi non caricati.', true))
    .finally(() => { teamNamesJob = null; if ($('setOv').classList.contains('open') && !setStack.length) renderSetList(); });
  return teamNamesJob;
}

function nmRow(row) {
  const r = setRow(null, row.name, `${row.espn} · #${row.tag}`);
  r.classList.add('nm');
  r.addEventListener('click', () => openNameSheet(row));
  return r;
}

function openNameSheet(row, espn = '') {
  haptic('select');
  setTeam = {nm:row, isNew:!row};
  // Campo vuoto = originale.
  setDraft = {espn:row ? row.espn : espn,
    name:row && row.custom && row.name !== row.base_name ? row.name : '',
    tag:row && row.custom && row.tag !== row.base_tag ? row.tag : ''};
  setStack = ['nm'];
  renderSetPage();
}

function nmPage() {
  const T = setTeam, D = setDraft, R = T.nm;
  const baseName = R ? R.base_name : (D.espn || 'Nome mostrato'), baseTag = R ? R.base_tag : 'Hashtag';
  return spNav(T.isNew ? 'Nuovo nome' : '', {save:true, cancel:true}) + `<div class="sp-body">
    ${T.isNew ? '' : `<div class="sp-hero"><h2>${setEsc(R.name)}</h2><p>#${setEsc(R.tag)}</p></div>`}
    <div class="sp-lbl">Nome ESPN</div>
    <div class="sp-list">${T.isNew
      ? `<input id="nmEspn" class="sp-field" type="text" maxlength="60" autocomplete="off" spellcheck="false" value="${setEsc(D.espn)}" placeholder="Come lo scrive ESPN">`
      : `<div class="sp-item"><span>${setEsc(R.espn)}</span><span class="sp-v">${spIco('lock', 16)}</span></div>`}</div>
    <div class="sp-lbl">Nome mostrato</div>
    <div class="sp-list"><input id="nmName" class="sp-field" type="text" maxlength="40" autocomplete="off" autocapitalize="words" spellcheck="false" value="${setEsc(D.name)}" placeholder="${setEsc(baseName)}"></div>
    <div class="sp-lbl">Hashtag</div>
    <div class="sp-list"><label class="sp-item"><span>#</span><input id="nmTag" class="sp-field sp-inline" type="text" maxlength="30" autocomplete="off" autocapitalize="off" spellcheck="false" value="${setEsc(D.tag)}" placeholder="${setEsc(baseTag)}"></label></div>
    ${R ? `<p class="sp-note">Originale: <b>${setEsc(R.base_name)}</b> · #${setEsc(R.base_tag)}. Campo vuoto = originale.</p>` : ''}
    ${R && !NO_LOGO_TEAMS.has(String(T.nm.espn || '').toLowerCase()) ? `<div class="sp-list"><button type="button" class="sp-item sp-act" data-sp="nm-logo">Aggiungi logo</button></div>` : ''}
    ${R && R.custom ? `<button type="button" class="sp-danger" data-sp="nm-reset">${T.confirmReset ? 'Tocca di nuovo per confermare' : R.added ? 'Elimina questo nome' : 'Ripristina originale'}</button>` : ''}
    <p class="sp-note sp-bottom">Vale per le grafiche e per i messaggi di LiveScore (dalla partita successiva se una è in corso).</p>
    <div id="setErr" class="sp-err"></div></div>`;
}

// Squadre senza stemma nelle grafiche: Juventus (le grafiche sono sue) e Italia (al posto dello stemma il nome).
const NO_LOGO_TEAMS = new Set(['juventus','italy']);

async function nmSave(reset) {
  const T = setTeam, D = setDraft;
  const team = reset ? {espn:T.nm.espn, reset:true}
    : {espn:T.isNew ? D.espn : T.nm.espn, name:D.name, tag:String(D.tag || '').replace(/^#+/, '')};
  if (!String(team.espn || '').trim()) { $('setErr').textContent = 'Scrivi il nome ESPN.'; return; }
  setBusy = true; renderSetPage();
  try {
    const body = await setPost({action:'name_save', team});
    setBusy = false;
    await loadTeamNames(true);
    closeSetSheet(); renderSetList();
    if (body.remote) setToast(reset ? 'Ripristinato' : 'Salvato'); else setToast(`Salvato solo per questa sessione (${body.warning})`, true);
  } catch (err) {
    setBusy = false; renderSetPage();
    $('setErr').textContent = err.message || 'Salvataggio non riuscito.';
  }
}
