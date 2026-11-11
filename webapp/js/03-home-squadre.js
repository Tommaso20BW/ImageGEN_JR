/* Mini App ImageGen JR. File caricati in ordine da index.html: l'ordine conta. */
/* ---------- Caricamento ---------- */
// HALF/END/FULL TIME: avanzamento reale letto da GET /progress (passi di render.py).
// Altre grafiche: avanzamento stimato sulla durata delle generazioni precedenti.
const STAGE_RANGE = {idle:[0,4], render:[2,10], cutout:[10,55], erase:[55,85], compose:[60,96]};
const STAGE_SUB = {
  cutout:'Scontorno la persona…',
  erase:'Cancello la persona dallo sfondo…',
  compose:'Compongo la grafica…'
};
const BUSY_SUB = {
  goal:'Compongo la grafica con foto e posa del giocatore.',
  table:'Scarico la classifica aggiornata da Diretta.it.',
  conv:'Compongo i convocati con bandiere e foto.',
  saved:'Compongo la grafica con foto e posa del portiere.',
  kick:'Preparo la grafica del calcio d’inizio.',
  second:'Preparo la grafica dell’inizio del secondo tempo.',
  half:'Avvio la generazione…',
  end_of_90:'Avvio la generazione…',
  full:'Avvio la generazione…',
  stats:'Preparo la tabella delle statistiche.'
};
const DEFAULT_MS = {ppcut:12000, goal:4000, saved:4000, kick:4000, second:4000, stats:7000, squad:6000, xi:8000, md:7000, jr:4000, igbn:4000, pxi:9000, cal:5000, table:35000, bracket:45000, conv:9000, half:6000, end_of_90:6000, full:6000, submit:2500};
const DURATIONS_KEY = 'imagegen-jr-durations';
const SLOW_SUB = 'Ci sta mettendo più del solito: attendi ancora qualche secondo.';
const RING_C = 2 * Math.PI * 42;
let busy = null;

function expectedMs(kind) {
  try {
    const saved = JSON.parse(localStorage.getItem(DURATIONS_KEY) || '{}');
    const v = Number(saved[kind]);
    if (v > 300 && v < 120000) return v;
  } catch (_) {}
  return DEFAULT_MS[kind] || 5000;
}

function rememberMs(kind, ms) {
  try {
    const saved = JSON.parse(localStorage.getItem(DURATIONS_KEY) || '{}');
    const prev = Number(saved[kind]);
    saved[kind] = Math.round(prev > 0 ? prev * .6 + ms * .4 : ms);
    localStorage.setItem(DURATIONS_KEY,JSON.stringify(saved));
  } catch (_) {}
}

function drawRing(pct) {
  const v = Math.max(0,Math.min(100,pct));
  $('busyArc').setAttribute('stroke-dashoffset',String(RING_C * (1 - v / 100)));
  const n = Math.round(v);
  $('busyPct').textContent = `${n}%`;
  if (n % 10 === 0) $('busyRing').setAttribute('aria-valuenow',String(n));
}

function busyTarget(now) {
  const t = now - busy.started;
  if (busy.real) {
    const [lo,hi] = STAGE_RANGE[busy.stage] || STAGE_RANGE.render;
    const st = now - busy.stageAt;
    return lo + (hi - lo) * .85 * (1 - Math.exp(-st / 2500));
  }
  return 95 * (1 - Math.exp(-2.6 * t / busy.expected));
}

function busyTick() {
  if (!busy || busy.finishing) return;
  const now = performance.now();
  const target = busyTarget(now);
  if (target > busy.shown) busy.shown += (target - busy.shown) * .18;
  drawRing(busy.shown);
  if (!busy.slow && now - busy.started > 25000 && !(busy.real && STAGE_SUB[busy.stage])) {
    busy.slow = true;
    $('busySub').textContent = SLOW_SUB;
  }
  busy.raf = requestAnimationFrame(busyTick);
}

function setBusyStage(stage) {
  if (!busy || !busy.real || stage === busy.stage) return;
  if (stage === 'idle' && busy.stage !== 'idle') return; // fine render: arriva la risposta
  busy.stage = stage;
  busy.stageAt = performance.now();
  if (STAGE_SUB[stage]) $('busySub').textContent = STAGE_SUB[stage];
}

