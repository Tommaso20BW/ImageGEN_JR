/* Mini App ImageGen JR. File caricati in ordine da index.html: l'ordine conta. */
/* ---------- Motion ---------- */
const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)');
// Animazioni disattivate in tutta l'app: le pagine e i controlli cambiano subito.
const motionOK = () => false;
const EASE_OUT = 'cubic-bezier(.2,.8,.2,1)';
const EASE_IN = 'cubic-bezier(.4,0,1,1)';
// Su iOS :active non scatta al tocco senza almeno un listener touchstart.
document.addEventListener('touchstart',() => {},{passive:true});
const urlParams = new URLSearchParams(location.search);
const session = urlParams.get('session') || '';
const directEndpoint = urlParams.get('direct') || '';
const directBase = directEndpoint.replace(/\/submit\/?$/,'');
// Live: aperta dal pulsante del LiveScore. Solo la foto di una fase, poi "Conferma".
const LIVE = urlParams.get('mode') === 'live';
const LIVE_SLOT = urlParams.get('slot') || 'half';
const LIVE_PHASE = urlParams.get('phase') || 'half';
const SEND_LABEL = LIVE ? 'Conferma' : 'Invia';
let liveTitle = '';
// Scadenza reale della sessione (ms epoch), passata da service.py. Senza, il timer resta nascosto.
// Si aggiorna: all'apertura si legge quella vera dal servizio (può essere stata allungata).
let sessionExpiresAt = Number(urlParams.get('expires')) || 0;
const sessionExpired = () => Boolean(sessionExpiresAt) && Date.now() >= sessionExpiresAt;
const EXPIRED_MESSAGE = 'Sessione scaduta. Avvia di nuovo il workflow ImageGen.';
const MIN_SEARCH = 2;
const MAX_RESULTS = 150;
const finePointer = window.matchMedia('(pointer:fine)').matches;

let kind = '';          // tipo reale; vuoto = schermata Home
// Nessuna opzione preselezionata: ogni scelta la fa l'utente.
let phase = '';
let pensOn = false;
let etOn = false;
const realKind = () => kind === 'match' ? phase : kind;
let competition = '';
let side = '';
let kit = '';
let kitAuto = false;   // kit messo in automatico (competizione UEFA, passo nascosto)
let jrColor = '';      // FOTO + JR: colore del logo
// FOTO + JR Sfocata: foto caricate (max 3), sfondo e posizione di ognuna
// (x/y centro in frazione della pagina, w larghezza in frazione della pagina).
const JR_LIMITS = {blur:4, collage:9};      // foto massime per stile
const jrLimit = () => JR_LIMITS[jrb.style] || 1;
const jrMin = () => jrb.style === 'collage' ? 2 : 1;
const jrb = {style:'', ratio:'3:4', cards:[], bg:'', sel:-1, uploading:0, tpl:0, order:null, swap:-1, csel:-1, tpls:null};
let pxiModule = '';    // PROBABILE XI: modulo
let tableComp = '';    // CLASSIFICA: SA, UCL, UEL o UECL
let calMonth = 0;      // CALENDARIO: mese (1-12)
const PREMATCH = ['squad','xi','md','pxi'];   // grafiche che partono dalla scelta della partita
let mdPick = '';       // id partita ESPN scelta, 'manual' o ''
let igPicking = false; // Storia IG: pagina "Dagli ultimi invii" aperta (11-invii.js)
// CITAZIONE IG (12-citazione.js): link letto, foto del post, foto scelta, foto profilo.
const iq = {url:'', photos:[], sel:-1, avatar:'', loading:false};
let kitFromMatch = false;   // maglia presa da ESPN (partite giocate): niente passaggio "Maglia"
let fixtureList = [];
let calRows = [];
let pxiPicks = Array(11).fill('');
let pose = '';
let moment = '';

let players = [];
let teams = [];
let playerMatches = [];
let teamMatches = [];
let selectedPlayer = null;
let selectedTeam = null;
let playersLoaded = false;
let teamsLoaded = false;
let catalogLoadPromise = null;
const CATALOG_CACHE_KEY = 'imagegen-jr-catalog-v2';
const SESSION_KEY = 'imagegen-jr-session';
// Ogni nuovo workflow ha una sessione diversa: butta via tutto ciò che il browser ricorda.
(function resetCacheOnNewSession() {
  try {
    if (localStorage.getItem(SESSION_KEY) === session && session) return;
    localStorage.removeItem('imagegen-jr-catalog-v1');
    localStorage.removeItem(CATALOG_CACHE_KEY);
    if (session) localStorage.setItem(SESSION_KEY,session);
    else localStorage.removeItem(SESSION_KEY);
  } catch (_) {}
  try {
    if (window.caches && caches.keys) caches.keys().then(keys => keys.forEach(k => caches.delete(k)));
  } catch (_) {}
})();

let flow = [];
let flowIndex = 0;
const statRows = Object.fromEntries(STATS.map(label => [label,{home:'',away:''}]));
let previewObjectUrl = '';
let previewPayloadText = '';
let previewMode = false;
let lastRenderedScreen = '';
let lastRenderedFlowIndex = null;
let lastRenderedPreviewMode = false;

const foldSpecial = value => String(value || '')
  .replace(/ı/g,'i').replace(/ł/g,'l').replace(/đ/g,'d')
  .replace(/ð/g,'d').replace(/þ/g,'th').replace(/ø/g,'o')
  .replace(/æ/g,'ae').replace(/œ/g,'oe').replace(/ß/g,'ss');

const norm = value => foldSpecial(String(value || '').toLowerCase())
  .normalize('NFKD')
  .replace(/[\u0300-\u036f]/g,'')
  .replace(/[^a-z0-9]+/g,' ')
  .trim();

