/* Mini App ImageGen JR. File caricati in ordine da index.html: l'ordine conta. */
/* ---------- Calendario: griglia del mese ---------- */
// Una partita per giorno: tocco sul giorno (o sulla riga dell'elenco) -> pannello dal basso
// con avversario (ricerca) e Casa/Trasferta.
const CAL_DOW = ['domenica','lunedì','martedì','mercoledì','giovedì','venerdì','sabato'];
let calEdit = null;   // {day, team, side, isNew} mentre il pannello è aperto

function calYearMonth() { return [Number($('calYear').value) || new Date().getFullYear(), calMonth || 1]; }
function calTeam(name) { return teams.find(t => t.name === name) || findTeamByName(name) || null; }

function renderCalRows() {
  const [y, m] = calYearMonth();
  const last = new Date(y, m, 0).getDate();
  $('calTitle').textContent = `${CAL_MONTHS[m - 1]} ${y}`;
  const byDay = new Map(calRows.map(r => [Number(r.day), r]));
  const grid = $('calGrid');
  grid.innerHTML = '';
  for (let i = 0; i < (new Date(y, m - 1, 1).getDay() + 6) % 7; i++) grid.appendChild(document.createElement('span'));
  for (let d = 1; d <= last; d++) {
    const row = byDay.get(d);
    const b = document.createElement('button');
    b.type = 'button';
    b.className = 'cal-day' + (row ? ' has' : '') + (calEdit && calEdit.day === d ? ' sel' : '');
    b.setAttribute('aria-label', row ? `${d}: ${displayTeamName(row.team)}, ${row.side === 'home' ? 'casa' : 'trasferta'}` : `${d}: aggiungi partita`);
    if (row) {
      b.innerHTML = `<span class="n">${d}</span><span class="logo"></span><span class="tag">${row.side === 'home' ? 'CASA' : 'TRASF.'}</span>`;
      fillLogo(b.querySelector('.logo'), calTeam(row.team));
    } else b.textContent = String(d);
    b.addEventListener('click', () => { haptic('select'); openCalSheet(d); });
    grid.appendChild(b);
  }
  $('calClear').hidden = !calRows.length;
  $('calSummary').textContent = calRows.length ? `${calRows.length} / ${CAL_MAX} partite` : 'Nessuna partita: tocca un giorno per aggiungerla.';
}

function openCalSheet(day) {
  const [y, m] = calYearMonth();
  const row = calRows.find(r => Number(r.day) === day);
  calEdit = {day, team: row ? row.team : '', side: row ? row.side : 'home', isNew: !row};
  const w = CAL_DOW[new Date(y, m - 1, day).getDay()];
  $('calShTitle').textContent = `${w.charAt(0).toUpperCase()}${w.slice(1)} ${day} ${CAL_MONTHS[m - 1].toLowerCase()}`;
  $('calShQ').value = row ? displayTeamName(row.team) : '';
  $('calShDel').hidden = !row;
  $('calShDel').parentElement.classList.toggle('solo', !row);
  $('calShErr').textContent = '';
  calSheetSync();
  $('calOv').classList.add('open');
  renderCalRows();
  if (!row) setTimeout(() => $('calShQ').focus(), 50);
}

function closeCalSheet() {
  if (!calEdit) return;
  calEdit = null;
  $('calOv').classList.remove('open');
  if ($('calShQ') === document.activeElement) $('calShQ').blur();
  if (flow[flowIndex] === 'calrows') renderCalRows();
}

function calSheetSync() {
  fillLogo($('calShLogo'), calEdit.team ? calTeam(calEdit.team) : null);
  $('calSh').querySelectorAll('.cal-seg button').forEach(b => {
    const on = b.dataset.side === calEdit.side;
    b.classList.toggle('on', on);
    b.setAttribute('aria-checked', on ? 'true' : 'false');
  });
  const box = $('calShSug');
  box.innerHTML = '';
  const q = $('calShQ').value;
  if (!norm(q) || (calEdit.team && norm(displayTeamName(calEdit.team)) === norm(q))) return;
  searchTeams(teams, q).slice(0, 4).forEach(team => {
    const b = document.createElement('button');
    b.type = 'button';
    b.innerHTML = '<span class="logo"></span><span></span>';
    b.lastChild.textContent = displayTeamName(team.name);
    fillLogo(b.firstChild, team);
    b.addEventListener('click', () => {
      calEdit.team = team.name;
      $('calShQ').value = displayTeamName(team.name);
      $('calShErr').textContent = '';
      calSheetSync();
    });
    box.appendChild(b);
  });
}

