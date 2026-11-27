/* Mini App ImageGen JR. File caricati in ordine da index.html: l'ordine conta. */
/* ---------- CAMBIO (SUB / SUBS) ----------
   La stessa grafica del LiveScore: chi entra sopra (IN), chi esce sotto (OUT).
   Tre passi semplici, ognuno una lista da toccare:
   1. "Chi esce": si toccano i giocatori (1, 2, 3… nell'ordine dei tocchi);
   2. "Chi entra": stesso ordine, in alto si vede al posto di chi entra il prossimo;
   3. "Minuto": il minuto e il riepilogo, dove si tocca un giocatore per correggere il numero.
   Da 1 a 5 cambi. Niente è spuntato all'inizio. Numeri dalla rosa o dai numeri
   salvati; quelli che mancano si chiedono (e il servizio li salva). Con + un giocatore fuori rosa
   (es. Primavera). Il minuto va solo nel testo del messaggio. */
const subMax = () => 5;
let subIns = [], subOuts = [];                  // [{name, label, number, player}] nell'ordine dei tocchi
const SUB_IDS = {out:['subOutSearch','subOutSummary','subOutList'], in:['subInSearch','subInSummary','subInList']};

function subReset() {
  subIns = []; subOuts = [];
  ['subMinute','subOutSearch','subInSearch'].forEach(id => { $(id).value = ''; });
}

// Il tema dipende dalla maglia solo in Serie A: le coppe hanno i loro colori, le amichevoli il grigio.
const subNeedsKit = () => competition === 'ita.1';

const subEntry = player => ({name:player.name, label:surnameOf(player), number:numberFor(player, player.name), player});
const subList = side => side === 'in' ? subIns : subOuts;
const subChosen = name => [...subIns, ...subOuts].some(e => e.name === name);

function subToggle(entry, side) {
  const list = subList(side);
  const at = list.findIndex(e => e.name === entry.name);
  clearError();
  if (at >= 0) {
    list.splice(at, 1);
    if (side === 'out') subIns.splice(at, 1);       // via anche chi entrava al suo posto
  } else if (side === 'out' && list.length >= subMax()) {
    showError(`Al massimo ${subMax()} cambi.`); return;
  } else if (side === 'in' && list.length >= subOuts.length) {
    showError(`Escono in ${subOuts.length}: hai già scelto chi entra per tutti.`); return;
  } else list.push(entry);
  haptic('select');
  renderSubList(side);
}

const SUB_ARROW = {
  in:'<svg viewBox="0 0 24 24" width="14" height="14" aria-hidden="true"><path d="M12 5l7 12H5z" fill="currentColor"/></svg>',
  out:'<svg viewBox="0 0 24 24" width="14" height="14" aria-hidden="true"><path d="M12 19L5 7h14z" fill="currentColor"/></svg>'
};

// Rosa in ordine di numero di maglia (chi non ce l'ha in fondo), senza chi è già dall'altra parte;
// i fuori rosa scelti restano in cima.
function subPool(side) {
  const other = subList(side === 'in' ? 'out' : 'in');
  const num = p => Number(numberFor(p, p.name)) || 999;
  const roster = players.filter(p => !other.some(e => e.name === p.name))
    .sort((a, b) => num(a) - num(b) || a.name.localeCompare(b.name, 'it'));
  const guests = subList(side).filter(e => !e.player).map(e => ({name:e.name, aliases:[], guest:e}));
  return [...guests, ...roster];
}