/* Nomi italiani: la fonte è data/teams.json di LiveScore (la stessa dell'immagine).
   Il confronto ignora maiuscole, accenti, trattini e parole generiche (FC, Football Club…);
   Le squadre non presenti in teams.json mostrano il nome del catalogo, senza modifiche. */
const NAME_NOISE = new Set(['fc','cf','afc','sc','ac','as','us','ss','cd','fk','sk','bk','if','losc',
  'football','club','futbol','calcio','spor','kulubu','kulub','de','of','the','1907','1909','1913','1898','1911']);
const stripNoise = key => key.split(' ').filter(word => word && !NAME_NOISE.has(word)).join(' ');
let teamNamesExact = new Map();
let teamNamesLoose = new Map();
let teamNamesRaw = null;
let teamNamesByAlias = new Map();
let teamNamesCustom = new Map();   // Impostazioni › Squadre e loghi: nome scelto, per ogni nome della squadra

function setTeamNames(obj) {
  if (!obj || typeof obj !== 'object' || Array.isArray(obj)) return false;
  const exact = new Map();
  const loose = new Map();
  const ambiguous = new Set();
  Object.entries(obj).forEach(([source,value]) => {
    const display = String(Array.isArray(value) ? value[0] : value || '').trim();
    const key = norm(source);
    if (!display || !key) return;
    exact.set(key,display);
    const short = stripNoise(key);
    if (!short) return;
    if (loose.has(short) && loose.get(short) !== display) ambiguous.add(short);
    else loose.set(short,display);
  });
  ambiguous.forEach(key => loose.delete(key));
  if (!exact.size) return false;
  teamNamesExact = exact;
  teamNamesLoose = loose;
  teamNamesRaw = obj;
  resolveTeamAliases();
  return true;
}

const lookupTeamName = name => {
  const key = norm(name);
  return teamNamesExact.get(key) || teamNamesLoose.get(stripNoise(key)) || '';
};

// Se il nome del catalogo non è in teams.json ma lo è un suo alias (es. "Sporting CP"),
// si usa la traduzione dell'alias; poi si riordina l'elenco per nome mostrato.
function resolveTeamAliases() {
  const byAlias = new Map();
  teams.forEach(team => {
    if (lookupTeamName(team.name)) return;
    for (const alias of (team.aliases || [])) {
      const hit = lookupTeamName(alias);
      if (hit) { byAlias.set(norm(team.name),hit); break; }
    }
  });
  teamNamesByAlias = byAlias;
  const custom = new Map();
  teams.forEach(team => {
    if (team.display_name) [team.name, ...(team.aliases || [])].forEach(n => custom.set(norm(n), team.display_name));
  });
  teamNamesCustom = custom;
  if (teams.length) {
    teams.sort((a,b) =>
      displayTeamName(a.name).localeCompare(displayTeamName(b.name),'it',{sensitivity:'base'}));
  }
}

function displayTeamName(name) {
  return teamNamesCustom.get(norm(name)) || baseDisplayName(name);
}

// Nome senza le correzioni di Impostazioni (teams.json di LiveScore o nome del catalogo).
function baseDisplayName(name) {
  const raw = String(name || '').trim();
  const key = norm(raw);
  return teamNamesExact.get(key)
    || teamNamesLoose.get(stripNoise(key))
    || teamNamesByAlias.get(key)
    || raw;
}

function currentMatchupNames() {
  const opponent = nat ? (natOppName() || 'Avversaria') : selectedTeam ? displayTeamName(selectedTeam.name) : 'Avversario';
  const us = nat ? 'Italia' : 'Juventus';
  return side === 'home' ? {home:us,away:opponent} : {home:opponent,away:us};
}

function namesFor(item) {
  return [item.name, displayTeamName(item.name), ...(item.aliases || [])].filter(Boolean);
}

function rankItem(item, query) {
  // Se la squadra ha un nome italiano (es. "FC Inter Milan" → "Inter"), il nome
  // originale conta solo se la ricerca ne copre l'inizio: altrimenti "milan" troverebbe anche l'Inter.
  const raw = norm(item.name);
  const translated = norm(displayTeamName(item.name)) !== raw;
  const all = namesFor(item).map(norm).filter(Boolean);
  const names = translated ? all.filter(v => v !== raw) : all;
  if (all.some(v => v === query)) return 0;
  if (all.some(v => v.startsWith(query))) return 1;
  if (names.some(v => v.split(' ').some(word => word.startsWith(query)))) return 2;
  if (names.some(v => v.includes(query))) return 3;
  return Infinity;
}

function searchItems(items, rawQuery) {
  const query = norm(rawQuery);
  if (!query) return items;
  return items
    .map(item => ({item,rank:rankItem(item,query)}))
    .filter(row => Number.isFinite(row.rank))
    .sort((a,b) => a.rank - b.rank ||
      displayTeamName(a.item.name).localeCompare(displayTeamName(b.item.name),'it',{sensitivity:'base'}))
    .map(row => row.item);
}

function labelOf(options, value) {
  return (options.find(([key]) => key === value) || ['',value])[1];
}

function currentPlayerPool() {
  const keepers = kind === 'saved';
  return players.filter(player => !keepers || player.role === 'goalkeeper');
}

