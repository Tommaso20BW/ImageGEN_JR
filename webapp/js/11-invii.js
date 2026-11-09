/* Mini App ImageGen JR. File caricati in ordine da index.html: l'ordine conta. */
/* ---------- Ultimi invii e ultime scelte ----------
   - "Ultimi invii" in Home (sezione "Altro"): le ultime grafiche mandate in questa sessione (il
     servizio tiene PNG e miniatura). Elenco, poi la grafica: "Rimanda" (stesso PNG, subito) o
     "Modifica i dati" (riapre la grafica compilata, per correggere minuto, risultato o giocatore).
   - Ultime scelte: per la stessa partita la Mini App ricorda risultato e maglia dell'ultimo
     invio. Scegliendo di nuovo quella partita si ritrovano già messi. */
const SENT_KEY = 'imagegen-jr-sent-v2';       // {items:{message_id: dati per "Modifica"}}, tra le sessioni
const LAST_KEY = 'imagegen-jr-last-v1';       // ultima partita usata: {match, kit, score, at}
const LAST_TTL = 8 * 3600000;                 // le scelte valgono 8 ore (una partita)
let recentItems = [];
let recentPick = null;

const readJson = key => { try { return JSON.parse(localStorage.getItem(key) || 'null'); } catch (_) { return null; } };
const writeJson = (key, value) => { try { localStorage.setItem(key, JSON.stringify(value)); } catch (_) {} };

// Grafiche che "Modifica" sa riaprire: senza foto caricate (quelle restano solo nel servizio).
function editableSnapshot() {
  if (nat) return null;
  if (kind === 'goal' || kind === 'saved') return true;
  return kind === 'match' && (!PHOTO_PHASES.has(phase) || isFriendly());
}

// Dopo un invio riuscito (09-rete.js): dati per "Modifica" e ultime scelte della partita.
function rememberSent(messageId) {
  const ev = [$('evHomeScore').value, $('evAwayScore').value];
  const sc = [$('homeScore').value, $('awayScore').value];
  if (messageId && editableSnapshot()) {
    const saved = readJson(SENT_KEY);
    const store = saved && saved.items ? saved : {items:{}};
    store.items[messageId] = {
      kind, phase, goalType, competition, side, kit, mdPick, kitFromMatch,
      opponent: selectedTeam ? selectedTeam.name : '',
      player: selectedPlayer ? selectedPlayer.name : '',
      typed: $('natPlayer').value, pose, minute: $('minute').value,
      ev, sc, pens: [$('homePens').value, $('awayPens').value], pensOn, etOn,
    };
    const ids = Object.keys(store.items);
    ids.slice(0, Math.max(0, ids.length - 30)).forEach(id => delete store.items[id]);
    writeJson(SENT_KEY, store);
  }
  // Partita del calendario: si ricordano maglia e risultato (dei gol o della fase).
  if (mdPick && mdPick !== 'manual' && !String(mdPick).startsWith('site:')) {
    const score = kind === 'goal' || kind === 'saved' ? ev : kind === 'match' && phase !== 'kick' ? sc : null;
    const last = readJson(LAST_KEY);
    const same = last && last.match === mdPick && Date.now() - last.at < LAST_TTL;
    writeJson(LAST_KEY, {match: mdPick, kit: kit || (same ? last.kit : ''),
      score: score || (same ? last.score : null), at: Date.now()});
  }
}

// Scelta una partita (04-dati-partita.js): se è quella dell'ultimo invio, maglia e risultato tornano.
function applyLastChoices(id) {
  const last = readJson(LAST_KEY);
  if (!last || last.match !== id || Date.now() - last.at > LAST_TTL) return;
  if (!kitFromMatch && !kit && !uefaAuto() && ['home','away','third'].includes(last.kit)) kit = last.kit;
  const untouched = ids => ids.every(i => ['', '0'].includes($(i).value.trim()));
  if (Array.isArray(last.score) && last.score.every(v => /^\d{1,2}$/.test(String(v)))) {
    [['evHomeScore','evAwayScore'], ['homeScore','awayScore']].forEach(([h, a]) => {
      if (untouched([h, a])) { $(h).value = String(last.score[0]); $(a).value = String(last.score[1]); }
    });
  }
}

