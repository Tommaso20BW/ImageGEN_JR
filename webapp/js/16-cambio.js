/* Mini App ImageGen JR. File caricati in ordine da index.html: l'ordine conta. */
/* ---------- CAMBIO (SUB / SUBS) ----------
   La stessa grafica del LiveScore: chi entra sopra (IN), chi esce sotto (OUT), da 1 a 5 cambi.
   Dalla rosa si tocca "Entra" o "Esce": il primo che entra prende il posto del primo che esce, e
   così via. Niente è spuntato all'inizio. Numeri dalla rosa o dai numeri salvati; quelli che
   mancano si chiedono (e il servizio li salva). Con + un giocatore fuori rosa (es. Primavera).
   Il minuto va solo nel testo del messaggio. */
const SUB_MAX = 5;
let subIns = [], subOuts = [];        // [{name, label, number, player}] nell'ordine dei tocchi

function subReset() {
  subIns = []; subOuts = [];
  $('subMinute').value = '';
  $('subSearch').value = '';
}

// Il tema dipende dalla maglia solo in Serie A: le coppe hanno i loro colori, le amichevoli il grigio.
const subNeedsKit = () => competition === 'ita.1';

const subEntry = player => ({name:player.name, label:surnameOf(player), number:numberFor(player, player.name), player});
const subSide = name => subIns.some(e => e.name === name) ? 'in' : subOuts.some(e => e.name === name) ? 'out' : '';

function subToggle(entry, side) {
  const list = side === 'in' ? subIns : subOuts;
  const other = side === 'in' ? subOuts : subIns;
  const at = list.findIndex(e => e.name === entry.name);
  clearError();
  if (at >= 0) list.splice(at, 1);
  else {
    if (list.length >= SUB_MAX) { showError(`Al massimo ${SUB_MAX} cambi.`); return; }
    const was = other.findIndex(e => e.name === entry.name);   // da Esce a Entra (o il contrario)
    if (was >= 0) other.splice(was, 1);
    list.push(entry);
  }
  haptic('select');
  renderSubs();
}

const SUB_ARROW = {
  in:'<svg viewBox="0 0 24 24" width="14" height="14" aria-hidden="true"><path d="M12 5l7 12H5z" fill="currentColor"/></svg>',
  out:'<svg viewBox="0 0 24 24" width="14" height="14" aria-hidden="true"><path d="M12 19L5 7h14z" fill="currentColor"/></svg>'
};

// Riepilogo: una riga per cambio, sopra chi entra e sotto chi esce. Tocco: numero di maglia.
function renderSubPairs() {
  const box = $('subPairs');
  box.innerHTML = '';
  const n = Math.max(subIns.length, subOuts.length);
  box.hidden = !n;
  for (let i = 0; i < n; i++) {
    const pair = document.createElement('div');
    pair.className = 'sub-pair';
    pair.innerHTML = '<span class="sp-n"></span><div class="sp-rows"></div>';
    pair.querySelector('.sp-n').textContent = String(i + 1);
    [['in', subIns[i]], ['out', subOuts[i]]].forEach(([side, e]) => {
      const row = document.createElement(e ? 'button' : 'div');
      row.className = `sp-row ${side}` + (e && !e.number ? ' miss' : '') + (e ? '' : ' empty');
      if (e) row.type = 'button';
      row.innerHTML = `<span class="sp-ico">${SUB_ARROW[side]}</span><span class="sp-num"></span><span class="sp-name"></span>`;
      row.querySelector('.sp-num').textContent = e ? (e.number || '?') : '';
      row.querySelector('.sp-name').textContent = e ? e.name
        : side === 'in' ? 'tocca Entra su un giocatore' : 'tocca Esce su un giocatore';
      if (e) row.addEventListener('click', async () => {
        const v = await askNumber(e.label, e.number);
        if (v !== null) { e.number = v; renderSubs(); }
      });
      pair.querySelector('.sp-rows').appendChild(row);
    });
    box.appendChild(pair);
  }
}

// Rosa in ordine di numero di maglia (chi non ce l'ha in fondo); i fuori rosa scelti restano in cima.
function subPool() {
  const num = p => Number(numberFor(p, p.name)) || 999;
  const roster = players.slice().sort((a, b) => num(a) - num(b) || a.name.localeCompare(b.name, 'it'));
  const guests = [...subIns, ...subOuts].filter(e => !e.player).map(e => ({name:e.name, aliases:[], guest:e}));
  return [...guests, ...roster];
}