/* ---------- Flow ---------- */
function buildFlow() {
  flow = [];
  // Partita UEFA: tema della competizione automatico; tema rimasto da un'altra partita: via.
  const uefa = uefaAuto();
  if (uefa) kit = uefa;
  else if (UEFA_THEMES[kit]) kit = '';
  if (LIVE) { flow = ['phasephoto']; flowIndex = 0; return; }
  if (nat) { flow = natFlow(); flowIndex = Math.max(0,Math.min(flowIndex,flow.length - 1)); return; }
  if (!kind) { flow = ['home']; flowIndex = 0; return; }
  if (kind === 'sent') { flow = ['sentlist','sentitem']; flowIndex = Math.max(0,Math.min(flowIndex,1)); return; }
  const base = ['competition','side','opponent'];
  // Goal/saved: maglia sempre. Half/end/full: solo con "Italia" (serve per lo sfondo);
  // le UEFA hanno lo sfondo della competizione. Stats: come half/end/full. Kick off: mai.
  const italy = competition.startsWith('ita.');
  const withKit = [...base,'kit'];
  // Prima si sceglie la partita dal calendario Juventus (competizione, campo e
  // avversario si compilano da soli; Matchday anche stadio, data e ora), oppure
  // "Altra partita" per scrivere tutto a mano, anche dati inventati.
  // Pre-gara: prossime partite; Goal/Event/Stats: partita in corso o già giocate.
  const picked = mdPick && mdPick !== 'manual';
  // Partita scelta: via competizione/campo/avversario; via anche la maglia se ESPN la sa.
  const pick = steps => ['mdpick',...(picked ? steps.filter(s => !base.includes(s) && !(s === 'kit' && kitFromMatch)) : steps)];
  // Amichevole: Gol/Parata senza foto del calciatore (niente maglia e posa), fasi senza foto.
  const friendly = isFriendly();
  if ((kind === 'goal' || kind === 'saved') && friendly) flow = pick([...base,...juveGoalSteps(true)]);
  else if (kind === 'goal' || kind === 'saved') flow = pick([...withKit,...juveGoalSteps(false)]);
  else if (kind === 'kick') flow = pick(base);
  else if (kind === 'match' && phase === 'kick') flow = pick(base);
  else if (kind === 'match') flow = [...pick([...(italy ? withKit : base),'score']),...(PHOTO_PHASES.has(phase) && !friendly ? ['phasephoto'] : [])];
  else if (kind === 'stats') flow = pick([...(italy ? withKit : base),'moment','stats']);
  else if (PREMATCH.includes(kind)) {
    // Matchday / Starting XI di una partita UEFA: niente passo "Maglia" (colori della coppa).
    const kitStep = uefa && kind !== 'pxi' ? [] : ['kit'];
    const rest = {squad:['squad'], xi:[...kitStep,'lineup','photo'], md:[...kitStep,'match','photo'], pxi:friendly ? ['xi11'] : ['kit','xi11']}[kind];
    flow = pick([...base,...rest]);
    // Squad List da una partita dei convocati: giocatori già compilati, si va dritti all'anteprima.
    if (kind === 'squad' && String(mdPick).startsWith('site:')) flow = ['mdpick'];
  }
  else if (kind === 'jr') flow = jrb.style === 'blur'
    ? ['jrstyle','jrphotos',...(jrb.cards.length > 1 ? ['jrbg'] : []),'jrcolor','jrblur']
    : jrb.style === 'collage' ? ['jrstyle','jrphotos','jrcolor','jrlayout']
    : ['jrstyle','jrratio','jrcolor','photo'];
  else if (kind === 'cal') flow = ['calmonth','calrows'];
  else if (kind === 'table') flow = ['tablecomp'];
  else if (kind === 'igbn') flow = igPicking ? ['igcontent','igsent'] : ['igcontent'];
  else if (kind === 'igq') flow = iq.photos.length > 1 ? ['iqurl','iqpick','iqtext'] : ['iqurl','iqtext'];
  flowIndex = Math.max(0,Math.min(flowIndex,flow.length - 1));
}

function stepTitle(step) {
  if (step === 'player') return kind === 'saved' ? 'Portiere' : 'Giocatore';
  return STEP_NAMES[step] || step;
}

function stepValue(step) {
  const natValue = natStepValue(step);
  if (natValue !== null) return natValue;
  switch (step) {
    case 'competition': return labelOf(competitionOptions(),competition);
    case 'side': return labelOf(SIDES,side);
    case 'opponent': return selectedTeam ? displayTeamName(selectedTeam.name) : '';
    case 'kit': return nat ? labelOf(NAT_KITS,kit) : needsShirt() ? labelOf(KITS,shirt) : labelOf(KITS,kit);
    case 'player': return selectedPlayer ? surnameOf(selectedPlayer) : '';
    case 'minute': {
      const min = $('minute').value.trim();
      const h = $('evHomeScore').value.trim(), a = $('evAwayScore').value.trim();
      return min ? `${h || 0}-${a || 0} · ${min}'` : '';
    }
    case 'pose': return labelOf(POSES,pose);
    case 'score': {
      const h = $('homeScore').value.trim(), a = $('awayScore').value.trim();
      let out = h !== '' && a !== '' ? `${h} – ${a}` : '';
      if (out && phase === 'full' && etOn) out += ' (suppl.)';
      if (out && phase === 'full' && pensOn) {
        const ph = $('homePens').value.trim(), pa = $('awayPens').value.trim();
        if (ph !== '' && pa !== '') out += ` (rig. ${ph} – ${pa})`;
      }
      return out;
    }
    case 'moment': return labelOf(MOMENTS,moment);
    case 'lineup': {
      const n = lineupRows().length;
      return n ? `${n} / 11` : '';
    }
    case 'photo': return photoState.id ? 'Caricata' : '';
    case 'phasephoto': return ppState.bg ? 'Caricata' : '';
    case 'jrcolor': return jrColorLabel();
    case 'jrstyle': return labelOf(JR_STYLES,jrb.style);
    case 'tablecomp': return labelOf(TABLE_COMPS,tableComp);
    case 'jrratio': return jrb.ratio;
    case 'jrphotos': return jrb.cards.length ? `${jrb.cards.length} foto` : '';
    case 'jrbg': { const n = jrb.cards.findIndex(c => c.id === jrb.bg); return n < 0 ? '' : `Foto ${n + 1}`; }
    case 'jrblur': return jrb.cards.length ? 'Pronta' : '';
    case 'jrlayout': return jrb.tpls ? `Layout ${jrb.tpl + 1}` : '';
    case 'module': return pxiModule;
    case 'mdpick': {
      if (mdPick.startsWith('site:')) {
        const s = squadSite.find(x => `site:${x.id}` === mdPick);
        if (!s) return '';
        const [,mo,d] = s.date.split('-').map(Number);
        return `${d} ${MONTHS_SHORT[mo - 1]} · ${displayTeamName(s.opponent)}`;
      }
      const m = fixtureList.find(f => f.id === mdPick);
      return mdPick === 'manual' ? 'A mano' : (m ? fixtureLabel(m, true) : '');
    }
    case 'iqurl': return iq.photos.length ? `${iq.photos.length} foto` : '';
    case 'iqpick': return iq.sel >= 0 ? `Foto ${iq.sel + 1}` : '';
    case 'iqtext': return $('iqName').value.trim();
    case 'igcontent': {
      const t = $('igText').value.trim().length;
      return [t ? 'Testo' : '', igb.id ? 'Foto' : ''].filter(Boolean).join(' + ');
    }
    case 'calmonth': return calMonth ? `${CAL_MONTHS[calMonth - 1]} ${$('calYear').value}` : '';
    case 'calrows': { const n = calRows.length; return n ? `${n} partit${n === 1 ? 'a' : 'e'}` : ''; }
    case 'xi11': { const n = pxiPicks.filter(Boolean).length; return n ? `${pxiModule || '?'} · ${n} / 11` : ''; }
    case 'match': {
      const t = $('matchTime').value, d = $('matchDate').value;
      return t && d ? `${d.split('-').reverse().join('/')} · ${t}` : '';
    }
    case 'squad': {
      const n = squadNames().length;
      return n ? `${n} giocatori` : '';
    }
    case 'stats': {
      const n = STATS.filter(l => statRows[l].home || statRows[l].away).length;
      return n ? `${n} / ${STATS.length} voci` : '';
    }
  }
  return '';
}