/* ----- "Ultimi invii" (Home, sezione "Altro"): due pagine come le altre ----- */
// sentlist: elenco delle grafiche inviate; sentitem: la grafica grande, "Rimanda" in basso
// (tasto giallo) e "Modifica i dati" sotto l'immagine.
// Ora dell'invio; se non è di oggi anche il giorno ("ieri 21:30", "2 nov 21:30").
const hhmm = ms => {
  const d = new Date(ms), time = d.toLocaleTimeString('it-IT', {hour:'2-digit', minute:'2-digit'});
  const day = n => { const x = new Date(); x.setHours(0,0,0,0); x.setDate(x.getDate() - n); return x.getTime(); };
  if (ms >= day(0)) return time;
  if (ms >= day(1)) return `ieri ${time}`;
  return `${d.getDate()} ${MONTHS_SHORT[d.getMonth()]} ${time}`;
};
// Sempre due righe (tutte le righe dell'elenco alte uguali): giocatore e minuto; risultato e
// avversario. Senza giocatore (Kick Off, fasi...) "risultato · avversario" sale sulla prima.
// Storia e Citazioni: account (se c'è) e poi l'inizio del testo (`note`).
// Avversario col nome italiano (come nel resto della Mini App); negli invii salvati prima:
// "IG" -> "Instagram" e niente "@" davanti al nome di una persona ("@Alessandro Del Piero").
const sentName = item => String(item.name || '').replace(/ IG$/, ' Instagram');
const sentLines = item => {
  const player = /^@\S+\s/.test(item.player || '') ? item.player.slice(1) : item.player;
  const who = [player, item.minute].filter(Boolean).join(' · ');
  const vs = item.opponent ? displayTeamName(item.opponent) : '';
  const match = item.note || [item.score, vs].filter(Boolean).join(' · ');
  return who ? [who, match] : [match, ''];
};
const sentUrl = (what, id) => `${directBase}/history/${what}?session=${encodeURIComponent(session)}&id=${encodeURIComponent(id)}`;

async function loadRecent() {
  if (LIVE || !directBase || !session) return;
  try {
    const response = await netFetch(`${directBase}/history?session=${encodeURIComponent(session)}`, {}, 15000, 2);
    const body = await response.json().catch(() => ({}));
    if (!response.ok || !body.ok) return;
    recentItems = Array.isArray(body.items) ? body.items : [];
  } catch (_) { return; }
  if (kind === 'sent' && flow[flowIndex] === 'sentlist') renderSentList();
  if (kind === 'igbn' && flow[flowIndex] === 'igsent') renderIgSent();
}

function renderSentList() {
  fillSentRows('sentList', 'sentEmpty', 'sentGroup', item => {
    haptic('select');
    recentPick = item;
    navDir = 1;
    flowIndex = flow.indexOf('sentitem');
    renderFlow();
  });
}

// Righe dell'elenco (miniatura, nome e ora, due righe di dettagli), con l'azione al tocco.
function fillSentRows(listId, emptyId, groupId, onPick) {
  const list = $(listId);
  list.innerHTML = '';
  $(emptyId).hidden = recentItems.length > 0;
  $(groupId).hidden = !recentItems.length;
  recentItems.forEach(item => {
    const b = document.createElement('button');
    b.type = 'button';
    b.className = 'hm-item hm-recent';
    b.innerHTML = '<img class="hm-thumb" alt="" loading="lazy"><span class="hm-txt">' +
      '<span class="hm-top"><span class="hm-name"></span><span class="hm-time"></span></span>' +
      '<span class="hm-desc"></span><span class="hm-desc"></span></span>' +
      '<svg class="hm-go" viewBox="0 0 24 24" aria-hidden="true"><path d="M9 6l6 6-6 6"/></svg>';
    b.querySelector('.hm-thumb').src = sentUrl('thumb', item.id);
    b.querySelector('.hm-name').textContent = sentName(item);
    const [who, match] = sentLines(item);
    const desc = b.querySelectorAll('.hm-desc');
    desc[0].textContent = who || ' ';      // riga vuota: spazio, così l'altezza resta uguale
    desc[1].textContent = match || ' ';
    b.querySelector('.hm-time').textContent = hhmm(item.at);
    b.addEventListener('click', () => onPick(item));
    list.appendChild(b);
  });
}

