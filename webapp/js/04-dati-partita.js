/* Mini App ImageGen JR. File caricati in ordine da index.html: l'ordine conta. */
/* ---------- Validation ---------- */
function validateScoreValue(id, optional=false) {
  const raw = $(id).value.trim();
  if (raw === '' && optional) return true;
  if (raw === '') { showError('Inserisci un valore.'); return false; }
  const value = Number(raw);
  if (!Number.isInteger(value) || value < 0 || value > 99) {
    showError('Inserisci un numero valido da 0 a 99.');
    return false;
  }
  return true;
}

function validateCurrent() {
  const step = flow[flowIndex];
  if (!natValidate(step)) return false;

  const choice = {competition, side, kit, pose, phase, moment, jrcolor:jrColor, module:pxiModule, mdpick:mdPick, jrstyle:jrb.style, tablecomp:tableComp, tableview:tableView, iqmode:iq.mode};
  if (step in choice && !choice[step]) { showError('Seleziona un’opzione per continuare.'); return false; }

  if (step === 'kit' && needsShirt() && !shirt) { showError('Scegli la maglia dei giocatori.'); return false; }
  if (step === 'opponent') return resolveTeam();
  if (step === 'player') return resolvePlayer();

  if (step === 'minute') {
    ['evHomeScore','evAwayScore'].forEach(id => { if (!$(id).value.trim()) $(id).value = '0'; });
    if (!(validateScoreValue('evHomeScore') && validateScoreValue('evAwayScore'))) return false;
    const v = $('minute').value.trim();
    if (!v) { showError('Inserisci il minuto.'); return false; }
    if (!/^\d{1,3}(?:\+\d{1,2})?$/.test(v)) {
      showError('Formato minuto non valido. Esempi: 45, 45+2, 90+5.');
      return false;
    }
  }

  if (step === 'score') {
    // Campo svuotato a mano = 0, come il valore di partenza.
    ['homeScore','awayScore'].forEach(id => { if (!$(id).value.trim()) $(id).value = '0'; });
    if (!(validateScoreValue('homeScore') && validateScoreValue('awayScore'))) return false;
    if (phase === 'full' && pensOn) {
      return validateScoreValue('homePens') && validateScoreValue('awayPens');
    }
  }

  if (step === 'lineup') {
    const rows = lineupRows();
    if (rows.length !== 11) { showError(`Servono 11 giocatori (ora ${rows.length}).`); return false; }
    if (new Set(rows.map(r => r.name)).size !== 11) { showError('Lo stesso giocatore compare due volte.'); return false; }
    const bad = rows.find(r => !/^\d{1,2}$/.test(r.number));
    if (bad) { showError(`Manca il numero di maglia di ${bad.label}.`); return false; }
    rememberShirts();
  }

  if (step === 'mdpick' && !mdPick) { showError('Scegli una partita o “Altra partita”.'); return false; }

  if (step === 'match') {
    if (!$('matchStadium').value.trim()) { showError('Scrivi lo stadio.'); return false; }
    if (!/^([01]?\d|2[0-3])[:.][0-5]\d$/.test($('matchTime').value.trim())) { showError('Inserisci l’orario (es. 20:45).'); return false; }
    if (!$('matchDate').value) { showError('Scegli la data.'); return false; }
  }

  if (step === 'jrphotos') {
    if (jrb.uploading) { showError('Attendi il caricamento delle foto.'); return false; }
    if (jrb.cards.length < jrMin()) { showError(jrMin() > 1 ? `Scegli almeno ${jrMin()} foto.` : 'Scegli almeno una foto.'); return false; }
    if (jrb.cards.length > jrLimit()) { showError(`Per questo stile al massimo ${jrLimit()} foto: scegli di nuovo.`); return false; }
  }
  if (step === 'jrcolor' && $('jrcHexBox').classList.contains('bad')) { showError('Il colore non è valido: servono 6 cifre esadecimali, per esempio #FF3366.'); return false; }
  if (step === 'jrbg' && !jrb.cards.some(c => c.id === jrb.bg)) { showError('Scegli la foto per lo sfondo.'); return false; }

  if (step === 'photo') {
    if (photoState.uploading) { showError('Attendi il caricamento della foto.'); return false; }
    if (!photoState.id) { showError('Scegli una foto.'); return false; }
  }

  if (step === 'phasephoto') {
    if (ppState.uploading) { showError('Attendi il caricamento della foto.'); return false; }
    if (!ppState.bg) { showError('Scegli una foto.'); return false; }
  }

  if (step === 'jrtitle' && !jrb.title.trim()) { showError('Scrivi il titolo.'); return false; }
  if (step === 'iqshot' && !iq.photos.length) { showError('Allega lo screenshot della storia.'); return false; }
  if (step === 'iqpick' && iq.sel < 0) { showError('Tocca la foto da usare.'); return false; }
  if (step === 'iqtext' && !iq.story && !$('iqText').value.trim()) { showError('Scrivi il testo della citazione.'); return false; }
  if (step === 'iqtext' && iq.story && !$('iqHandle').value.trim() && !$('iqName').value.trim()) { showError('Scrivi il @account della storia.'); return false; }
  if (step === 'igcontent') {
    if (igb.uploading) { showError('Attendi il caricamento della foto.'); return false; }
    if (!$('igText').value.trim() && !igb.id) { showError('Scrivi un testo o scegli una foto.'); return false; }
  }

  if (step === 'calmonth') {
    if (!calMonth) { showError('Scegli il mese.'); return false; }
    const y = Number($('calYear').value);
    if (!Number.isInteger(y) || y < 2000 || y > 2100) { showError('Anno non valido.'); return false; }
  }

  if (step === 'calrows') {
    if (!calRows.length) { showError('Aggiungi almeno una partita.'); return false; }
    const last = new Date(Number($('calYear').value), calMonth, 0).getDate();
    const bad = calRows.find(r => !(Number.isInteger(Number(r.day)) && r.day >= 1 && r.day <= last) || !r.team);
    if (bad) { showError(`Completa ogni partita: giorno da 1 a ${last} e avversario.`); return false; }
  }

  if (step === 'convlist' && !convValidate()) return false;

  if (step === 'xi11') {
    const n = pxiRead.length;
    if (n !== 11) { showError(`Servono 11 giocatori (ora ${n}).`); return false; }
    const unknown = isFriendly() ? null : pxiRead.find(r => !r.player);   // amichevoli: chiunque
    if (unknown) { showError(`${unknown.label} non è nella rosa: serve la sua foto.`); return false; }
    if (new Set(pxiPicks).size !== 11) { showError('Lo stesso giocatore compare due volte.'); return false; }
    if (!pxiModule) { showError('Scegli il modulo.'); return false; }
    const keeper = pxiRead[0].player;
    if (keeper && keeper.role !== 'goalkeeper') { showError(`Il primo deve essere il portiere (ora ${keeper.name}).`); return false; }
  }

  if (step === 'squad') {
    const n = squadNames().length;
    if (!n) { showError('Incolla almeno un giocatore.'); return false; }
    if (n > 30) { showError('Massimo 30 giocatori.'); return false; }
  }

  if (step === 'stats') {
    collectStats();
    let bad = null, any = false;
    statRowEls().forEach((r,i) => {
      const {home,away} = statRows[STATS[i]];
      r.classList.remove('bad');
      if (home || away) any = true;
      if (!home !== !away) { r.classList.add('bad'); bad = bad || r; }
    });
    if (bad) {
      showError('Inserisci entrambi i valori oppure lascia la riga vuota.');
      bad.scrollIntoView({block:'center',behavior:'auto'});
      return false;
    }
    if (!any) { showError('Inserisci almeno una statistica.'); return false; }
  }
  return true;
}