function initCalendarSheet() {
  $('calShQ').addEventListener('input', () => {
    const q = norm($('calShQ').value);
    const exact = teams.find(t => namesFor(t).some(n => norm(n) === q));
    calEdit.team = exact ? exact.name : '';
    $('calShErr').textContent = '';
    calSheetSync();
  });
  $('calSh').querySelectorAll('.cal-seg button').forEach(b => b.addEventListener('click', () => {
    calEdit.side = b.dataset.side; haptic('select'); calSheetSync();
  }));
  $('calShSave').addEventListener('click', () => {
    if (!calEdit.team) { $('calShErr').textContent = 'Scegli l’avversario dall’elenco.'; return; }
    if (calEdit.isNew && calRows.length >= CAL_MAX) { $('calShErr').textContent = `Al massimo ${CAL_MAX} partite.`; return; }
    calRows = calRows.filter(r => Number(r.day) !== calEdit.day);
    calRows.push({day: String(calEdit.day), team: calEdit.team, side: calEdit.side});
    calRows.sort((a, b) => a.day - b.day);
    haptic('success');
    clearError();
    closeCalSheet();
    renderSteps();
  });
  $('calShDel').addEventListener('click', () => {
    calRows = calRows.filter(r => Number(r.day) !== calEdit.day);
    closeCalSheet();
    renderSteps();
  });
  $('calShClose').addEventListener('click', closeCalSheet);
  $('calOv').addEventListener('click', e => { if (e.target === $('calOv')) closeCalSheet(); });
  $('calClear').addEventListener('click', () => { calRows = []; haptic('light'); renderCalRows(); renderSteps(); });
}

/* ---------- Liste incollate (Starting XI e Probabili) ---------- */
// Formati accettati:
//   "Juventus (3-4-1-2): Vicario; Gatti, Bremer, Lucumì; ...; Woltemade, Kolo Muani ⚪️⚫️"
//   un giocatore per riga, con o senza numero ("25 Vicario", "Vicario 25").
// ";" separa i reparti, "," i giocatori dello stesso reparto (da sinistra a destra).
// Cognomi sulla grafica e nella ricerca; il nome completo serve solo per la rosa.
const SHORT_NAMES = {nicolas_gonzalez:'Nico Gonzalez', douglas_luiz:'Douglas Luiz', randal_kolo_muani:'Kolo Muani',
  khephren_thuram_ulien:'Thuram', neto_murara:'Neto', lloyd_casius_kelly:'Kelly', pape_matar_sarr:'Sarr', juan_david_cabal:'Cabal'};
const shirtBook = {};              // slug -> numero (data/shirt_numbers.json, anche giocatori fuori rosa)
let xiPicks = [];                  // [{name, label, number, player}]
let pxiRead = [];
let pxiModuleManual = false;

function surnameOf(p) {
  if (!p) return '';
  if (SHORT_NAMES[p.slug]) return SHORT_NAMES[p.slug];
  const words = String(p.name || '').split(/\s+/);
  const singles = (p.aliases || []).filter(a => !a.includes('.') && !a.trim().includes(' '));
  for (const a of singles) { const w = words.find(w => norm(w) === norm(a)); if (w) return w; }
  return singles[singles.length - 1] || words[words.length - 1] || p.name;
}

const slugOf = name => norm(name).replace(/ /g,'_');