function renderSubList(side) {
  const [searchId, summaryId, listId] = SUB_IDS[side];
  const list = subList(side);
  const q = $(searchId).value;
  const items = playersLoaded ? searchItems(subPool(side), q) : [];
  const box = $(listId);
  box.innerHTML = '';
  items.forEach(item => {
    const at = list.findIndex(e => e.name === item.name);
    const entry = at >= 0 ? list[at] : item.guest || subEntry(item);
    const row = document.createElement('button');
    row.type = 'button';
    row.className = 'result sub-row' + (at >= 0 ? ` on ${side}` : '');
    row.setAttribute('aria-pressed', at >= 0 ? 'true' : 'false');
    row.innerHTML = '<span class="res-main"><span class="sub-num"></span><span class="res-name"></span></span>' +
      '<span class="sub-for"></span><span class="sub-badge"></span>';
    row.querySelector('.sub-num').textContent = entry.number || '';
    row.querySelector('.res-name').textContent = item.name;
    if (at >= 0) row.querySelector('.sub-badge').textContent = String(at + 1);
    if (at >= 0 && side === 'in' && subOuts[at]) row.querySelector('.sub-for').textContent = `per ${subOuts[at].label}`;
    row.addEventListener('click', () => subToggle(entry, side));
    box.appendChild(row);
  });
  const n = list.length;
  $(summaryId).textContent = !playersLoaded ? 'Caricamento giocatori…'
    : norm(q) && !items.length ? 'Nessun risultato.'
    : side === 'out' ? (n ? `Escono ${n}` : `${items.length} giocatori`)
    : `Entrano ${n} su ${subOuts.length}`;
  if (side === 'out') $('subMax').textContent = String(subMax());
  else renderSubNext();
  renderSteps();
}

// "Chi entra": in alto al posto di chi entra il prossimo che tocchi.
function renderSubNext() {
  const box = $('subNext');
  const next = subOuts[subIns.length];
  box.classList.toggle('done', !next);
  if (!next) { box.textContent = subIns.length === 1 ? 'Fatto: 1 cambio' : `Fatto: ${subIns.length} cambi`; return; }
  box.innerHTML = `${SUB_ARROW.out}<span>Chi entra al posto di <b></b>?</span>`;
  box.querySelector('b').textContent = `${next.number ? next.number + ' ' : ''}${next.name}`;
}

// "Minuto": riepilogo dei cambi, sopra chi entra e sotto chi esce. Tocco: numero di maglia.
function renderSubPairs() {
  const box = $('subPairs');
  box.innerHTML = '';
  subIns.forEach((inn, i) => {
    const pair = document.createElement('div');
    pair.className = 'sub-pair';
    pair.innerHTML = '<span class="sp-n"></span><div class="sp-rows"></div>';
    pair.querySelector('.sp-n').textContent = String(i + 1);
    [['in', inn], ['out', subOuts[i]]].forEach(([side, e]) => {
      if (!e) return;
      const row = document.createElement('button');
      row.type = 'button';
      row.className = `sp-row ${side}` + (e.number ? '' : ' miss');
      row.innerHTML = `<span class="sp-ico">${SUB_ARROW[side]}</span><span class="sp-num"></span><span class="sp-name"></span>`;
      row.querySelector('.sp-num').textContent = e.number || '?';
      row.querySelector('.sp-name').textContent = e.name;
      row.addEventListener('click', async () => {
        const v = await askNumber(e.label, e.number);
        if (v !== null) { e.number = v; renderSubPairs(); }
      });
      pair.querySelector('.sp-rows').appendChild(row);
    });
    box.appendChild(pair);
  });
}

function subEnter(step) {
  if (step === 'submin') { renderSubPairs(); return; }
  const side = step === 'subin' ? 'in' : 'out';
  if (!playersLoaded) loadCatalogs().then(() => renderSubList(side)); else renderSubList(side);
}

// Giocatore fuori rosa: nome scritto a mano (il numero si chiede dopo).
function askGuest(side) {
  return new Promise(resolve => {
    const box = document.createElement('div');
    box.className = 'ask open';
    box.setAttribute('role', 'dialog');
    box.innerHTML = `<form class="ios-alert"><div class="ia-body"><h2>${side === 'in' ? 'Entra' : 'Esce'} un fuori rosa</h2><p>Nome e cognome come vuoi che compaia.</p>` +
      '<label class="ia-field"><input type="text" maxlength="30" autocomplete="off" autocapitalize="words" spellcheck="false" enterkeyhint="done" placeholder="Nome e cognome"></label></div>' +
      '<div class="ia-btns"><button type="button">Annulla</button><button type="submit" class="ia-main">Aggiungi</button></div></form>';
    const input = box.querySelector('input');
    const done = value => { box.remove(); resolve(value); };
    box.querySelector('button[type=button]').onclick = () => done(null);
    box.querySelector('form').onsubmit = e => {
      e.preventDefault();
      const name = input.value.replace(/\s+/g, ' ').trim();
      if (!name) { input.focus(); return; }
      haptic('select');
      done(name);
    };
    document.body.appendChild(box);
    setTimeout(() => input.focus(), 50);
  });
}