async function nextField(validate=true) {
  clearError();

  if (previewMode) { submitPreviewGraphic(); return; }

  if (validate) {
    const step = flow[flowIndex];
    if ((step === 'opponent' && !teamsLoaded) || ((step === 'player' || step === 'convlist') && !playersLoaded) ||
        (step === 'calmonth' && !teamsLoaded)) {
      await loadCatalogs();
      refreshSearchSummaries();
    }
    if (step === 'lineup' && !(await askMissingNumbers())) return;
    if (step === 'convlist' && !(await askConvNames())) return;
    if (step === 'iqurl' && !(await iqLoad())) return;
    if (!validateCurrent()) return;
  }

  if (kind === 'sent') { if (flow[flowIndex] === 'sentitem') resendRecent(); return; }
  if (flowIndex >= flow.length - 1) { previewGraphic(); return; }
  flowIndex += 1;
  renderFlow();
}

function previousField() {
  clearError();

  if (previewMode) {
    if (kind === 'cal') flowIndex = Math.max(0, flow.indexOf('calmonth'));
    closePreview();
    return;
  }

  if (flowIndex <= 0) { if (!LIVE) goHome(); return; }
  flowIndex -= 1;
  renderFlow();
}

/* ---------- Stats ---------- */
function statRowEls() { return [...$('statRows').querySelectorAll('.stat-row')]; }