function pollProgress() {
  if (!busy || !busy.real || !directBase || !session) return;
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(),1500);
  fetch(`${directBase}/progress?session=${encodeURIComponent(session)}&_=${Date.now()}`,{
    cache:'no-store', credentials:'omit', signal:controller.signal
  })
    .then(r => { if (!r.ok) throw new Error(String(r.status)); return r.json(); })
    .then(data => { if (busy) { busy.pollFails = 0; setBusyStage(String(data.stage || 'idle')); } })
    .catch(() => {
      // Backend senza /progress (o tunnel lento): si passa alla stima.
      if (busy && ++busy.pollFails >= 2) {
        busy.real = false;
        clearInterval(busy.poll);
      }
    })
    .finally(() => clearTimeout(timer));
}

function showBusy(title, sub, kind) {
  hideBusy();
  const real = PHOTO_PHASES.has(kind) && Boolean(directBase);
  busy = {
    kind, real, started:performance.now(), stageAt:performance.now(), stage:'idle',
    expected:expectedMs(kind), shown:0, slow:false, pollFails:0, raf:0, poll:0, finishing:false
  };
  $('busyTitle').textContent = title;
  $('busySub').textContent = sub;
  drawRing(0);
  $('busy').classList.add('open');
  $('busy').setAttribute('aria-hidden','false');
  document.documentElement.classList.add('is-busy');
  busy.raf = requestAnimationFrame(busyTick);
  if (real) busy.poll = setInterval(pollProgress,600);
}

// Porta il cerchio al 100% con una breve animazione, poi risolve: nessuna attesa finta.
function finishBusy() {
  if (!busy) return Promise.resolve();
  const b = busy;
  const now = performance.now();
  const elapsed = now - b.started;
  if (!b.real || b.stage === 'idle') rememberMs(b.kind,elapsed);
  b.finishing = true;
  cancelAnimationFrame(b.raf);
  clearInterval(b.poll);
  const duration = 350;
  const from = b.shown;
  const t0 = now;
  return new Promise(resolve => {
    const step = () => {
      if (busy !== b) { resolve(); return; }
      const k = Math.min(1,(performance.now() - t0) / duration);
      const eased = 1 - Math.pow(1 - k,3);
      drawRing(from + (100 - from) * eased);
      if (k < 1) requestAnimationFrame(step);
      else setTimeout(resolve,160);
    };
    requestAnimationFrame(step);
  });
}

function hideBusy() {
  if (busy) {
    cancelAnimationFrame(busy.raf);
    clearInterval(busy.poll);
    busy = null;
  }
  $('busy').classList.remove('open');
  $('busy').setAttribute('aria-hidden','true');
  document.documentElement.classList.remove('is-busy');
}

/* ---------- Home ---------- */
function renderHome() {
  const box = $('homeList');
  if (!box || box.dataset.ready) return;
  box.dataset.ready = '1';
  HOME_GROUPS.forEach(g => {
    const sec = document.createElement('section');
    sec.className = 'hm-group';
    sec.setAttribute('aria-label',g.title);
    sec.innerHTML = '<div class="hm-head"><span class="hm-title"></span></div><div class="hm-list"></div>';
    sec.querySelector('.hm-title').textContent = g.title;
    sec.querySelector('.hm-head').insertAdjacentHTML('afterbegin',svgIcon(g.icon,'hm-gico'));
    const list = sec.querySelector('.hm-list');
    g.ids.forEach(id => {
      const r = REQUESTS.find(x => x.id === id);
      if (!r) return;
      const b = document.createElement('button');
      b.type = 'button';
      b.className = 'hm-item';
      b.dataset.id = r.id;
      b.innerHTML = svgIcon(r.icon,'hm-ico') + '<span class="hm-txt"><span class="hm-name"></span><span class="hm-desc"></span></span>' +
        '<svg class="hm-go" viewBox="0 0 24 24" aria-hidden="true"><path d="M9 6l6 6-6 6"/></svg>';
      b.querySelector('.hm-name').textContent = r.title;
      b.querySelector('.hm-desc').textContent = r.desc;
      b.addEventListener('click',() => openRequest(r));
      list.appendChild(b);
    });
    box.appendChild(sec);
  });
}

// Etichetta in alto di ogni pagina: nome della richiesta.
function applyEyebrows(screenName) {
  if (LIVE || !screenName || screenName === 'home') return;
  const screen = document.querySelector(`[data-screen="${screenName}"]`);
  const eb = screen && screen.querySelector('.eyebrow');
  const req = currentRequest();
  if (!eb || !req) return;
  eb.textContent = screenName === 'preview' ? `${req.title} · Anteprima` : req.title;
}

function openRequest(r) {
  navDir = 1;
  nat = r.id === 'ita';
  changeKind(r.kind,true,false,r.phase || '');
}