function renderSentItem() {
  const item = recentPick;
  if (!item) return;
  $('sentTitle').textContent = sentName(item);
  const [who, match] = sentLines(item);
  $('sentLead').textContent = [who, match, `inviata alle ${hhmm(item.at)}`].filter(Boolean).join(' · ');
  $('sentImage').src = sentUrl('image', item.id);
  $('sentEdit').hidden = !sentSnapshot(item.id);
  $('sentNote').textContent = sentSnapshot(item.id)
    ? '“Rimanda” la manda di nuovo uguale. Per cambiare minuto, risultato o giocatore usa “Modifica i dati”.'
    : '“Rimanda” la manda di nuovo uguale. Questa grafica non si può modificare da qui: rifalla dalla Home.';
}

function sentSnapshot(id) {
  const saved = readJson(SENT_KEY);
  return saved && saved.items ? saved.items[id] || null : null;
}

// Tasto giallo "Rimanda" (nextField in 04-dati-partita.js).
async function resendRecent() {
  if (!recentPick) return;
  clearError();
  const next = $('nextButton');
  next.disabled = true;
  next.textContent = 'Invio…';
  syncNav();
  try {
    const response = await netFetch(`${directBase}/resend`, {
      method:'POST', headers:{'Content-Type':'application/json','X-ImageGEN-Session':session},
      body:JSON.stringify({v:1, action:'resend', session, id:recentPick.id})
    }, 90000, 2, true);
    const body = await response.json().catch(() => ({}));
    if (!response.ok || !body.ok) throw new Error(body.error || `Invio non riuscito (${response.status}).`);
    haptic('success');
    next.textContent = 'Inviata ✓';
    setTimeout(() => {
      if (kind !== 'sent') return;
      next.disabled = false;
      navDir = -1;
      flowIndex = 0;
      renderFlow();
      loadRecent();
    }, 900);
  } catch (error) {
    next.disabled = false;
    next.textContent = 'Rimanda';
    showError(sessionExpired() ? EXPIRED_MESSAGE : error && error.name === 'AbortError'
      ? 'ImageGEN non risponde. Controlla la chat del bot: la foto potrebbe essere arrivata.'
      : (error.message || 'Invio non riuscito.'));
  }
}

// Riapre la grafica con i dati dell'invio, sul passo da correggere (minuto o risultato).
async function editRecent() {
  const snap = recentPick && sentSnapshot(recentPick.id);
  if (!snap) return;
  haptic('select');
  if (!playersLoaded || !teamsLoaded) await loadCatalogs();
  navDir = 1;
  nat = false;
  changeKind(snap.kind, true, true, snap.phase || '');
  competition = snap.competition || '';
  side = snap.side || '';
  kit = snap.kit || '';
  goalType = snap.goalType || 'goal';
  mdPick = snap.mdPick || '';
  kitFromMatch = !!snap.kitFromMatch;
  selectedTeam = teams.find(t => t.name === snap.opponent) || null;
  $('opponentSearch').value = selectedTeam ? displayTeamName(selectedTeam.name) : '';
  selectedPlayer = players.find(p => p.name === snap.player) || null;
  $('playerSearch').value = selectedPlayer ? surnameOf(selectedPlayer) : '';
  $('natPlayer').value = snap.typed || '';
  pose = snap.pose || '';
  $('minute').value = snap.minute || '';
  const put = (ids, values) => ids.forEach((id, i) => { $(id).value = values && values[i] != null ? String(values[i]) : $(id).value; });
  put(['evHomeScore','evAwayScore'], snap.ev);
  put(['homeScore','awayScore'], snap.sc);
  put(['homePens','awayPens'], snap.pens);
  pensOn = !!snap.pensOn;
  etOn = !!snap.etOn;
  buildFlow();
  const target = ['minute', 'score'].find(s => flow.includes(s));
  flowIndex = target ? flow.indexOf(target) : flow.length - 1;
  refreshSearchSummaries();
  if (typeof updatePhaseUI === 'function') updatePhaseUI();
  pendingRefresh = true;
  renderFlow();
}
$('sentEdit').addEventListener('click', editRecent);

/* ----- Storia IG: foto dagli ultimi invii ----- */
// "Dagli ultimi invii" apre una pagina con l'elenco; il tocco su una grafica la rende la foto
// della storia (il servizio la tratta come una foto caricata) e si torna al Contenuto.
function openIgSent() {
  haptic('select');
  igPicking = true;
  buildFlow();
  navDir = 1;
  flowIndex = flow.indexOf('igsent');
  renderFlow();
}