function buildStatRows() {
  const box = $('statRows');
  box.innerHTML = '';
  STATS.forEach(label => {
    const [ph,pa] = STAT_PLACEHOLDERS[STAT_TYPES[label] || 'int'];
    const name = label === 'xG' ? 'xG' : label.charAt(0) + label.slice(1).toLowerCase();
    const row = document.createElement('div');
    row.className = 'stat-row';
    row.innerHTML = '<input inputmode="decimal" enterkeyhint="next" autocomplete="off"><label></label><input inputmode="decimal" enterkeyhint="next" autocomplete="off">';
    const [h,l,a] = row.children;
    h.placeholder = ph;
    a.placeholder = pa;
    l.textContent = name;
    h.setAttribute('aria-label',`${name} casa`);
    a.setAttribute('aria-label',`${name} trasferta`);
    box.appendChild(row);
  });
}

function collectStats() {
  let n = 0;
  statRowEls().forEach((r,i) => {
    const [h,a] = r.querySelectorAll('input');
    const home = h.value.trim(), away = a.value.trim();
    statRows[STATS[i]] = {home,away};
    const filled = !!(home || away);
    r.classList.toggle('filled',filled);
    if (filled) n++;
    if (home && away) r.classList.remove('bad');
  });
  $('statCount').textContent = `${n} / ${STATS.length} voci`;
  return n;
}

/* ---------- Calendario Juventus (ESPN, tramite il workflow) ---------- */
// Nomi completi delle competizioni (mai abbreviati).
const COMP_SHORT = {'ita.1':'Serie A','ita.coppa_italia':'Coppa Italia','ita.super_cup':'Supercoppa Italiana',
  'uefa.champions':'Champions League','uefa.europa':'Europa League','uefa.europa.conf':'Conference League',
  'uefa.super_cup':'Supercoppa UEFA','fifa.cwc':'Mondiale per Club','club.friendly':'Amichevole'};
const MONTHS_SHORT = ['gen','feb','mar','apr','mag','giu','lug','ago','set','ott','nov','dic'];
const isoDay = d => new Date(d.getTime() - d.getTimezoneOffset() * 60000).toISOString().slice(0,10);

async function fetchFixtures(from, to) {
  if (!directBase || !session) return [];
  const url = `${directBase}/fixtures?session=${encodeURIComponent(session)}&from=${from}&to=${to}`;
  const response = await netFetch(url, {method:'GET'}, 30000);
  const body = await response.json().catch(() => ({}));
  return response.ok && body.ok ? (body.matches || []) : [];
}