// Giocatore della rosa dal testo scritto: nome, alias o cognome (accenti e maiuscole non contano).
function findPlayer(text) {
  const q = norm(text);
  if (!q) return null;
  const keys = p => [p.name, surnameOf(p), ...(p.aliases || [])].map(norm);
  const exact = players.filter(p => keys(p).includes(q));
  if (exact.length === 1) return exact[0];
  const byWord = players.filter(p => norm(p.name).split(' ').includes(q) || norm(p.name).endsWith(' ' + q));
  return byWord.length === 1 ? byWord[0] : null;
}

function cleanName(text) {
  const t = text.replace(/\s+/g,' ').trim();
  return t === t.toLowerCase() || t === t.toUpperCase()
    ? t.toLowerCase().replace(/(^|[\s'-])\p{L}/gu, m => m.toUpperCase()) : t;
}

// Testo -> {module, groups:[[{label, number}]]}
function parseFormation(raw) {
  let text = String(raw || '').replace(/\r/g,'');
  // Messaggi inoltrati ("📲 X - _Morik92_" / formazione / "Apri X"): resta solo la formazione.
  // Formazione su una riga (reparti separati da ;): si tiene la riga più lunga con almeno due ;.
  // Altrimenti via le righe che non sono giocatori: link, @account, 📲, "Apri …",
  // "X - …" / "Instagram - …" e nomi tra _trattini bassi_.
  const rawRows = text.split('\n');
  const semi = rawRows.filter(l => (l.match(/;/g) || []).length >= 2);
  if (semi.length) text = semi.reduce((a,b) => b.length > a.length ? b : a);
  else text = rawRows.filter(l => !/https?:\/\/|www\.|@\w|📲|^\W*apri\b|^\W*(x|twitter|instagram|ig|telegram|tiktok|facebook)\s*[-–—:|]|_[^_\s][^_]*_/i.test(l)).join('\n');
  const mod = text.match(/\b(\d(?:\s*-\s*\d){2,4})\b/);
  const module = mod ? mod[1].replace(/\s/g,'') : '';
  // Via l'intestazione ("Lecce Juve:", "🎯 UFFICIALE Juventus (3-4-1-2):") e le parentesi.
  if (/[;,]/.test(text)) text = text.replace(/^[^;,\n]*:\s*/,'');
  text = text.replace(/\([^)]*\)/g,' ');
  const single = !/[;,]/.test(text);
  // Reparti separati da ; oppure uno per riga con le virgole ("Gatti, Bremer, Lucumi").
  let lines = /;/.test(text) ? text.split(/[;\n]/) : text.split('\n');
  if (single) {
    // Un giocatore per riga: via punti elenco e righe vuote; un numero da solo
    // su una riga va col nome della riga dopo ("25" + "Vicario G.").
    const rows = lines.map(l => l.replace(/^[\s*•·\-–—>]+/,'').trim()).filter(Boolean);
    lines = [];
    for (let i = 0; i < rows.length; i++) {
      if (/^\d{1,2}\.?$/.test(rows[i]) && rows[i + 1] && !/^\d/.test(rows[i + 1])) { lines.push(`${rows[i]} ${rows[i + 1]}`); i++; }
      else lines.push(rows[i]);
    }
  }
  const groups = [];
  lines.forEach(line => {
    const parts = (single ? [line] : line.split(',')).map(part => {
      if (/:\s*$/.test(part.trim())) return null;                       // "Juventus:", "Panchina:"
      const clean = part.replace(/[^\p{L}\p{N}\s'’.\-]/gu,' ').replace(/\s+/g,' ').replace(/^[\s.\-]+/,'').trim();
      if (!clean) return null;
      const m = clean.match(/^(\d{1,2})[\s.)-]+(.+)$/) || clean.match(/^(.+?)\s+(\d{1,2})$/);
      let number = '', label = clean;
      if (m) { if (/^\d/.test(m[1])) { number = m[1]; label = m[2]; } else { label = m[1]; number = m[2]; } }
      // Via le iniziali del nome: "Vicario G." / "G. Vicario" -> "Vicario".
      label = label.replace(/\s+\p{L}\.$/u,'').replace(/^\p{L}\.\s+/u,'').replace(/[.\-\s]+$/,'').trim();
      return label && /\p{L}/u.test(label) ? {label, number:number ? String(Number(number)) : ''} : null;
    }).filter(Boolean);
    if (parts.length) groups.push(parts);
  });
  return {module, groups};
}

function numberFor(player, label) {
  if (player && player.number) return String(player.number);
  const slug = player ? player.slug : slugOf(label);
  return shirtBook[slug] ? String(shirtBook[slug]) : '';
}

function readXiText() {
  const {groups} = parseFormation($('xiText').value);
  const old = new Map(xiPicks.map(r => [r.name, r.number]));
  xiPicks = groups.flat().slice(0,11).map(({label, number}) => {
    const player = findPlayer(label);
    const name = player ? player.name : cleanName(label);
    return {name, player, label:player ? surnameOf(player) : cleanName(label),
            number:number || old.get(name) || numberFor(player, label)};
  });
  renderXiParsed();
}

function renderXiParsed() {
  const box = $('xiParsed');
  box.innerHTML = '';
  xiPicks.forEach(r => {
    const row = document.createElement('button');
    row.type = 'button';
    row.className = 'parsed-row' + (r.number ? '' : ' miss') + (r.player ? '' : ' new');
    row.innerHTML = '<span class="pr-num"></span><span class="pr-name"></span><span class="pr-role"></span>';
    row.querySelector('.pr-num').textContent = r.number || '?';
    row.querySelector('.pr-name').textContent = r.label.toUpperCase();
    row.querySelector('.pr-role').textContent = r.player ? '' : 'nuovo';
    row.addEventListener('click', async () => {
      const n = await askNumber(r.label, r.number);
      if (n !== null) { r.number = n; renderXiParsed(); }
    });
    box.appendChild(row);
  });
  updateLineupSummary();
  renderSteps();
}

function lineupRows() { return xiPicks.filter(p => p.name); }

function updateLineupSummary() {
  const n = lineupRows().length;
  const miss = xiPicks.filter(r => !r.number).length;
  $('lineupSummary').textContent = `${n} / 11 giocatori` + (miss ? ` · ${miss} senza numero (tocca per scriverlo)` : '');
}

// Numeri: quelli noti arrivano dal repository (data/shirt_numbers.json); quelli
// scritti qui valgono subito e all'invio il server li salva nel repository.
function rememberShirts() {
  lineupRows().forEach(r => {
    if (!/^\d{1,2}$/.test(r.number)) return;
    if (r.player) r.player.number = Number(r.number);
    shirtBook[r.player ? r.player.slug : slugOf(r.name)] = Number(r.number);
  });
}

// Popup: "Che numero ha X?" -> stringa o null (annullato).
function askNumber(label, current='') {
  return new Promise(resolve => {
    const box = $('ask'), input = $('askInput');
    $('askText').textContent = `Che numero ha ${label}?`;
    input.value = current || '';
    box.classList.add('open');
    setTimeout(() => input.focus(), 50);
    const done = value => {
      box.classList.remove('open');
      $('askForm').onsubmit = null; $('askCancel').onclick = null; input.oninput = null;
      resolve(value);
    };
    input.oninput = () => { input.value = input.value.replace(/\D/g,'').slice(0,2); };
    $('askForm').onsubmit = e => { e.preventDefault(); if (/^\d{1,2}$/.test(input.value)) { haptic('select'); done(String(Number(input.value))); } };
    $('askCancel').onclick = () => done(null);
  });
}

async function askMissingNumbers() {
  for (const r of xiPicks) {
    if (r.number) continue;
    const n = await askNumber(r.label);
    if (n === null) { renderXiParsed(); return false; }
    r.number = n;
  }
  renderXiParsed();
  return true;
}

// Probabili: il modulo è quello scritto (es. "(3-4-1-2)"), altrimenti si ricava dai reparti.
// Probabile formazione della Juventus da Gazzetta o Sky Sport (servizio:
// probabili_web.py): riempie il campo come se fosse incollata, poi si può correggere.
async function loadPxiSource(btn) {
  const src = btn.dataset.src;
  clearError();
  if (!directBase || !session) { showError('Sessione vecchia. Riavvia ImageGen dal workflow.'); return; }
  const all = [...document.querySelectorAll('.src-row .btn')];
  all.forEach(b => { b.disabled = true; b.classList.toggle('loading', b === btn); });
  // Mentre carica il pulsante toccato resta sbiadito (.loading): nessuna scritta.
  try {
    const response = await netFetch(`${directBase}/probabili?session=${encodeURIComponent(session)}&source=${encodeURIComponent(src)}`,{}, 60000, 1);
    const body = await response.json().catch(() => ({}));
    if (!response.ok || !body.ok) throw new Error(body.error || 'Formazione non trovata.');
    const lineup = body.lineup;
    $('pxiText').value = lineup.text;
    pxiModuleManual = false;            // vale il modulo del sito
    readPxiText();
    all.forEach(b => b.classList.toggle('on', b === btn));
    $('pxiSrcHint').textContent = '';     // il pulsante evidenziato basta: niente riepilogo
    if (lineup.updated) btn.querySelector('.src-upd').textContent = lineup.updated.replace(' ', ' · ');
    haptic('success');
  } catch (err) {
    $('pxiSrcHint').textContent = '';
    showError(err && err.message ? err.message : 'Formazione non trovata.');
  } finally {
    all.forEach(b => { b.disabled = false; b.classList.remove('loading'); });
  }
}

// Pulsanti dei siti: compaiono solo se il sito parla della partita scelta (stesso avversario).
// Qui anche giorno e ora dell'ultimo aggiornamento, sotto ogni pulsante.
let pxiInfoAt = 0, pxiInfoBusy = false;   // ultima lettura dei siti (si rilegge dopo 1 minuto)
let pxiInfo = null;       // {updated:{sito:'gg/mm hh:mm'}, opponents:{sito:'Genoa'}} dal servizio
function sameTeam(siteName, team) {
  const a = stripNoise(norm(siteName));
  if (!a || !team) return false;
  // Nome italiano e alias; il nome originale solo se non ha traduzione (come nella ricerca:
  // "FC Inter Milan" non deve combaciare con "Milan").
  const shown = displayTeamName(team.name);
  const names = [shown,...(team.aliases || [])];
  if (norm(shown) === norm(team.name)) names.push(team.name);
  const words = v => ` ${v} `;
  return names.map(n => stripNoise(norm(n))).filter(Boolean).some(b =>
    a === b || (Math.min(a.length,b.length) >= 4 && (words(b).includes(words(a)) || words(a).includes(words(b)))));
}
function updatePxiSources() {
  const row = $('srcRow');
  if (!row) return;
  let shown = 0;
  row.querySelectorAll('.btn').forEach(b => {
    const src = b.dataset.src;
    const ok = Boolean(pxiInfo && selectedTeam && sameTeam(pxiInfo.opponents && pxiInfo.opponents[src],selectedTeam));
    b.hidden = !ok;
    if (!ok) b.classList.remove('on');
    if (ok) shown++;
    const when = ok && pxiInfo.updated && pxiInfo.updated[src];
    b.querySelector('.src-upd').textContent = when ? when.replace(' ', ' · ') : '';
  });
  row.hidden = !shown;
}
async function loadPxiUpdates() {
  updatePxiSources();
  if (pxiInfoBusy || (pxiInfo && Date.now() - pxiInfoAt < 60000) || !directBase || !session) return;
  pxiInfoBusy = true;
  try {
    const response = await netFetch(`${directBase}/probabili_info?session=${encodeURIComponent(session)}`,{}, 60000, 1);
    const body = await response.json().catch(() => ({}));
    if (!response.ok || !body.ok) throw new Error();
    pxiInfo = {updated:body.updated || {}, opponents:body.opponents || {}};
    pxiInfoAt = Date.now();
    updatePxiSources();
  } catch (_) {
    // si riprova alla prossima apertura della schermata
  } finally { pxiInfoBusy = false; }
}

/* ---------- Scelta modulo: pannello dal basso (5 colonne), + per crearne, Elimina ---------- */
const rolesOf = m => { try { return ((pxiLay.layouts[m] || {}).roles) || PXI_ROLES[m] || []; } catch (_) { return PXI_ROLES[m] || []; } };

// I moduli stanno tutti in data/probabili_layouts.json: la lista si aggiorna da lì.
function syncModules() {
  const all = pxiLay.layouts, keys = Object.keys(all);
  if (!keys.length) return;
  keys.sort((a,b) => a[0] - b[0]);                 // per difesa (3, 4, 5), poi l'ordine del file
  PXI_MODULES = keys.map(m => [m, m]);
  PXI_ROLES = Object.fromEntries(keys.map(m => [m, all[m].roles || PXI_ROLES[m] || []]));
  if (!PXI_ROLES[pxiModule]) pxiModule = keys[0];
  renderModuleButton();
}

// Mini campo: portiere in basso, attacco in alto, file e margini a distanza uguale.
function modPitch(name) {
  const rows = [1, ...String(name).split('-').map(Number)], n = rows.length, top = 18;
  let dots = '';
  rows.forEach((k,i) => {
    const y = top + (n - 1 - i) * (100 - 2 * top) / (n - 1);
    for (let j = 0; j < k; j++) dots += `<circle cx="${(j + 1) * 100 / (k + 1)}" cy="${y}" r="5"/>`;
  });
  return `<svg viewBox="0 0 100 100" aria-hidden="true">${dots}</svg>`;
}

// "451", "4 5 1" o "4-5-1" -> "4-5-1" se sono 10 giocatori di movimento, altrimenti ''.
function normMod(text) {
  const d = String(text).match(/\d/g) || [], n = d.map(Number);
  return n.length >= 2 && n.length <= 6 && n.every(x => x > 0) && n.reduce((a,b) => a + b, 0) === 10 ? d.join('-') : '';
}

function renderModuleButton() {
  const box = $('moduleOpts');
  if (!box) return;
  box.innerHTML = `<button type="button" class="mod-btn">${pxiModule ? modPitch(pxiModule) : ''}<span><b>${pxiModule ? 'Modulo' : 'Scegli il modulo'}</b></span><em>${pxiModule || ''}</em><i>›</i></button>`;
  box.firstChild.addEventListener('click',openModSheet);
}

let modEdit = false, modArmed = '';
async function openModSheet() {
  haptic('select');
  await loadLayouts();
  syncModules();
  modEdit = false; modArmed = '';
  renderModSheet();
  $('modOv').classList.add('open');
}
const closeModSheet = () => $('modOv').classList.remove('open');

function modPost(action, module) {
  return netFetch(`${directBase}/layout`,{
    method:'POST', headers:{'Content-Type':'application/json','X-ImageGEN-Session':session},
    body:JSON.stringify({v:1, action, session, module})
  }, 30000).then(async r => {
    const body = await r.json().catch(() => ({}));
    if (!r.ok || !body.ok) throw new Error(body.error || 'Operazione non riuscita.');
    return body.layout;
  });
}

function renderModSheet(adding = false) {
  const sh = $('modSh');
  sh.innerHTML = `<div class="mod-bar"></div><div class="mod-top"><b>Modulo</b><button type="button" id="modEditBtn">${modEdit ? 'Fine' : 'Elimina'}</button></div>`
    + `<div class="mod-grid">${PXI_MODULES.map(([m]) => `<button type="button" class="mod-tile${m === pxiModule ? ' on' : ''}${modEdit ? ' del' : ''}${modArmed === m ? ' armed' : ''}" data-m="${m}">${modPitch(m)}<span>${modArmed === m ? 'Elimina?' : m}</span></button>`).join('')}`
    + `<button type="button" class="mod-tile add" id="modAdd"><span class="plus">+</span><span>Nuovo</span></button></div>`
    + `<div class="mod-new${adding ? ' open' : ''}" id="modNew"><span id="modPrev"></span><input id="modIn" inputmode="numeric" maxlength="11" placeholder="Es. 451" autocomplete="off"><button type="button" id="modOk" disabled>Aggiungi</button><div class="err" id="modErr"></div></div>`;
  $('modEditBtn').addEventListener('click',() => { modEdit = !modEdit; modArmed = ''; renderModSheet(); });
  sh.querySelectorAll('.mod-tile[data-m]').forEach(b => b.addEventListener('click',async () => {
    const m = b.dataset.m;
    if (!modEdit) { pxiModule = m; pxiModuleManual = true; haptic('select'); closeModSheet(); readPxiText(); return; }
    if (modArmed !== m) { modArmed = m; renderModSheet(); return; }   // secondo tocco: conferma
    try {
      await modPost('module_delete', m);
      delete pxiLay.layouts[m];
      modArmed = '';
      if (pxiModule === m) { pxiModuleManual = false; pxiModule = ''; }
      syncModules(); readPxiText(); renderModSheet();
    } catch (err) { modArmed = ''; renderModSheet(); $('modErr').textContent = err.message; $('modNew').classList.add('open'); }
  }));
  $('modAdd').addEventListener('click',() => { modEdit = false; renderModSheet(true); $('modIn').focus(); });
  const input = $('modIn'), ok = $('modOk');
  input.addEventListener('input',() => {
    const name = normMod(input.value);
    $('modPrev').innerHTML = name ? modPitch(name) : '';
    $('modErr').textContent = input.value && !name ? 'Servono 10 giocatori di movimento (es. 4-5-1).' : '';
    ok.disabled = !name;
  });
  ok.addEventListener('click',async () => {
    ok.disabled = true;
    try {
      const made = await modPost('module_add', input.value);
      pxiLay.layouts[made.module] = made.layout;
      pxiModule = made.module; pxiModuleManual = true;
      syncModules(); closeModSheet(); readPxiText(); haptic('success');
    } catch (err) { $('modErr').textContent = err.message; ok.disabled = false; }
  });
}

function readPxiText() {
  const {module, groups} = parseFormation($('pxiText').value);
  const flat = groups.flat().slice(0,11);
  if (!pxiModuleManual) {
    const fromLines = groups.length > 2 ? groups.slice(1).map(g => g.length).join('-') : '';
    // Elenco senza reparti (un giocatore per riga): resta il modulo scelto.
    pxiModule = PXI_ROLES[module] ? module : PXI_ROLES[fromLines] ? fromLines : pxiModule;
  }
  // Le formazioni incollate elencano ogni reparto da destra a sinistra (prima il
  // terzino destro); nella grafica i ruoli vanno da sinistra a destra (TS … TD).
  // Si divide l'elenco nei reparti del modulo (portiere, poi 4-3-3 → 4, 3, 3)
  // e si legge ogni reparto al contrario.
  const sizes = pxiModule ? [1, ...pxiModule.split('-').map(Number)] : [];
  let ordered = flat;
  if (sizes.length > 1) {
    ordered = [];
    let at = 0;
    sizes.forEach(n => { ordered.push(...flat.slice(at, at + n).reverse()); at += n; });
    ordered.push(...flat.slice(at));
  }
  pxiRead = ordered.map(({label}) => {
    const player = findPlayer(label);
    return {player, label:player ? surnameOf(player) : cleanName(label)};
  });
  pxiPicks = pxiRead.map(r => r.player ? r.player.name : '');
  renderModuleButton();
  const roles = rolesOf(pxiModule);
  const box = $('pxiParsed');
  box.innerHTML = '';
  pxiRead.forEach((r,i) => {
    const row = document.createElement('div');
    row.className = 'parsed-row' + (r.player ? '' : ' new');
    row.innerHTML = '<span class="pr-num pr-role"></span><span class="pr-name"></span><span class="pr-role"></span>';
    row.children[0].textContent = roles[i] || '';
    row.children[1].textContent = r.label.toUpperCase();
    row.children[2].textContent = r.player ? '' : 'non in rosa';
    box.appendChild(row);
  });
  $('pxiSummary').textContent = `${pxiRead.length} / 11 giocatori`;
  renderSteps();
}