// La lista viene ricostruita solo se cambia il percorso; altrimenti si aggiornano
// le classi, così spunte e linea della timeline possono animarsi.
const CHECK_SVG = '<svg width="12" height="12" viewBox="0 0 12 12" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M2.6 6.3 5 8.6l4.4-5"/></svg>';

function renderSteps() {
  queueMicrotask(syncNav);      // sottotitolo e "Fine" seguono ogni scelta (avversario, dati…)
  const list = $('stepList');
  const key = flow.join(',');
  if (list.dataset.key !== key) {
    list.dataset.key = key;
    list.innerHTML = '';
    [...flow,null].forEach((step,i) => {
      const li = document.createElement('li');
      const b = document.createElement('button');
      b.type = 'button';
      b.className = 'step-item';
      b.innerHTML = `<span class="mark">${CHECK_SVG}</span><span><div class="step-name"></div><div class="step-val"></div></span>`;
      if (step === null) b.querySelector('.step-name').textContent = 'Anteprima';
      else b.addEventListener('click',() => {
        saveCurrentStatDraft();
        previewMode = false;
        flowIndex = i;
        renderFlow();
      });
      li.appendChild(b);
      list.appendChild(li);
    });
  }
  [...list.children].forEach((li,i) => {
    const b = li.firstChild;
    const step = flow[i];
    const isPreview = i === flow.length;
    const done = !isPreview && (previewMode || i < flowIndex);
    const current = isPreview ? previewMode : (!previewMode && i === flowIndex);
    li.classList.toggle('done',done);
    b.classList.toggle('done',done);
    b.classList.toggle('current',current);
    b.disabled = isPreview || !done;
    if (!isPreview) {
      b.querySelector('.step-name').textContent = stepTitle(step);
      b.querySelector('.step-val').textContent = (done || current) ? stepValue(step) : '';
    }
  });
}

function renderProgress() {
  // Tipo non ancora scelto: percorso sconosciuto, barra quasi vuota.
  const p = previewMode ? 1 : (flowIndex + 1) / (flow.length + 1);
  $('progressBar').style.width = `${Math.round(p * 1000) / 10}%`;
}

// Al primo passo "Indietro" riporta alla Home (tranne in modalità live).
const backLocked = () => LIVE && !previewMode && flowIndex === 0;

function setPreviewError(message='') {
  $('previewError').textContent = message;
  $('previewError').style.display = message ? 'block' : 'none';
}

function openPreview(url) {
  if (previewObjectUrl && previewObjectUrl !== url) {
    try { URL.revokeObjectURL(previewObjectUrl); } catch (_) {}
  }
  previewObjectUrl = url;
  if (url) $('previewImage').src = url;
  setPreviewError('');
  previewMode = true;
  haptic('success');
  renderFlow();
}