function fixtureLabel(m, short=false) {
  const [y,mo,d] = m.date.split('-').map(Number);
  const who = displayTeamName(m.opponent || m.opponent_espn);
  const where = m.side === 'home' ? 'in casa' : 'in trasferta';
  return short ? `${d} ${MONTHS_SHORT[mo - 1]} · ${who}`
    : `${d} ${MONTHS_SHORT[mo - 1]} · ${m.time} · ${who} (${where}) · ${COMP_SHORT[m.competition] || m.competition}`;
}

const WEEKDAYS = ['dom','lun','mar','mer','gio','ven','sab'];

function fixtureCard(m) {
  const b = document.createElement('button');
  b.type = 'button';
  b.className = 'fx-card' + (mdPick === m.id ? ' selected' : '');
  const team = teams.find(t => t.name === m.opponent);
  const [y,mo,d] = m.date.split('-').map(Number);
  const day = WEEKDAYS[new Date(y, mo - 1, d).getDay()];
  b.innerHTML = `<span class="logo fx-logo"></span>
    <span class="fx-main"><span class="fx-team"></span>
      <span class="fx-when"></span><span class="fx-info"></span></span>`;
  b.querySelector('.fx-team').textContent = displayTeamName(m.opponent || m.opponent_espn);
  b.querySelector('.fx-when').textContent = `${day} ${d} ${MONTHS_SHORT[mo - 1]} · ${m.time}`;
  b.querySelector('.fx-info').textContent =
    `${COMP_SHORT[m.competition] || m.competition} · ${m.side === 'home' ? 'Casa' : 'Trasferta'} · ${m.stadium || 'stadio da inserire'}`;
  fillLogo(b.querySelector('.fx-logo'), team || null);
  if (!team) { b.disabled = true; b.title = 'Logo squadra mancante nel catalogo'; }
  else if (!competitionOptions().some(([v]) => v === m.competition)) { b.disabled = true; b.title = 'Competizione non prevista per questa grafica'; }
  b.addEventListener('click', async () => { haptic('select'); await pickMdFixture(m.id); if (flow[flowIndex] === 'mdpick') nextField(true); });
  return b;
}

// Due elenchi: prossime partite (pre-gara) e partite di oggi/già giocate (dalla più recente).
const fixtureCache = {}, fixtureAt = {}, fixtureJobs = {};
const FIXTURE_TTL = 300000;     // 5 minuti: poi si riscarica in silenzio
const fixtureMode = () => PREMATCH.includes(kind) ? 'next' : 'past';

// Un solo caricamento alla volta per elenco; se fallisce restano le partite già scaricate.
function getFixtures(mode, force=false) {
  const fresh = fixtureCache[mode] && fixtureCache[mode].length && Date.now() - (fixtureAt[mode] || 0) < FIXTURE_TTL;
  if (fresh && !force) return Promise.resolve(fixtureCache[mode]);
  if (fixtureJobs[mode]) return fixtureJobs[mode];
  fixtureJobs[mode] = (async () => {
    const today = new Date();
    const day = n => isoDay(new Date(today.getTime() + n * 86400000));
    try {
      const rows = (mode === 'next' ? await fetchFixtures(day(0), day(60)) : await fetchFixtures(day(-30), day(0)))
        .filter(m => COMP_SHORT[m.competition]);
      if (rows.length) { fixtureCache[mode] = mode === 'next' ? rows : rows.reverse(); fixtureAt[mode] = Date.now(); }
    } catch (_) {}
    fixtureJobs[mode] = null;
    return fixtureCache[mode] || [];
  })();
  return fixtureJobs[mode];
}

// All'apertura: partite in arrivo e già giocate partono in background.
function prefetchFixtures() {
  if (LIVE || !directBase || !session) return;
  getFixtures('next'); getFixtures('past');
}