function goHome() {
  navDir = -1;
  haptic('select');
  nat = false;
  changeKind('',true,true);
}

// Dalla Home laterale / dal titolo: se c'è lavoro in corso, prima si chiede conferma.
function askGoHome() {
  if (LIVE || !kind) return;
  if (flowIndex === 0 && !previewMode) { goHome(); return; }
  const msg = 'Tornare alla Home? Quello che hai inserito in questa grafica andrà perso.';
  if (tg && typeof tg.showConfirm === 'function') {
    try { tg.showConfirm(msg,ok => { if (ok) goHome(); }); return; } catch (_) {}
  }
  if (window.confirm(msg)) goHome();
}

// Cambiando tipo di grafica si riparte da zero: nessun dato resta salvato.
function resetAllData() {
  competition = '';
  side = '';
  kit = '';
  kitAuto = false;
  shirt = '';
  jrColor = '';
  jrb.cards.forEach(c => { try { URL.revokeObjectURL(c.url); } catch (_) {} });
  Object.assign(jrb,{style:'', title:'', tcolor:'#ffffff', cards:[], bg:'', sel:-1, uploading:0, tpl:0, order:null, swap:-1, csel:-1, tpls:null});
  jrc.key = ''; jrcCloseSheet();
  pxiModule = '';
  pxiPicks = Array(11).fill('');
  calMonth = 0;
  tableComp = '';
  tableView = '';
  mdPick = '';
  kitFromMatch = false;
  calRows = [];
  pose = '';
  moment = '';
  phase = '';
  pensOn = false;
  etOn = false;
  selectedTeam = null;
  selectedPlayer = null;
  natReset();
  ['opponentSearch','playerSearch','minute','homePens','awayPens','squadText','matchStadium','matchTime','matchDate','xiText','pxiText'].forEach(id => { $(id).value = ''; });
  xiPicks = [];
  pxiModuleManual = false;
  $('pxiSrcHint').textContent = '';
  document.querySelectorAll('.src-row .btn').forEach(b => b.classList.remove('on'));
  updateSquadSummary();
  updateLineupSummary();
  clearPhoto();
  clearPhase();
  igClearPhoto();
  $('igText').value = '';
  igColor = 'black';
  Object.assign(iq, {url:'', photos:[], sel:-1, avatar:'', loading:false, verified:false, story:false});
  ['iqUrl','iqText','iqName','iqHandle'].forEach(id => { $(id).value = ''; });
  igRefresh();
  $('calYear').value = String(new Date().getFullYear());
  $('matchTime').value = '20:45';
  $('matchDate').value = new Date(Date.now() - new Date().getTimezoneOffset() * 60000).toISOString().slice(0,10);
  // Il risultato parte da 0–0: se non lo tocchi resta così.
  $('homeScore').value = '0';
  $('awayScore').value = '0';
  $('evHomeScore').value = '0';
  $('evAwayScore').value = '0';
  clearStats();
  previewPayloadText = '';
  if (previewObjectUrl) {
    try { URL.revokeObjectURL(previewObjectUrl); } catch (_) {}
    previewObjectUrl = '';
  }
  $('previewImage').removeAttribute('src');
  setPreviewError('');
}

function changeKind(value, force=false, quiet=false, ph='') {
  if (value === kind && !previewMode && !force) return;
  if (!quiet) haptic('select');
  previewMode = false;
  kind = value;
  resetAllData();
  phase = ph;
  if (kind === 'squad') prefetchSquadSite();
  buildFlow();
  flowIndex = 0;
  refreshSearchSummaries();
  pendingRefresh = true;
  renderFlow();
}

/* ---------- Search ---------- */
// Lista con chiave: se i risultati non cambiano si aggiorna solo la selezione;
// se cambiano, entrano con una breve cascata solo le righe che prima non c'erano.
/* ---------- Loghi squadre ---------- */
// source_url è il PNG ufficiale (mono: nero su trasparente); il CSS lo rende nero o bianco
// in base al tema. preview_url (a colori, dal CDN) resta solo come riserva.
function teamLogoUrls(team) {
  if (!team) return [];
  const preview = team.preview_url ? String(team.preview_url).replace(/([?&])w=\d+/,'$1w=96') : '';
  return [team.logo,team.source_url,preview].filter(Boolean);
}