function renderIgSent() {
  fillSentRows('igSentList', 'igSentEmpty', 'igSentGroup', pickIgSent);
}

async function pickIgSent(item) {
  haptic('select');
  clearError();
  igb.uploading = true;
  igRefresh();
  try {
    const response = await netFetch(`${directBase}/usesent`, {
      method:'POST', headers:{'Content-Type':'application/json','X-ImageGEN-Session':session},
      body:JSON.stringify({v:1, action:'usesent', session, id:item.id})
    }, 60000, 2, true);
    const body = await response.json().catch(() => ({}));
    if (!response.ok || !body.ok) throw new Error(body.error || 'Grafica non disponibile.');
    if (igb.url && igb.url.startsWith('blob:')) { try { URL.revokeObjectURL(igb.url); } catch (_) {} }
    igb.id = body.photo_id;
    igb.url = sentUrl('image', item.id);
    haptic('success');
    navDir = -1;
    flowIndex = 0;
    renderFlow();            // Contenuto: igPicking torna false e il percorso si accorcia
  } catch (error) {
    showError(error && error.name === 'AbortError' ? 'ImageGEN non risponde. Riprova.' : (error.message || 'Grafica non disponibile.'));
  } finally {
    igb.uploading = false;
    igRefresh();
  }
}

/* ----- Storia IG: frasi pronte ----- */
// Elenco sotto il testo: un tocco mette la frase nel testo; "×" la toglie; "Salva il testo
// come frase pronta" la aggiunge. Le frasi restano nel repo degli asset (sent_store.py).
let igPhrases = [];
async function phrasesCall(action, text='', color='black') {
  const response = await netFetch(`${directBase}/phrases`, {
    method:'POST', headers:{'Content-Type':'application/json','X-ImageGEN-Session':session},
    body:JSON.stringify({v:1, action, session, text, color})
  }, 20000, 2);
  const body = await response.json().catch(() => ({}));
  if (!response.ok || !body.ok) throw new Error(body.error || 'Frasi non disponibili.');
  igPhrases = (Array.isArray(body.phrases) ? body.phrases : [])
    .map(p => typeof p === 'string' ? {text:p, color:'black'} : p).filter(p => p && p.text);
  renderPhrases();
}

function loadPhrases() {
  if (!directBase || !session) return;
  renderPhrases();
  phrasesCall('list').catch(() => {});
}

function renderPhrases() {
  const box = $('igPhrases');
  box.querySelectorAll('.ig-phrase').forEach(el => el.remove());
  const save = $('igPhraseSave');
  igPhrases.forEach(({text, color}) => {
    const row = document.createElement('div');
    row.className = 'ios-row ig-phrase';
    row.innerHTML = '<button class="ig-ph-use" type="button"><span class="ig-ph-dot"></span><span class="ig-ph-txt"></span></button>' +
      '<button class="ig-ph-del" type="button" aria-label="Elimina la frase">×</button>';
    row.querySelector('.ig-ph-txt').textContent = text;
    row.querySelector('.ig-ph-dot').style.background = igHex(color);
    row.querySelector('.ig-ph-use').addEventListener('click', () => {
      haptic('select');
      $('igText').value = text;
      setIgColor(color, false);
      clearError();
      igRefresh();
      renderPhrases();
    });
    row.querySelector('.ig-ph-del').addEventListener('click', () => deletePhrase(text));
    box.insertBefore(row, save);
  });
  // Già salvata uguale (stesso testo e stesso colore): niente da salvare.
  const current = cleanPhrase($('igText').value);
  save.disabled = !current || igPhrases.some(p => p.text === current && p.color === igColor);
  $('igPhrasesEmpty').hidden = igPhrases.length > 0;
}

async function savePhrase() {
  const text = $('igText').value.trim();
  if (!text) { showError('Scrivi prima il testo da salvare.'); return; }
  try { await phrasesCall('add', text, igColor); haptic('success'); }
  catch (error) { showError(error.message || 'Frase non salvata.'); }
}