function renderMdFixtures(mode) {
  fixtureList = fixtureCache[mode] || [];
  $('mdPickHint').textContent = fixtureList.length ? '' : 'Calendario non disponibile: usa “A mano”.';
  const box = $('mdPickOpts');
  box.innerHTML = '';
  const shown = fixtureList.slice(0,10);
  const today = isoDay(new Date());
  [['Oggi', shown.filter(m => m.date === today)],
   [mode === 'next' ? 'Prossime' : 'Giocate', shown.filter(m => m.date !== today)]].forEach(([title, ms]) => {
    if (!ms.length) return;
    const h = document.createElement('div'); h.className = 'lst-head'; h.textContent = title; box.appendChild(h);
    const g = document.createElement('div'); g.className = 'lst'; ms.forEach(m => g.appendChild(fixtureCard(m))); box.appendChild(g);
  });
}

async function loadMdFixtures() {
  const mode = fixtureMode();
  const stale = fixtureCache[mode] && fixtureCache[mode].length;
  if (!stale) {
    $('mdPickHint').textContent = 'Carico le partite…';
    $('mdPickOpts').innerHTML = '';
  } else renderMdFixtures(mode);       // subito quelle già pronte
  const before = fixtureCache[mode];
  await getFixtures(mode);
  if (mode !== fixtureMode() || flow[flowIndex] !== 'mdpick') return;     // nel frattempo è cambiato altro
  if (!stale || fixtureCache[mode] !== before) renderMdFixtures(mode);
}

/* ---------- Squad List: convocati letti da juventus.com ---------- */
// Il servizio legge gli articoli "I convocati" della prima squadra (GET /convocati);
// un tocco compila partita (competizione, campo, avversario) e giocatori.
let squadSite = [];
let squadSiteAt = 0;

function findTeamByName(name) {
  const q = norm(name);
  if (!q) return null;
  return teams.find(t => namesFor(t).some(n => norm(n) === q))
    || teams.find(t => namesFor(t).some(n => { const v = norm(n); return v.startsWith(`${q} `) || q.startsWith(`${v} `); }))
    || null;
}

function siteDateLabel(iso) {
  const [y,mo,d] = String(iso || '').split('-').map(Number);
  return y ? `${WEEKDAYS[new Date(y, mo - 1, d).getDay()]} ${d} ${MONTHS_SHORT[mo - 1]}` : '';
}

function siteCard(m) {
  const b = document.createElement('button');
  b.type = 'button';
  b.className = 'fx-card' + (mdPick === `site:${m.id}` ? ' selected' : '');
  const opp = findTeamByName(m.opponent);
  b.innerHTML = `<span class="logo fx-logo"></span>
    <span class="fx-main"><span class="fx-team"></span><span class="fx-when"></span><span class="fx-info"></span></span>`;
  fillLogo(b.querySelector('.fx-logo'), opp || {name:m.side === 'home' ? m.away : m.home});
  b.querySelector('.fx-team').textContent = `${displayTeamName(m.home)} – ${displayTeamName(m.away)}`;
  b.querySelector('.fx-when').textContent = siteDateLabel(m.date);
  let info = `${COMP_SHORT[m.competition] || m.competition_label || 'Competizione'} · ${m.players.length} convocati`;
  if (!opp) { b.disabled = true; info += ' · squadra non nel catalogo'; }
  else if (!competitionOptions().some(([v]) => v === m.competition)) { b.disabled = true; info += ' · competizione non prevista'; }
  b.querySelector('.fx-info').textContent = info;
  b.addEventListener('click',() => { haptic('select'); pickSquadSite(m); });
  return b;
}

function renderSquadSite() {
  const box = $('mdPickOpts');
  box.innerHTML = '';
  squadSite.forEach(m => box.appendChild(siteCard(m)));
}