// CLASSIFICA: l'anteprima è l'elenco delle squadre; per le altre grafiche l'immagine.
const TABLE_ZONES = {z1:'#1E6BFF', z2:'#FF8A00', z3:'#1DB954', z4:'#E5484D'};
function showTablePreview(table) {
  const on = !!table;
  document.querySelector('[data-screen="preview"] .preview-wrap').hidden = on;
  $('previewTable').hidden = !on;
  const lead = $('previewLead');
  if (lead.dataset.def === undefined) lead.dataset.def = lead.textContent;   // testo normale (anche quello del LIVE)
  lead.textContent = on
    ? 'Controlla la classifica. Se è tutto ok, premi “Invia”: arriva la grafica nella chat del bot.'
    : lead.dataset.def;
  if (!on) { $('previewTable').innerHTML = ''; return; }
  const esc = s => String(s ?? '').replace(/[&<>"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
  const sub = [table.giornata ? `Giornata ${table.giornata}` : '', table.stagione].filter(Boolean).join(' · ');
  const rows = table.rows.map(r => {
    const dr = Number(r.dr) > 0 ? '+' + r.dr : String(r.dr);
    const zone = TABLE_ZONES[r.zone] ? ` style="--z:${TABLE_ZONES[r.zone]}"` : '';
    const juve = /juventus/i.test(r.team) ? ' juve' : '';
    return `<div class="ptab-row${juve}"${zone}><span class="ptab-pos">${esc(r.pos)}</span>` +
      `<span class="ptab-team">${esc(r.team)}</span><span class="ptab-dr">${esc(dr)}</span>` +
      `<span class="ptab-pt">${esc(r.pt)}</span></div>`;
  }).join('');
  $('previewTable').innerHTML =
    `<div class="field-label">${esc(table.name)}${sub ? ' · ' + esc(sub) : ''}</div>` +
    `<div class="ptab-head"><span>Pos</span><span>Squadra</span><span>DR</span><span>PT</span></div>` +
    `<div class="ios-list ptab-list">${rows}</div>`;
}

function closePreview() {
  previewMode = false;
  setPreviewError('');
  renderFlow();
}

/* Transizione di schermata:
   - la vecchia esce in fretta (170ms) scivolando appena nel verso opposto;
   - la nuova entra a cascata: titolo, testo e contenuto arrivano uno dopo l'altro
     dal lato di marcia, con una curva lunga che decelera dolcemente.
   Tutto via Web Animations API: se l'utente tocca di nuovo, si annulla e riparte pulito. */
let screenAnims = [];
let navDir = 0;     // 1 = avanti, -1 = indietro: forza il verso dell'animazione (Home ⇄ percorso)
let pendingRefresh = false;

function stopScreenAnims() {
  screenAnims.forEach(a => { try { a.cancel(); } catch (_) {} });
  screenAnims = [];
  document.querySelectorAll('.screen.leaving').forEach(el => {
    el.classList.remove('leaving');
    el.style.top = '';
  });
}

function animateScreenOut(prev, dir, scrollTop) {
  prev.classList.add('leaving');
  prev.style.top = `calc(var(--pad-top) - ${scrollTop}px)`;
  const a = prev.animate([
    {opacity:1},
    {opacity:0}
  ],{duration:100, easing:EASE_IN, fill:'forwards'});
  a.onfinish = () => {
    prev.classList.remove('leaving');
    prev.style.top = '';
    a.cancel();
  };
  screenAnims.push(a);
}

function animateScreenIn(screen, dir) {
  // Solo dissolvenza: nessuno scorrimento tra una pagina e l'altra.
  screenAnims.push(screen.animate([{opacity:0},{opacity:1}],{duration:160, easing:EASE_OUT, fill:'backwards'}));
}

function renderFlow() {
  const screenName = previewMode ? 'preview' : flow[flowIndex];
  const screen = document.querySelector(`[data-screen="${screenName}"]`);
  const previous = document.querySelector('[data-screen].active');
  const changedScreen = Boolean(previous && screen && previous !== screen);
  let backwards = false;
  if (lastRenderedPreviewMode && !previewMode) backwards = true;
  else if (!previewMode && !lastRenderedPreviewMode && lastRenderedFlowIndex !== null) {
    backwards = flowIndex < lastRenderedFlowIndex;
  }
  const animate = motionOK() && lastRenderedScreen !== '';
  if (navDir) { backwards = navDir < 0; navDir = 0; }
  const dir = backwards ? -1 : 1;
  const scrollTop = $('stage').scrollTop;

  stopScreenAnims();
  document.querySelectorAll('[data-screen]').forEach(el => {
    if (el !== screen) el.classList.remove('active');
  });
  if (screen) screen.classList.add('active');
  document.body.classList.toggle('home-mode',screenName === 'home');
  const editing = screenName === 'photo' || screenName === 'phasephoto' || screenName === 'jrblur' || screenName === 'jrlayout';
  $('stage').classList.toggle('photo-mode', editing);
  if (editing) $('stage').scrollTop = 0;
  try {
    if (tg && tg.disableVerticalSwipes) editing ? tg.disableVerticalSwipes() : tg.enableVerticalSwipes();
  } catch (_) {}
  if (screenName === 'phasephoto') { if (LIVE) $('ppEyebrow').textContent = liveTitle || labelOf(PHASES,phase); loadPpGhost(); requestAnimationFrame(layoutPhase); }
  if (screenName === 'photo') { updatePhotoOverlay(); requestAnimationFrame(layoutPhoto); }
  if (screenName === 'jrphotos') renderJrPicker();
  if (screenName === 'jrlayout') { renderJrLayout(true); requestAnimationFrame(() => { fitColBig(); renderJrLayout(); }); }
  if (screenName === 'jrbg') renderJrBg();
  if (screenName === 'jrblur') { jrbAutoLayout(); requestAnimationFrame(() => { fitJrbFrame(); renderJrb(); }); }
  if (screenName === 'lineup') readXiText();
  if (screenName === 'mdpick') {
    $('mdPickLead').textContent = kind === 'md'
      ? 'Dal calendario della Juventus: competizione, avversario, stadio, data e ora si compilano da soli.'
      : PREMATCH.includes(kind)
        ? 'Dal calendario della Juventus: competizione, campo e avversario si compilano da soli.'
        : 'Partita di oggi o già giocata: competizione, campo e avversario si compilano da soli.';
    $('squadLinkBtn').hidden = kind !== 'squad';
    if (kind === 'squad') {
      $('mdPickLead').textContent = 'Dai convocati pubblicati su juventus.com (prima squadra), dal più recente: partita e giocatori si compilano da soli.';
      loadSquadSite();
    } else loadMdFixtures();
  }
  if (screenName === 'sentlist') { renderSentList(); loadRecent(); }
  if (screenName === 'igcontent') { if (igPicking) { igPicking = false; buildFlow(); } loadPhrases(); renderIgColor(); }
  if (screenName === 'igsent') { renderIgSent(); loadRecent(); }
  if (screenName === 'iqpick') renderIqPick();
  if (screenName === 'sentitem') renderSentItem();
  if (screenName === 'calrows') fillCalendarFromFixtures();
  if (screenName === 'calrows') renderCalRows();
  else closeCalSheet();
  if (screenName === 'xi11') { readPxiText(); loadPxiUpdates(); loadLayouts().then(() => { syncModules(); readPxiText(); }); }
  lastRenderedScreen = screenName || '';
  lastRenderedFlowIndex = flowIndex;
  lastRenderedPreviewMode = previewMode;

  $('stage').scrollTop = 0;
  $('backButton').disabled = backLocked();
  $('backButton').textContent = (!previewMode && flowIndex === 0 && !LIVE) ? '‹ Home' : '‹ Indietro';
  // Calendario compilato da solo: "Modifica" in alto apre l'elenco partite.
  $('previewEdit').hidden = !(previewMode && (kind === 'cal' || kind === 'pxi'));
  $('nextButton').textContent = previewMode ? SEND_LABEL : kind === 'sent' ? 'Rimanda' : (isLastStep() ? 'Anteprima' : 'Avanti ›');

  clearError();
  updateScreenValues();
  applyEyebrows(screenName);
  renderSteps();
  renderProgress();
  syncNav();

  if (animate && screen) {
    if (changedScreen) {
      animateScreenOut(previous,dir,scrollTop);
      animateScreenIn(screen,dir);
    } else if (pendingRefresh) {
      animateScreenIn(screen,0);
    }
  }
  pendingRefresh = false;
  autoFocusCurrent();
  if (!previewMode && (flow.includes('photo') || flow.includes('phasephoto'))) preloadEditorImages();
}

function isLastStep() {
  return flowIndex === flow.length - 1;
}

/* ---------- Option groups ---------- */
// Ricostruisce i bottoni solo se cambiano le opzioni; altrimenti sposta la selezione
// sugli elementi esistenti, così il passaggio radio→radio è animato.
const AUTO_OPTS = new Set(['natKindOpts','natPlayOpts','goalTypeOpts','tableCompOpts','competitionOpts','sideOpts','kitOpts','jrRatioOpts','jrStyleOpts','calMonthOpts','poseOpts','momentOpts']);
function renderOptions(id, options, value, onSelect) {
  const box = $(id);
  box._options = options;
  box._onSelect = onSelect;
  const key = options.map(([v,label,disabled]) => `${v}:${label}:${disabled ? 1 : 0}`).join('|');
  if (box.dataset.key !== key) {
    box.dataset.key = key;
    box.innerHTML = '';
    options.forEach(([v,label,disabled]) => {
      const b = document.createElement('button');
      b.type = 'button';
      b.className = 'opt';
      b.dataset.v = v;
      b.setAttribute('role','radio');
      b.innerHTML = '<span class="radio"></span><span class="opt-label"></span>';
      b.querySelector('.opt-label').textContent = label;
      if (disabled) {
        b.disabled = true;
        b.innerHTML += '<span class="soon">non disponibile</span>';
      } else {
        b.addEventListener('click',() => {
          // Elenchi di una sola scelta: toccata la riga si passa al passaggio dopo (stile Apple).
          const auto = AUTO_OPTS.has(id) && !previewMode;
          if (b.classList.contains('selected')) { if (auto) nextField(true); return; }
          haptic('select');
          box._onSelect(v);
          renderOptions(id,box._options,v,box._onSelect);
          renderSteps();
          if (auto) setTimeout(() => { if (box.offsetParent) nextField(true); }, 180);
        });
      }
      box.appendChild(b);
    });
  }
  box.querySelectorAll('.opt').forEach(b => {
    const on = !b.disabled && b.dataset.v === value;
    b.classList.toggle('selected',on);
    b.setAttribute('aria-checked',on ? 'true' : 'false');
  });
}

function updateScreenValues() {
  renderOptions('competitionOpts',competitionOptions(),competition,v => {
    competition = v;
    // UEFA (fuori da goal/saved): la maglia non si chiede, sfondo della competizione.
    if (!v.startsWith('ita.') && kind !== 'goal' && kind !== 'saved' && kind !== 'xi' && kind !== 'md' && kind !== 'pxi') { kit = 'home'; kitAuto = true; }
    else if (kitAuto) { kit = ''; kitAuto = false; }
    buildFlow();
    refreshSearchSummaries();
  });
  renderOptions('sideOpts',SIDES,side,v => { side = v; updateScreenValues(); });
  $('sideLead').textContent = nat ? 'Dove gioca l’Italia?' : 'Dove gioca la Juventus?';
  if (nat) {
    $('kitTitle').textContent = 'Maglia dell’Italia';
    $('kitLead').textContent = 'Home: grafiche azzurre. Away: grafiche bianche.';
    renderOptions('kitOpts',NAT_KITS,kit,v => { kit = v; });
  } else if (needsShirt()) {
    // Probabile XI UEFA: colori della competizione già decisi, qui solo le foto.
    $('kitTitle').textContent = 'Maglia dei giocatori';
    $('kitLead').textContent = `Colori ${UEFA_THEMES[kit]} già impostati. Scegli la maglia delle foto dei giocatori.`;
    renderOptions('kitOpts',KITS,shirt,v => { shirt = v; });
  } else {
    $('kitTitle').textContent = 'Quale maglia?';
    $('kitLead').textContent = 'Scegli il kit Juventus da usare nella grafica.';
    renderOptions('kitOpts',KITS,kit,v => { kit = v; kitAuto = false; updatePhotoOverlay(); });
  }
  renderJrColor();
  renderOptions('jrRatioOpts',JR_RATIOS,jrb.ratio,v => { jrb.ratio = v; photoState.x = 0; photoState.y = 0; });
  renderOptions('jrStyleOpts',JR_STYLES,jrb.style,v => {
    jrb.style = v;
    if (jrb.cards.length > jrLimit()) {          // meno posti nel nuovo stile: restano le prime foto
      jrb.cards.slice(jrLimit()).forEach(c => { try { URL.revokeObjectURL(c.url); if (c.small) URL.revokeObjectURL(c.small); } catch (_) {} });
      jrb.cards = jrb.cards.slice(0,jrLimit());
      if (!jrb.cards.some(c => c.id === jrb.bg)) jrb.bg = jrb.cards.length === 1 ? jrb.cards[0].id : '';
    }
    jrb.tpls = null; jrb.order = null; jrb.tpl = 0; jrb.swap = -1; jrb.csel = -1;
    buildFlow();
  });
  renderModuleButton();
  renderOptions('tableCompOpts',TABLE_COMPS,tableComp,v => { tableComp = v; });
  renderOptions('calMonthOpts',CAL_MONTHS.map((m,i) => [String(i + 1),m]),String(calMonth || ''),v => { if (calMonth !== Number(v)) calRows = []; calMonth = Number(v); autoCalendar(); });
  renderOptions('poseOpts',POSES,pose,v => pose = v);
  natRender();
  renderOptions('momentOpts',MOMENTS,moment,v => moment = v);
  updatePhaseUI();

  $('playerTitle').textContent = kind === 'saved' ? 'Scegli il portiere' : 'Scegli il giocatore';
  $('playerSearch').placeholder = kind === 'saved' ? 'Cerca portiere…' : 'Cerca giocatore…';

  if (selectedTeam) $('opponentSearch').value = displayTeamName(selectedTeam.name);
  if (selectedPlayer) $('playerSearch').value = selectedPlayer.name;

  const m = currentMatchupNames();
  $('scoreHomeName').textContent = m.home;
  $('scoreAwayName').textContent = m.away;
  $('evHomeName').textContent = m.home;
  $('evAwayName').textContent = m.away;
  $('pensHomeName').textContent = m.home;
  $('pensAwayName').textContent = m.away;
  $('statHomeName').textContent = m.home;
  $('statAwayName').textContent = m.away;
}

function updatePhaseUI() {
  const t = PHASE_TEXT[phase];
  if (t) { $('scoreTitle').textContent = t.title; $('scoreLead').textContent = t.lead; }
  $('pensToggleWrap').classList.toggle('open',phase === 'full');
  $('pensWrap').classList.toggle('open',phase === 'full' && pensOn);
  const b = $('pensToggle');
  b.classList.toggle('selected',pensOn);
  b.setAttribute('aria-checked',pensOn ? 'true' : 'false');
  const e = $('etToggle');
  e.classList.toggle('selected',etOn);
  e.setAttribute('aria-checked',etOn ? 'true' : 'false');
}

function autoFocusCurrent() {
  if (previewMode) return;
  // Risultato: i campi sono solo pulsanti (+/-), il focus su telefono ruberebbe il tocco successivo.
  const inputMap = {
    opponent:'opponentSearch', player:'playerSearch', minute:'minute', natopp:'natOpp', natplayer:'natPlayer'
  };
  const id = inputMap[flow[flowIndex]];
  if (!id) return;
  // Con la lista squadre già visibile, su telefono la tastiera la coprirebbe.
  if (id === 'opponentSearch' && !finePointer) return;
  setTimeout(() => {
    const el = $(id);
    if (!el) return;
    try { el.focus({preventScroll:true}); } catch (_) { el.focus(); }
  }, 140);
}

function haptic(type='select') {
  const h = tg && tg.HapticFeedback;
  if (!h) return;
  try {
    if (type === 'select') h.selectionChanged();
    else if (type === 'error') h.notificationOccurred('error');
    else if (type === 'success') h.notificationOccurred('success');
    else h.impactOccurred('light');
  } catch (_) {}
}

function showError(message) {
  haptic('error');
  const el = $('error');
  el.textContent = message;
  el.style.display = 'block';
  $('stage').scrollTop = 0;
  // Entra dall'alto e fa un piccolo "no" orizzontale, come un campo password sbagliato.
  if (motionOK()) el.animate([
    {opacity:0, transform:'translate3d(0,-4px,0)', offset:0},
    {opacity:1, transform:'translate3d(0,0,0)', offset:.3},
    {transform:'translate3d(-3px,0,0)', offset:.5},
    {transform:'translate3d(2px,0,0)', offset:.7},
    {opacity:1, transform:'none', offset:1}
  ],{duration:360, easing:'ease-out'});
}
function clearError() { $('error').style.display = 'none'; }

const CLOSE_MESSAGE = 'Vuoi chiudere ImageGEN? Il lavoro in corso andrà perso e le foto inviate verranno cancellate dalla chat.';

function askCloseWorkflow() {
  if (tg && typeof tg.showConfirm === 'function') {
    try {
      tg.showConfirm(CLOSE_MESSAGE, ok => { if (ok) closeWorkflow(); });
      return;
    } catch (_) {}
  }
  if (window.confirm(CLOSE_MESSAGE)) closeWorkflow();
}

async function closeWorkflow() {
  clearError();
  setPreviewError('');
  const closeBtn = $('closeWorkflowButton');
  if (closeBtn) closeBtn.disabled = true;

  const payload = JSON.stringify({v:1,action:'close',session});

  if (directBase && session) {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 2500);
    try {
      await fetch(`${directBase}/close`, {
        method:'POST', mode:'cors', cache:'no-store', credentials:'omit', keepalive:true,
        headers:{'Content-Type':'application/json','X-ImageGEN-Session':session},
        body:payload, signal:controller.signal
      });
    } catch (_) {
    } finally { clearTimeout(timer); }
  }

  setTimeout(() => {
    try {
      try { if (tg && typeof tg.disableClosingConfirmation === 'function') tg.disableClosingConfirmation(); } catch (_) {}
      if (tg && typeof tg.close === 'function') { tg.close(); return; }
      window.close();
    } catch (_) {}
    if (closeBtn) closeBtn.disabled = false;
  }, 120);
}

/* ---------- Timer sessione ---------- */
let timerHandle = null;
let expiredShown = false;

/* Ultimi 5 minuti: un tocco nella Mini App allunga la sessione di 5 minuti (servizio:
   Service.extend, fino a 60 minuti in tutto per il limite del workflow GitHub). */
let extending = false;
let limitShown = false;
let sessionMaxAt = 0;     // ora massima della sessione (60 minuti dall'avvio)
// La scadenza nel link è quella iniziale (30 minuti): se la sessione è stata allungata e la
// Mini App si riapre dopo, quella vera arriva dal servizio. Finché non arriva, niente
// "Sessione scaduta"; se arriva ed è ancora attiva, l'errore eventualmente mostrato sparisce.
let sessionChecked = !(directBase && session);
function applySessionInfo(info) {
  if (!info || !Number(info.expires)) return;
  sessionExpiresAt = Number(info.expires);
  if (Number(info.max)) sessionMaxAt = Number(info.max);
  if (!sessionExpired() && expiredShown) {
    expiredShown = false;
    if ($('error').textContent === EXPIRED_MESSAGE) clearError();
    if ($('previewError').textContent === EXPIRED_MESSAGE) setPreviewError('');
    $('nextButton').disabled = false;
  }
  updateSessionTimer();
  if (!timerHandle && !sessionExpired()) timerHandle = setInterval(updateSessionTimer,1000);
}
async function maybeExtendSession() {
  if (!sessionExpiresAt || !directBase || !session || extending) return;
  const left = sessionExpiresAt - Date.now();
  if (left <= 0 || left > 300000) return;
  extending = true;
  try {
    const response = await netFetch(`${directBase}/extend`,{
      method:'POST', headers:{'Content-Type':'application/json','X-ImageGEN-Session':session},
      body:JSON.stringify({v:1, action:'extend', session})
    }, 20000);
    const body = await response.json().catch(() => ({}));
    if (!response.ok || !body.ok) return;
    applySessionInfo(body);
    if (body.extended) haptic('success');
    else if (!limitShown && body.max && body.expires >= body.max - 1000) {
      limitShown = true;
      showError('Limite di 60 minuti raggiunto: dopo la scadenza riavvia ImageGen dal workflow.');
    }
  } catch (_) {
  } finally {
    extending = false;
  }
}
// Tocco sul cronometro: popup per portare subito la sessione al massimo.
const clock = ms => new Date(ms).toLocaleTimeString('it-IT',{hour:'2-digit',minute:'2-digit'});
function openTimeSheet() {
  if (!sessionExpiresAt || sessionExpired()) return;
  haptic('select');
  const atMax = !sessionMaxAt || sessionExpiresAt >= sessionMaxAt - 60000;
  $('tmTitle').textContent = atMax ? 'Tempo massimo' : 'Più tempo';
  $('tmText').textContent = atMax
    ? `La sessione dura già il massimo (60 minuti dall’avvio): scade alle ${clock(sessionExpiresAt)}.`
    : `Porto la sessione al massimo? Scadrà alle ${clock(sessionMaxAt)} invece che alle ${clock(sessionExpiresAt)}.`;
  $('tmCancel').textContent = atMax ? 'OK' : 'Annulla';
  $('tmGo').hidden = atMax;
  $('tmBtns').classList.toggle('one', atMax);
  $('tmGo').disabled = false;
  $('tmOv').classList.add('open');
}
function closeTimeSheet() { $('tmOv').classList.remove('open'); }
async function extendToMax() {
  $('tmGo').disabled = true;
  try {
    const response = await netFetch(`${directBase}/extend`,{
      method:'POST', headers:{'Content-Type':'application/json','X-ImageGEN-Session':session},
      body:JSON.stringify({v:1, action:'extend', session, to_max:true})
    }, 20000);
    const body = await response.json().catch(() => ({}));
    if (!response.ok || !body.ok) throw new Error(body.error || 'Non riesco ad allungare la sessione.');
    applySessionInfo(body);
    haptic('success');
    closeTimeSheet();
  } catch (error) {
    closeTimeSheet();
    showError(error && error.name !== 'AbortError' && error.message ? error.message : 'Non riesco ad allungare la sessione. Riprova.');
  }
}
$('sessionTimer').addEventListener('click', openTimeSheet);
$('sessionTimer').addEventListener('keydown', e => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); openTimeSheet(); } });
// Il popup è in fondo alla pagina (dopo questo script): i tocchi si leggono dal documento.
document.addEventListener('click', e => {
  if (e.target.closest('#tmCancel')) closeTimeSheet();
  else if (e.target.closest('#tmGo')) extendToMax();
  else if (e.target.id === 'tmOv') closeTimeSheet();
});

// Qualsiasi tocco o tasto negli ultimi 5 minuti conta.
document.addEventListener('pointerdown',() => { maybeExtendSession(); },{capture:true, passive:true});
document.addEventListener('keydown',() => { maybeExtendSession(); },{capture:true});

function updateSessionTimer() {
  const box = $('sessionTimer');
  if (!sessionExpiresAt) { box.classList.add('hidden'); return; }
  const left = Math.max(0,Math.ceil((sessionExpiresAt - Date.now()) / 1000));
  box.classList.remove('hidden');
  box.classList.toggle('warn',left > 0 && left <= 120);
  box.classList.toggle('over',left <= 0);
  $('sessionTimerText').textContent = left > 0
    ? `${Math.floor(left / 60)}:${String(left % 60).padStart(2,'0')}`
    : 'Scaduta';
  if (left <= 0) {
    clearInterval(timerHandle);
    timerHandle = null;
    if (!sessionChecked) { $('sessionTimerText').textContent = '…'; return; }
    if (!expiredShown) {
      expiredShown = true;
      $('nextButton').disabled = true;
      if (previewMode) setPreviewError(EXPIRED_MESSAGE);
      else showError(EXPIRED_MESSAGE);
    }
  }
}