// Riempie un contenitore .logo: prova le URL in ordine, se falliscono tutte mostra l'iniziale.
function fillLogo(box, team) {
  const key = team ? `${team.name}|${(team.logo || '').length}` : '';
  if (box.dataset.team === key) return;
  box.dataset.team = key;
  box.innerHTML = '';
  box.classList.remove('fallback');
  if (!team) return;
  const urls = teamLogoUrls(team);
  const initial = () => {
    box.innerHTML = '';
    box.classList.add('fallback');
    box.textContent = displayTeamName(team.name).charAt(0).toUpperCase();
  };
  if (!urls.length) { initial(); return; }
  const img = new Image();
  img.alt = '';
  img.decoding = 'async';
  img.loading = 'eager';
  img.referrerPolicy = 'no-referrer';
  let i = 0;
  img.onload = () => img.classList.add('ok');
  img.onerror = () => { i += 1; if (i < urls.length) img.src = urls[i]; else initial(); };
  img.src = urls[0];
  box.appendChild(img);
}

function updateOpponentLogo() {
  fillLogo($('opponentLogo'),selectedTeam);
  $('opponentField').classList.toggle('has-logo',Boolean(selectedTeam));
}

function renderResults(listId, matches, selectedName, labelFn, onPick, logoFn, maxResults = MAX_RESULTS) {
  const box = $(listId);
  box._onPick = onPick;
  const items = matches.slice(0,maxResults);
  const key = items.map(item => item.name).join('\n');
  if (box.dataset.key !== key) {
    const before = new Set([...box.children].map(b => b.dataset.name));
    const animateRows = motionOK();
    let n = 0;
    box.dataset.key = key;
    box.innerHTML = '';
    items.forEach(item => {
      const b = document.createElement('button');
      b.type = 'button';
      b.className = 'result';
      b.dataset.name = item.name;
      b.innerHTML = '<span class="res-main"><span class="res-name"></span></span><span class="tick" aria-hidden="true">✓</span>';
      b.querySelector('.res-name').textContent = labelFn(item);
      if (logoFn) {
        const logo = document.createElement('span');
        logo.className = 'logo';
        logo.setAttribute('aria-hidden','true');
        fillLogo(logo,logoFn(item));
        b.firstChild.prepend(logo);
      }
      if (animateRows && !before.has(item.name)) {
        b.classList.add('enter');
        b.style.animationDelay = `${Math.min(n++,6) * 15}ms`;
      }
      b.addEventListener('click',() => { haptic('select'); box._onPick(item); });
      box.appendChild(b);
    });
  }
  box.querySelectorAll('.result').forEach(b => {
    b.classList.toggle('selected',Boolean(selectedName) && b.dataset.name === selectedName);
  });
}

/* ---------- Squadre per competizione ---------- */
// Pack FCLogo da cui pescare le avversarie (suffisso dello slug, es. "2026-27-serie-a").
const COMPETITION_PACKS = {
  'ita.1':['serie-a'],
  'ita.super_cup':['serie-a'],
  'ita.coppa_italia':['serie-a','serie-b'],
  'uefa.champions':['uefa-champions-league'],
  'uefa.europa':['uefa-europa-league'],
  'uefa.europa.conf':['uefa-conference-league']
};

function competitionPacks() {
  return COMPETITION_PACKS[competition] || [];
}

// Se il catalogo non ha ancora il pack della competizione, mostra tutte le squadre.
let teamPoolFallback = false;
function currentTeamPool() {
  const packs = competitionPacks();
  const pool = teams.filter(team =>
    (team.packs || []).some(slug => packs.some(suffix => String(slug).endsWith(`-${suffix}`))));
  teamPoolFallback = !pool.length;
  return teamPoolFallback ? teams : pool;
}

// Lista completa subito; la ricerca filtra da 1 carattere.
function searchTeams(pool, rawQuery) {
  if (!norm(rawQuery)) return pool;
  return pool
    .map(item => ({item,rank:rankItem(item,norm(rawQuery))}))
    .filter(row => Number.isFinite(row.rank))
    .sort((a,b) => a.rank - b.rank ||
      displayTeamName(a.item.name).localeCompare(displayTeamName(b.item.name),'it',{sensitivity:'base'}))
    .map(row => row.item);
}