async function addGuest(side) {
  const name = await askGuest(side);
  if (!name) return;
  const hit = findPlayer(name);
  const entry = hit ? subEntry(hit) : {name:cleanName(name), label:cleanName(name), number:numberFor(null, name), player:null};
  if (subChosen(entry.name)) { showError(`${entry.name} è già nei cambi.`); return; }
  if (!entry.number) {
    const v = await askNumber(entry.label);
    if (v === null) return;
    entry.number = v;
  }
  subToggle(entry, side);
}

// Prima di andare avanti: i numeri che mancano.
async function askSubNumbers(step) {
  const side = step === 'subin' ? 'in' : 'out';
  for (const e of subList(side)) {
    if (e.number) continue;
    const v = await askNumber(e.label);
    if (v === null) { renderSubList(side); return false; }
    e.number = v;
  }
  renderSubList(side);
  return true;
}

const subNumberOk = list => {
  const bad = list.find(e => !/^\d{1,2}$/.test(e.number) || Number(e.number) < 1);
  if (bad) showError(`Manca il numero di maglia di ${bad.label}.`);
  return !bad;
};

function subValidate(step) {
  if (step === 'subout') {
    if (!subOuts.length) { showError('Tocca chi esce.'); return false; }
    if (subOuts.length > subMax()) { showError(`Al massimo ${subMax()} cambi.`); return false; }
    return subNumberOk(subOuts);
  }
  if (step === 'subin') {
    if (subIns.length < subOuts.length) { showError(`Manca chi entra al posto di ${subOuts[subIns.length].label}.`); return false; }
    return subNumberOk(subIns);
  }
  const v = $('subMinute').value.trim();
  if (!v) { showError('Inserisci il minuto.'); return false; }
  if (!/^\d{1,3}(?:\+\d{1,2})?$/.test(v)) { showError('Formato minuto non valido. Esempi: 67, 45+2, 90+5.'); return false; }
  if (!subNumberOk([...subIns, ...subOuts])) return false;
  // I numeri scritti valgono subito anche per le prossime grafiche (il servizio li salva all'invio).
  [...subIns, ...subOuts].forEach(e => {
    if (e.player) e.player.number = Number(e.number);
    shirtBook[e.player ? e.player.slug : slugOf(e.name)] = Number(e.number);
  });
  return true;
}

function subPayload() {
  return subIns.map((inn, i) => ({out:{name:subOuts[i].name, number:subOuts[i].number}, in:{name:inn.name, number:inn.number}}));
}

function subStepValue(step) {
  if (step === 'submin') { const min = $('subMinute').value.trim(); return min ? `${min}'` : ''; }
  const list = subList(step === 'subin' ? 'in' : 'out');
  return list.length > 2 ? `${list.length} giocatori` : list.map(e => e.label).join(', ');
}

// "Modifica" dagli Ultimi invii.
const subSnapshot = () => ({ins:subIns.map(e => [e.name, e.number]), outs:subOuts.map(e => [e.name, e.number]), minute:$('subMinute').value});
function subRestore(snap) {
  const back = ([name, number]) => {
    const player = players.find(p => p.name === name) || null;
    return {name, label:player ? surnameOf(player) : name, number:String(number || ''), player};
  };
  subIns = (snap.ins || []).map(back);
  subOuts = (snap.outs || []).map(back);
  $('subMinute').value = snap.minute || '';
}

['out', 'in'].forEach(side => $(SUB_IDS[side][0]).addEventListener('input', () => renderSubList(side)));
document.querySelectorAll('.sub-guest').forEach(b => b.addEventListener('click', () => { haptic('select'); addGuest(b.dataset.side); }));
$('subMinute').addEventListener('input', renderSteps);
$('subQuick').addEventListener('click', event => {
  const b = event.target.closest('button[data-v]');
  if (!b) return;
  const input = $('subMinute');
  input.value = b.dataset.v;
  input.focus({preventScroll:true});
  try { input.setSelectionRange(input.value.length, input.value.length); } catch (_) {}
  renderSteps();
});