// Lettura dei convocati da juventus.com (o da un link incollato). Lancia se non riesce.
async function fetchSquadSite(link) {
  const url = `${directBase}/convocati?session=${encodeURIComponent(session)}` + (link ? `&url=${encodeURIComponent(link)}` : '');
  const response = await netFetch(url, {method:'GET'}, 60000);
  const body = await response.json().catch(() => ({}));
  if (!response.ok || !body.ok) throw new Error(body.error || 'Convocati non disponibili.');
  if (link) {
    squadSite = [...body.items, ...squadSite.filter(x => !body.items.some(n => n.id === x.id))]
      .sort((a, b) => String(b.published).localeCompare(String(a.published)));
  } else { squadSite = body.items; squadSiteAt = Date.now(); }
  return body.items;
}

const squadSiteFresh = () => squadSite.length && Date.now() - squadSiteAt < 120000;
let squadSiteJob = null;

// Appena si tocca "Squad List": i convocati si cercano mentre si apre la schermata.
function prefetchSquadSite() {
  if (LIVE || !directBase || !session || squadSiteFresh() || squadSiteJob) return;
  squadSiteJob = fetchSquadSite('').catch(() => {}).finally(() => { squadSiteJob = null; });
}

async function loadSquadSite(link) {
  const hint = $('mdPickHint');
  if (!link && squadSiteFresh()) { hint.textContent = ''; renderSquadSite(); return; }
  if (!directBase || !session) { hint.textContent = 'Sessione vecchia. Riavvia ImageGen dal workflow.'; renderSquadSite(); return; }
  hint.textContent = link ? 'Leggo l’articolo…' : 'Cerco i convocati su juventus.com…';
  if (!link) $('mdPickOpts').innerHTML = '';
  try {
    if (!link && squadSiteJob) { await squadSiteJob; if (!squadSiteFresh()) await fetchSquadSite(''); }
    else await fetchSquadSite(link);
    hint.textContent = '';
  } catch (err) {
    hint.textContent = `${err && err.message ? err.message : 'Convocati non disponibili.'} Usa “Link” in alto per incollare l’articolo o scegli “Altra partita”.`;
  }
  if (kind === 'squad' && flow[flowIndex] === 'mdpick') renderSquadSite();
}

/* Link manuale: pannello dal basso, incolli l'URL e parte subito la grafica. */
const SQUAD_URL_OK = /^https:\/\/www\.juventus\.com\/(?:it|en)\/news\/articoli\/[\w\-./%]+$/;
let lnkBusy = false;
function openLinkSheet() {
  haptic('select');
  $('lnkErr').textContent = '';
  $('lnkIn').value = '';
  $('lnkGo').disabled = true;
  $('lnkOv').classList.add('open');
  setTimeout(() => $('lnkIn').focus(), 80);
}
const closeLinkSheet = () => $('lnkOv').classList.remove('open');

async function submitLink() {
  if (lnkBusy) return;
  const err = $('lnkErr'), btn = $('lnkGo');
  const link = $('lnkIn').value.trim();
  err.textContent = '';
  const fail = msg => { err.textContent = msg; haptic('error'); };
  if (!link) return fail('Incolla il link dell’articolo.');
  if (!SQUAD_URL_OK.test(link)) return fail('Link non valido: serve un articolo dei convocati su juventus.com.');
  if (!directBase || !session) return fail('Sessione vecchia. Riavvia ImageGen dal workflow.');
  lnkBusy = true; btn.disabled = true; btn.textContent = 'Leggo…';
  try {
    const items = await fetchSquadSite(link);
    const m = items && items[0];
    if (!m) throw new Error('Articolo non valido: servono i convocati della prima squadra.');
    if (!findTeamByName(m.opponent)) throw new Error('Squadra avversaria non presente nel catalogo.');
    if (!competitionOptions().some(([v]) => v === m.competition)) throw new Error('Competizione non prevista per la Squad List.');
    closeLinkSheet();
    pickSquadSite(m);          // compila tutto e passa dritto all'anteprima
  } catch (e) {
    fail(e && e.message ? e.message : 'Link non valido.');
  } finally {
    lnkBusy = false; btn.textContent = 'Genera'; btn.disabled = !$('lnkIn').value.trim();
  }
}