function refreshSearchSummaries() {
  const tq = $('opponentSearch').value;
  const pool = teamsLoaded ? currentTeamPool() : [];
  // Lista: solo la competizione. Ricerca scritta: tutte le squadre, prima quelle della competizione.
  if (norm(tq)) {
    const inPool = new Set(pool.map(item => item.name));
    teamMatches = searchTeams(teamsLoaded ? teams : [],tq)
      .map((item,i) => ({item,i,own:inPool.has(item.name) ? 0 : 1}))
      .sort((a,b) => a.own - b.own || a.i - b.i)
      .map(row => row.item);
  } else {
    teamMatches = pool;
  }

  // Squadra non più nel catalogo: si riparte da zero.
  if (selectedTeam && teamsLoaded && !teams.some(item => item.name === selectedTeam.name)) {
    selectedTeam = null;
    $('opponentSearch').value = '';
    teamMatches = pool;
  }
  if (selectedTeam && !teamMatches.some(item => item.name === selectedTeam.name)) {
    if (!namesFor(selectedTeam).some(name => norm(tq) === norm(name))) selectedTeam = null;
  }

  const compLabel = labelOf(competitionOptions(),competition);
  if (!teamsLoaded) $('opponentSummary').textContent = 'Caricamento squadre…';
  else if (!norm($('opponentSearch').value)) $('opponentSummary').textContent = teamPoolFallback
    ? `${pool.length} squadre (catalogo ${compLabel} non ancora disponibile)`
    : `${pool.length} squadre · ${compLabel}`;
  else if (!teamMatches.length) $('opponentSummary').textContent = 'Nessun risultato.';
  else if (selectedTeam) $('opponentSummary').textContent = `Selezionata: ${displayTeamName(selectedTeam.name)}`;
  else $('opponentSummary').textContent = `${teamMatches.length} risultat${teamMatches.length === 1 ? 'o' : 'i'}`;

  renderResults('opponentList',teamMatches,selectedTeam && selectedTeam.name,
    item => displayTeamName(item.name),
    item => {
      selectedTeam = item;
      $('opponentSearch').value = displayTeamName(item.name);
      refreshSearchSummaries();
      renderSteps();
      document.activeElement && document.activeElement.blur && document.activeElement.blur();
    },
    item => item);
  updateOpponentLogo();

  const pq = $('playerSearch').value;
  playerMatches = playersLoaded ? searchItems(currentPlayerPool(),pq) : [];

  if (selectedPlayer && !playerMatches.some(item => item.name === selectedPlayer.name)) {
    if (norm(pq) !== norm(selectedPlayer.name) && norm(pq) !== norm(surnameOf(selectedPlayer))) selectedPlayer = null;
  }

  if (!playersLoaded) $('playerSummary').textContent = 'Caricamento giocatori…';
  else if (!norm(pq)) $('playerSummary').textContent = `${playerMatches.length} ${kind === 'saved' ? 'portieri' : 'giocatori'}`;
  else if (!playerMatches.length) $('playerSummary').textContent = 'Nessun risultato.';
  else if (selectedPlayer) $('playerSummary').textContent = `Selezionato: ${surnameOf(selectedPlayer)}`;
  else $('playerSummary').textContent = `${playerMatches.length} risultat${playerMatches.length === 1 ? 'o' : 'i'}`;

  renderResults('playerList',playerMatches,selectedPlayer && selectedPlayer.name,
    item => surnameOf(item),
    item => {
      selectedPlayer = item;
      $('playerSearch').value = surnameOf(item);
      refreshSearchSummaries();
      renderSteps();
      document.activeElement && document.activeElement.blur && document.activeElement.blur();
    },
    null,
    Infinity);
}

function resolveTeam() {
  if (!teamsLoaded) { showError('Impossibile caricare le squadre. Riprova.'); return false; }
  if (selectedTeam) return true;
  const query = norm($('opponentSearch').value);
  const exact = teamMatches.find(item => namesFor(item).some(name => norm(name) === query));
  if (exact || teamMatches.length === 1) {
    selectedTeam = exact || teamMatches[0];
    $('opponentSearch').value = displayTeamName(selectedTeam.name);
    refreshSearchSummaries();
    return true;
  }
  showError(teamMatches.length > 1 ? 'Seleziona una squadra dalla lista.' : 'Cerca e seleziona un avversario.');
  return false;
}

function resolvePlayer() {
  if (!playersLoaded) { showError('Impossibile caricare i giocatori. Riprova.'); return false; }
  if (selectedPlayer) return true;
  const query = norm($('playerSearch').value);
  const exact = playerMatches.find(item => namesFor(item).some(name => norm(name) === query));
  if (exact || playerMatches.length === 1) {
    selectedPlayer = exact || playerMatches[0];
    $('playerSearch').value = selectedPlayer.name;
    refreshSearchSummaries();
    return true;
  }
  if (playerMatches.length > 1) showError(kind === 'saved' ? 'Seleziona un portiere dalla lista.' : 'Seleziona un giocatore dalla lista.');
  else showError(kind === 'saved' ? 'Cerca e seleziona un portiere.' : 'Cerca e seleziona un giocatore.');
  return false;
}