function deletePhrase(text) {
  const go = async ok => {
    if (!ok) return;
    try { await phrasesCall('delete', text); haptic('success'); }
    catch (error) { showError(error.message || 'Frase non eliminata.'); }
  };
  const msg = `Eliminare la frase pronta “${text.length > 60 ? text.slice(0, 60) + '…' : text}”?`;
  if (tg && typeof tg.showConfirm === 'function') {
    try { tg.showConfirm(msg, go); return; } catch (_) {}
  }
  go(window.confirm(msg));
}

// Come sent_store.clean_phrase: spazi in più tolti riga per riga, a capo conservati.
const cleanPhrase = v => String(v || '').replace(/\r/g, '').split('\n')
  .map(l => l.split(/\s+/).filter(Boolean).join(' ')).join('\n').trim();

/* ----- Storia IG: colore del testo ----- */
// Pallino in alto a destra = colore attuale; un tocco apre la tavolozza sopra il testo.
// Stessi colori di graphics/ig_story.py (TEXT_COLORS).
const IG_COLORS = [['black','#1a1612','Nero'],['blue','#3897F0','Blu'],['green','#70C050','Verde'],
  ['yellow','#FDCB5C','Giallo'],['orange','#FD8D32','Arancione'],['red','#ED4956','Rosso'],
  ['pink','#D10869','Rosa'],['purple','#A307BA','Viola']];
const igHex = key => (IG_COLORS.find(c => c[0] === key) || IG_COLORS[0])[1];

function setIgColor(key, close=true) {
  igColor = IG_COLORS.some(c => c[0] === key) ? key : 'black';
  renderIgColor();
  if (close) $('igColors').hidden = true;
  renderPhrases();
}

function renderIgColor() {
  $('igColorDot').style.background = igHex(igColor);
  // Nel riquadro il testo ha già il colore scelto (il nero resta quello del tema, leggibile anche al buio).
  $('igText').style.color = igColor === 'black' ? '' : igHex(igColor);
  $('igColors').querySelectorAll('.ig-sw').forEach(b => {
    const on = b.dataset.c === igColor;
    b.classList.toggle('on', on);
    b.setAttribute('aria-checked', on ? 'true' : 'false');
  });
}

IG_COLORS.forEach(([key, hex, name]) => {
  const b = document.createElement('button');
  b.type = 'button';
  b.className = 'ig-sw';
  b.dataset.c = key;
  b.style.background = hex;
  b.setAttribute('role', 'radio');
  b.setAttribute('aria-label', name);
  b.title = name;
  b.addEventListener('click', () => { haptic('select'); setIgColor(key); });
  $('igColors').appendChild(b);
});
$('igColorBtn').addEventListener('click', () => {
  haptic('select');
  $('igColors').hidden = !$('igColors').hidden;
  renderIgColor();
});

$('igFromSent').addEventListener('click', openIgSent);
$('igPhraseSave').addEventListener('click', savePhrase);
$('igText').addEventListener('input', renderPhrases);

/* ----- ImageGEN sta per spegnersi ----- */
// Ultimi 5 minuti: riquadro come quelli di errore ma neutro, in alto su ogni pagina, fino alla
// chiusura. Se c'è ancora margine, ricorda che dal cronometro si arriva a 60 minuti.
// Niente messaggi su Telegram.
function updateEndNotice() {
  const box = $('notice');
  const left = sessionExpiresAt - Date.now();
  const show = !LIVE && sessionExpiresAt && left > 0 && left <= 300000;
  if (!show) { box.style.display = 'none'; return; }
  const atMax = sessionMaxAt && sessionExpiresAt >= sessionMaxAt - 60000;
  const text = !sessionMaxAt
    ? `ImageGEN si spegne alle ${clock(sessionExpiresAt)}. Invia le ultime grafiche.`
    : atMax
    ? `ImageGEN si spegne alle ${clock(sessionExpiresAt)}: è il limite di 60 minuti. ` +
      'Invia le ultime grafiche; per continuare dopo, riavvia il workflow.'
    : `ImageGEN si spegne alle ${clock(sessionExpiresAt)}. ` +
      `Per arrivare alle ${clock(sessionMaxAt)} tocca il cronometro in alto.`;
  if (box.textContent !== text) box.textContent = text;
  box.style.display = 'block';
}
setInterval(updateEndNotice, 5000);

if (!LIVE) updateEndNotice();