function pickSquadSite(m) {
  mdPick = `site:${m.id}`;
  kitFromMatch = false;
  competition = m.competition;
  side = m.side;
  selectedTeam = findTeamByName(m.opponent);
  $('opponentSearch').value = selectedTeam ? displayTeamName(selectedTeam.name) : '';
  $('squadText').value = m.players.join('\n');
  updateSquadSummary();
  buildFlow();
  renderSteps();
  renderFlow();
  // Convocati dal sito: la partita è l'unico passaggio, il tocco porta all'anteprima.
  if (flow[flowIndex] === 'mdpick') nextField(true);
}

// Un tocco: competizione, campo, avversario, stadio, data e ora.
async function matchKit(m) {
  if (!directBase || !session) return '';
  try {
    const url = `${directBase}/kit?session=${encodeURIComponent(session)}&event=${encodeURIComponent(m.id)}&league=${encodeURIComponent(m.competition)}`;
    const body = await (await netFetch(url, {method:'GET'}, 8000)).json();
    return body && body.ok && ['home','away','third'].includes(body.kit) ? body.kit : '';
  } catch (_) { return ''; }
}

async function pickMdFixture(id) {
  mdPick = id;
  const m = fixtureList.find(f => f.id === id);
  kitFromMatch = false;
  // Partite giocate (Goal/Event/Stats): la maglia la dice ESPN.
  if (m && !PREMATCH.includes(kind)) {
    $('mdPickHint').textContent = 'Cerco la maglia della partita…';
    const k = await matchKit(m);
    $('mdPickHint').textContent = '';
    if (mdPick !== id) return;
    if (k) { kit = k; kitAuto = false; kitFromMatch = true; }
  }
  if (m) {
    competition = m.competition;
    side = m.side;
    selectedTeam = teams.find(t => t.name === m.opponent) || null;
    $('opponentSearch').value = selectedTeam ? displayTeamName(selectedTeam.name) : '';
    $('matchStadium').value = m.stadium;
    $('matchTime').value = m.time;
    $('matchDate').value = m.date;
    // Stessa partita dell'ultimo invio: maglia e risultato già messi (11-invii.js).
    if (typeof applyLastChoices === 'function') applyLastChoices(id);
  }
  buildFlow();
  renderSteps();
  renderFlow();
}

// Calendario: tocco sul mese -> partite del mese e anteprima subito.
// "Modifica" nell'anteprima riporta all'elenco delle partite da correggere.
async function autoCalendar() {
  const now = new Date();
  // Stagione: un mese già passato da più di un mese è quello dell'anno dopo.
  $('calYear').value = String(now.getFullYear() + (calMonth < now.getMonth() ? 1 : 0));
  calRows = [];
  await fillCalendarFromFixtures();
  // Niente salto automatico alle partite né all'anteprima: si prosegue con Avanti.
  buildFlow();
  renderFlow();
}

// Calendario: scelto il mese, le partite si compilano da sole (modificabili).
async function fillCalendarFromFixtures() {
  if (calRows.some(r => r.day || r.team)) return;
  const year = Number($('calYear').value), month = calMonth;
  const last = new Date(year, month, 0).getDate();
  const pad = n => String(n).padStart(2,'0');
  $('calSummary').textContent = 'Carico le partite del mese…';
  let found = [];
  try { found = await fetchFixtures(`${year}-${pad(month)}-01`, `${year}-${pad(month)}-${pad(last)}`); } catch (_) {}
  if (calRows.some(r => r.day || r.team)) return;           // nel frattempo modificato a mano
  if (found.length) {
    calRows = found.slice(0, CAL_MAX).map(m => ({day:String(Number(m.date.slice(8))), team:m.opponent || '', side:m.side}));
  }
  renderCalRows();
  renderSteps();
  if (!found.length) $('calSummary').textContent = `${calRows.length} / ${CAL_MAX} partite · nessuna trovata nel calendario`;
}