function renderSubs() {
  renderSubPairs();
  const q = $('subSearch').value;
  const items = playersLoaded ? searchItems(subPool(), q) : [];
  const box = $('subList');
  box.innerHTML = '';
  items.forEach(item => {
    const entry = item.guest || subEntry(item);
    const side = subSide(item.name);
    const row = document.createElement('div');
    row.className = 'result sub-row' + (side ? ` on-${side}` : '');
    row.innerHTML = '<span class="res-main"><span class="sub-num"></span><span class="res-name"></span></span>' +
      '<span class="sub-btns"><button type="button" class="sub-btn in">Entra</button><button type="button" class="sub-btn out">Esce</button></span>';
    row.querySelector('.sub-num').textContent = entry.number || '';
    row.querySelector('.res-name').textContent = item.name;
    ['in', 'out'].forEach(s => {
      const b = row.querySelector(`.sub-btn.${s}`);
      const list = s === 'in' ? subIns : subOuts;
      const at = list.findIndex(e => e.name === item.name);
      b.classList.toggle('on', at >= 0);
      b.setAttribute('aria-pressed', at >= 0 ? 'true' : 'false');
      if (at >= 0) b.textContent = `${s === 'in' ? 'Entra' : 'Esce'} ${at + 1}`;
      // Stesso oggetto se già scelto: il numero corretto a mano resta.
      b.addEventListener('click', () => subToggle(list[at] || [...subIns, ...subOuts].find(e => e.name === item.name) || entry, s));
    });
    box.appendChild(row);
  });
  const nIn = subIns.length, nOut = subOuts.length;
  $('subSummary').textContent = !playersLoaded ? 'Caricamento giocatori…'
    : norm(q) && !items.length ? 'Nessun risultato.'
    : nIn || nOut ? `Entrano ${nIn} · escono ${nOut}` : `${items.length} giocatori`;
  renderSteps();
}

// Giocatore fuori rosa: nome scritto a mano, poi Entra o Esce (il numero si chiede dopo).
function askGuest() {
  return new Promise(resolve => {
    const box = document.createElement('div');
    box.className = 'ask open';
    box.setAttribute('role', 'dialog');
    box.innerHTML = '<form class="ios-alert"><div class="ia-body"><h2>Fuori rosa</h2><p>Nome e cognome come vuoi che compaia.</p>' +
      '<label class="ia-field"><input type="text" maxlength="30" autocomplete="off" autocapitalize="words" spellcheck="false" enterkeyhint="done" placeholder="Nome e cognome"></label></div>' +
      '<div class="ia-btns"><button type="button" data-v="out">Esce</button><button type="submit" class="ia-main" data-v="in">Entra</button></div>' +
      '<div class="ia-btns one"><button type="button" data-v="">Annulla</button></div></form>';
    const input = box.querySelector('input');
    const done = value => { box.remove(); resolve(value); };
    const pick = side => {
      const name = input.value.replace(/\s+/g, ' ').trim();
      if (!side) { done(null); return; }
      if (!name) { input.focus(); return; }
      haptic('select');
      done({name, side});
    };
    box.querySelectorAll('button[type=button]').forEach(b => { b.onclick = () => pick(b.dataset.v); });
    box.querySelector('form').onsubmit = e => { e.preventDefault(); pick('in'); };
    document.body.appendChild(box);
    setTimeout(() => input.focus(), 50);
  });
}

async function addGuest() {
  const got = await askGuest();
  if (!got) return;
  const hit = findPlayer(got.name);
  const entry = hit ? subEntry(hit) : {name:cleanName(got.name), label:cleanName(got.name), number:numberFor(null, got.name), player:null};
  if (subSide(entry.name)) { showError(`${entry.name} è già nei cambi.`); return; }
  if (!entry.number) {
    const v = await askNumber(entry.label);
    if (v === null) return;
    entry.number = v;
  }
  subToggle(entry, got.side);
}

// Prima di andare avanti: i numeri che mancano.
async function askSubNumbers() {
  for (const e of [...subIns, ...subOuts]) {
    if (e.number) continue;
    const v = await askNumber(e.label);
    if (v === null) { renderSubs(); return false; }
    e.number = v;
  }
  renderSubs();
  return true;
}

function subValidate() {
  const nIn = subIns.length, nOut = subOuts.length;
  if (!nIn && !nOut) { showError('Tocca Entra ed Esce sui giocatori del cambio.'); return false; }
  if (nIn !== nOut) { showError(`Entrano ${nIn} e escono ${nOut}: devono essere uguali.`); return false; }
  const bad = [...subIns, ...subOuts].find(e => !/^\d{1,2}$/.test(e.number) || Number(e.number) < 1);
  if (bad) { showError(`Manca il numero di maglia di ${bad.label}.`); return false; }
  const v = $('subMinute').value.trim();
  if (!v) { showError('Inserisci il minuto.'); return false; }
  if (!/^\d{1,3}(?:\+\d{1,2})?$/.test(v)) { showError('Formato minuto non valido. Esempi: 67, 45+2, 90+5.'); return false; }
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

const subStepValue = () => {
  const n = Math.min(subIns.length, subOuts.length), min = $('subMinute').value.trim();
  return n ? `${n} cambi${n === 1 ? 'o' : ''}${min ? ` · ${min}'` : ''}` : '';
};

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

$('subSearch').addEventListener('input', () => renderSubs());
$('subMinute').addEventListener('input', renderSteps);
$('subManual').addEventListener('click', () => { haptic('select'); addGuest(); });
$('subQuick').addEventListener('click', event => {
  const b = event.target.closest('button[data-v]');
  if (!b) return;
  const input = $('subMinute');
  input.value = b.dataset.v;
  input.focus({preventScroll:true});
  try { input.setSelectionRange(input.value.length, input.value.length); } catch (_) {}
  renderSteps();
});
