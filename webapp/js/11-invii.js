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

// Scelta una partita (04-dati-partita.js): se è quella dell'ultimo invio, torna il risultato.
// La maglia no: non si spunta mai nulla in automatico, la si sceglie ogni volta.
function applyLastChoices(id) {
  const last = readJson(LAST_KEY);
  if (!last || last.match !== id || Date.now() - last.at > LAST_TTL) return;
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
// Cos'è la grafica (negli invii salvati prima "IG" -> "Instagram").
const sentName = item => String(item.name || '').replace(/ IG$/, ' Instagram');
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

// Griglia di foto grandi: sopra la sfumatura solo cos'è (Rinnovo, Storia Instagram...) e l'ora.
function fillSentRows(listId, emptyId, groupId, onPick) {
  const list = $(listId);
  list.innerHTML = '';
  $(emptyId).hidden = recentItems.length > 0;
  $(groupId).hidden = !recentItems.length;
  recentItems.forEach(item => {
    const b = document.createElement('button');
    b.type = 'button';
    b.className = 'sent-tile';
    b.innerHTML = '<img alt="" loading="lazy"><span class="sent-cap"><b></b><small></small></span>';
    b.querySelector('img').src = sentUrl('thumb', item.id);
    b.querySelector('b').textContent = sentName(item);
    b.querySelector('small').textContent = hhmm(item.at);
    b.addEventListener('click', () => onPick(item));
    list.appendChild(b);
  });
}

function renderSentItem() {
  const item = recentPick;
  if (!item) return;
  $('sentTitle').textContent = sentName(item);
  const when = hhmm(item.at);
  $('sentLead').textContent = `Inviata ${/^\d/.test(when) ? 'alle ' : ''}${when}`;
  $('sentImage').src = sentUrl('image', item.id);
  $('sentEdit').hidden = !sentSnapshot(item.id);
  $('sentNote').textContent = '';
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
    closeMiniAppSoon(700);
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
  igPicking = 'sent';
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
// Pagina a parte (dal riquadro "Frasi pronte"): un tocco mette la frase nel testo e si torna alla
// storia; "×" la toglie; "Salva il testo attuale" la aggiunge. Restano nel repo degli asset (sent_store.py).
let igPhrases = [];
async function phrasesCall(action, text='', color='black', extra={}) {
  const response = await netFetch(`${directBase}/phrases`, {
    method:'POST', headers:{'Content-Type':'application/json','X-ImageGEN-Session':session},
    body:JSON.stringify({v:1, action, session, text, color, ...extra})
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

function openIgPhrases() {
  haptic('select');
  igPicking = 'phr';
  buildFlow();
  navDir = 1;
  flowIndex = flow.indexOf('igphr');
  renderFlow();
}

function renderPhrases() {
  const box = $('igPhrases');
  box.querySelectorAll('.ig-phrase').forEach(el => el.remove());
  const save = $('igPhraseSave');
  igPhrases.forEach(phrase => {
    const {text, color} = phrase;
    const row = document.createElement('div');
    row.className = 'ios-row ig-phrase';
    row.innerHTML = '<button class="ig-ph-use" type="button"><span class="ig-ph-dot"></span><span class="ig-ph-body">' +
      '<span class="ig-ph-txt"></span><span class="ig-ph-meta"></span></span></button>' +
      '<button class="ig-ph-del" type="button" aria-label="Elimina la frase">×</button>';
    row.querySelector('.ig-ph-txt').textContent = text;
    row.querySelector('.ig-ph-meta').textContent = phraseMeta(phrase);
    row.querySelector('.ig-ph-dot').style.background = igHex(color);
    row.querySelector('.ig-ph-use').addEventListener('click', () => {
      haptic('select');
      $('igText').value = text;
      setIgColor(color, false);
      if ('label' in phrase) {          // salvata con etichetta, fonte e link: torna tutto com'era
        setIgLabel(phrase.label);
        $('igLabelText').value = phrase.label === 'custom' ? phrase.label_text || '' : '';
        $('igSource').value = phrase.source || '';
        $('igLinkText').value = phrase.link_text || '';
        renderIgLink();
      }
      clearError();
      igRefresh();
      renderPhrases();
      if (flow[flowIndex] === 'igphr') { navDir = -1; flowIndex = 0; renderFlow(); }
    });
    row.querySelector('.ig-ph-del').addEventListener('click', () => deletePhrase(text));
    box.appendChild(row);
  });
  // Già salvata uguale (stesso testo, colore, etichetta, fonte e link): niente da salvare.
  const current = cleanPhrase($('igText').value);
  const extra = phraseExtra();
  save.disabled = !current || igPhrases.some(p => p.text === current && p.color === igColor &&
    'label' in p && Object.keys(extra).every(k => (p[k] || '') === extra[k]));
  $('igPhrasesEmpty').hidden = igPhrases.length > 0;
  $('igPhrCount').textContent = igPhrases.length === 1 ? '1 frase' : igPhrases.length ? `${igPhrases.length} frasi` : 'Salvate da te';
}

async function savePhrase() {
  const text = $('igText').value.trim();
  if (!text) { showError('Scrivi prima il testo da salvare.'); return; }
  try { await phrasesCall('add', text, igColor, phraseExtra()); haptic('success'); }
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

// Etichetta, titolo, fonte e link di adesso: si salvano con la frase.
function phraseExtra() {
  const one = v => String(v || '').split(/\s+/).filter(Boolean).join(' ');
  return {label: igLabel || '', label_text: igLabel === 'custom' ? one($('igLabelText').value).toUpperCase() : '',
          source: one($('igSource').value), link_text: one($('igLinkText').value)};
}
// Sotto la frase, in piccolo: cosa si rimette con lei.
function phraseMeta(p) {
  if (!('label' in p)) return '';
  const label = p.label === 'custom' ? p.label_text : (IG_LABELS.find(l => l[0] === p.label) || [])[1];
  return [label, p.source && `Fonte: ${p.source}`, p.link_text && `Link: ${p.link_text}`].filter(Boolean).join(' · ');
}

// Come sent_store.clean_phrase: spazi in più tolti riga per riga, a capo conservati.
const cleanPhrase = v => String(v || '').replace(/\r/g, '').split('\n')
  .map(l => l.split(/\s+/).filter(Boolean).join(' ')).join('\n').trim();

/* ----- Storia IG: etichetta in alto ----- */
// Stesse chiavi di graphics/ig_story.py (LABELS).
// Nessuna scelta = nessun titolo; "Personalizzato" apre il campo per scriverlo.
const IG_LABELS = [['breaking','Breaking News'],['mercato','Calciomercato'],['ufficiale','Ufficiale'],['custom','Personalizzato']];

function setIgLabel(key) {
  igLabel = IG_LABELS.some(l => l[0] === key) ? key : '';
  $('igLabelText').hidden = igLabel !== 'custom';
  $('igLabels').querySelectorAll('.ig-seg').forEach(b => {
    const on = b.dataset.l === igLabel;
    b.classList.toggle('selected', on);
    b.setAttribute('aria-checked', on ? 'true' : 'false');
  });
}

// Selettore a segmenti come quelli di iOS: nomi corti, la grafica scrive quello completo.
const IG_LABEL_SHORT = {breaking: 'Breaking', mercato: 'Mercato', ufficiale: 'Ufficiale', custom: 'Personalizzato'};

IG_LABELS.forEach(([key, name]) => {
  const b = document.createElement('button');
  b.type = 'button';
  b.className = 'ig-seg';
  b.dataset.l = key;
  b.textContent = IG_LABEL_SHORT[key];
  b.setAttribute('role', 'radio');
  b.setAttribute('aria-label', name);
  // un secondo tocco su quello scelto lo toglie: nessun titolo
  b.addEventListener('click', () => {
    haptic('select');
    setIgLabel(igLabel === key ? '' : key);
    if (igLabel === 'custom' && !$('igLabelText').value.trim()) $('igLabelText').focus();
  });
  $('igLabels').appendChild(b);
});
setIgLabel(igLabel);

/* ----- Storia IG: spazio per il link -----
   Icona in alto a destra del colore: apre il riquadro come la tavolozza. Con un testo c'è la striscia
   (lunga quanto il pulsante con quel testo), vuoto niente. L'icona si colora quando c'è. */
function renderIgLink() {
  $('igLinkBtn').classList.toggle('on', !!$('igLinkText').value.trim());
}
const closeIgLink = () => { $('igLinkOv').classList.remove('open'); $('igLinkText').blur(); renderIgLink(); };
$('igLinkBtn').addEventListener('click', () => {
  haptic('select');
  $('igLinkOv').classList.add('open');
  setTimeout(() => $('igLinkText').focus(), 80);
});
$('igLinkText').addEventListener('input', renderIgLink);
$('igLinkText').addEventListener('keydown', e => { if (e.key === 'Enter') { e.preventDefault(); closeIgLink(); } });
$('igLinkDone').addEventListener('click', () => { haptic('select'); closeIgLink(); });
$('igLinkClear').addEventListener('click', () => { haptic('select'); $('igLinkText').value = ''; closeIgLink(); });
$('igLinkOv').addEventListener('click', e => { if (e.target.id === 'igLinkOv') closeIgLink(); });

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
$('igFromTg').addEventListener('click', openIgTg);
$('igOpenPhr').addEventListener('click', openIgPhrases);
$('igPhraseSave').addEventListener('click', savePhrase);
$('igText').addEventListener('input', renderPhrases);

// Fonte della notizia: le righe "📰 ilBianconero" / "📲 Nome - Testata" (anche incollate o prese dal
// canale) escono dal testo e vanno nel campo Fonte, che diventa un blocco nero nella grafica.
const IG_SOURCE_LINE = /^[ \t]*(?:\u{1F4F0}|\u{1F4F2})\uFE0F?[ \t]*(\S[^\n]*)$/gmu;
function igSplitSource() {
  const box = $('igText'), text = box.value, found = [];
  const rest = text.replace(IG_SOURCE_LINE, (_, name) => { found.push(name.trim()); return ''; });
  if (!found.length) return;
  box.value = rest.replace(/\n{3,}/g, '\n\n').trim();
  $('igSource').value = found.join(' · ').slice(0, 90);
  haptic('select');
  igRefresh();
}
$('igText').addEventListener('input', igSplitSource);

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

/* ----- Storia IG: testo dagli ultimi post del canale Telegram (app/tgchannel.py) -----
   "Dal canale" apre l'elenco degli ultimi 20 post, già senza emoji, fonte e firma: il tocco su una
   notizia mette testo e foto nella storia e si torna al Contenuto. Niente miniature nell'elenco:
   solo un album, al tocco, apre le sue foto per scegliere quale usare (o "Solo testo"). */
let tgPosts = null, tgLoading = false;
function openIgTg() {
  haptic('select');
  igPicking = 'tg';
  buildFlow();
  navDir = 1;
  flowIndex = flow.indexOf('igtg');
  renderFlow();
}
async function loadIgTg() {
  if (tgLoading) return;
  clearError();
  if (!directBase || !session) { showError('Sessione vecchia. Riavvia ImageGen dal workflow.'); return; }
  tgLoading = true;
  renderIgTg();
  try {
    const response = await netFetch(`${directBase}/tgposts`, {
      method:'POST', headers:{'Content-Type':'application/json','X-ImageGEN-Session':session},
      body:JSON.stringify({v:1, action:'tgposts', session})
    }, 30000, 2, true);
    const body = await response.json().catch(() => ({}));
    if (!response.ok || !body.ok) throw new Error(body.error || 'Canale Telegram non disponibile.');
    tgPosts = Array.isArray(body.posts) ? body.posts : [];
  } catch (error) {
    showError(error && error.name === 'AbortError' ? 'ImageGEN non risponde. Riprova.' : (error.message || 'Canale Telegram non disponibile.'));
  } finally {
    tgLoading = false;
    renderIgTg();
  }
}
function tgWhen(iso) {
  const d = new Date(iso);
  if (isNaN(d)) return '';
  const time = d.toLocaleTimeString('it-IT', {hour:'2-digit', minute:'2-digit'});
  return d.toDateString() === new Date().toDateString() ? time : `${d.getDate()}/${d.getMonth() + 1} ${time}`;
}
function renderIgTg() {
  const list = $('igTgList'), posts = tgPosts || [];
  list.innerHTML = '';
  $('igTgNote').textContent = tgLoading && !posts.length ? 'Leggo il canale…' : tgPosts && !posts.length ? 'Nessun post.' : '';
  $('igTgGroup').hidden = !posts.length;
  posts.forEach(post => {
    const photos = Array.isArray(post.photos) ? post.photos : [];
    const many = photos.length > 1;
    const b = document.createElement('div');
    b.className = 'hm-item tg-post';
    b.setAttribute('role', 'button');
    b.tabIndex = 0;
    b.innerHTML = '<span class="hm-txt"><span class="hm-top"><span class="hm-name"></span><span class="hm-time"></span></span>' +
      '<span class="tg-meta"></span></span>' +
      '<svg class="hm-go" viewBox="0 0 24 24" aria-hidden="true"><path d="M9 6l6 6-6 6"/></svg>';
    b.querySelector('.hm-name').textContent = post.text || 'Solo foto';
    b.querySelector('.hm-time').textContent = tgWhen(post.date);
    b.querySelector('.tg-meta').textContent = photos.length === 1 ? 'Con foto' : many ? `${photos.length} foto · tocca per scegliere` : '';
    if (many) {
      b.addEventListener('click', event => {
        if (event.target.closest('.tg-pic')) return;
        haptic('select');
        list.querySelectorAll('.tg-open').forEach(x => { if (x !== b) x.classList.remove('tg-open'); });
        b.classList.toggle('tg-open');
      });
      const row = document.createElement('div');
      row.className = 'tg-pics';
      photos.forEach((url, i) => {
        const t = document.createElement('button');
        t.type = 'button';
        t.className = 'tg-pic';
        t.style.backgroundImage = `url("${url}")`;
        t.setAttribute('aria-label', `Usa la foto ${i + 1}`);
        t.addEventListener('click', () => pickIgTg(post, url));
        row.appendChild(t);
      });
      if (post.text) {
        const t = document.createElement('button');
        t.type = 'button';
        t.className = 'tg-pic tg-nopic';
        t.textContent = 'Solo testo, senza foto';
        t.addEventListener('click', () => pickIgTg(post, ''));
        row.appendChild(t);
      }
      b.querySelector('.hm-txt').appendChild(row);
    } else {
      b.addEventListener('click', () => pickIgTg(post, photos[0] || ''));
    }
    list.appendChild(b);
  });
}
let tgPicking = false;
async function pickIgTg(post, photoUrl) {
  if (tgPicking) return;
  clearError();
  if (photoUrl) {
    haptic('select');
    tgPicking = true;
    igb.uploading = true;
    igRefresh();
    try {
      const response = await netFetch(`${directBase}/tgphoto`, {
        method:'POST', headers:{'Content-Type':'application/json','X-ImageGEN-Session':session},
        body:JSON.stringify({v:1, action:'tgphoto', session, url:photoUrl})
      }, 60000, 2, true);
      const body = await response.json().catch(() => ({}));
      if (!response.ok || !body.ok) throw new Error(body.error || 'Foto del canale non disponibile.');
      if (igb.url && igb.url.startsWith('blob:')) { try { URL.revokeObjectURL(igb.url); } catch (_) {} }
      igb.id = body.photo_id;
      igb.url = photoUrl;
    } catch (error) {
      showError(error && error.name === 'AbortError' ? 'ImageGEN non risponde. Riprova.' : (error.message || 'Foto del canale non disponibile.'));
      return;
    } finally {
      tgPicking = false;
      igb.uploading = false;
      igRefresh();
    }
  }
  haptic('success');
  if (post.text) { $('igText').value = String(post.text).slice(0, 500); igSplitSource(); }
  if (post.text || post.source) $('igSource').value = String(post.source || '').slice(0, 90);
  igRefresh();
  renderPhrases();
  navDir = -1;
  flowIndex = 0;
  renderFlow();            // Contenuto: igPicking torna false e il percorso si accorcia
}

/* ----- Storia IG: si salva nella galleria del telefono, non va sul canale -----
   Testi dell'anteprima per la storia; con le altre grafiche tornano quelli di prima. */
const GALLERY_TEXT = {
  previewLead: 'Se è tutto ok, premi “Salva in galleria”. Altrimenti torna indietro e modifica i dati.',
  previewNote: 'Questa è la storia vera: finisce nella galleria del telefono, sul canale non arriva.',
};
function galleryPreviewText() {
  for (const [id, text] of Object.entries(GALLERY_TEXT)) {
    const el = $(id);
    if (!el) continue;
    if (kind === 'igbn') {
      if (el.textContent !== text) { el.dataset.orig = el.textContent; el.textContent = text; }
    } else if (el.textContent === text && el.dataset.orig) el.textContent = el.dataset.orig;
  }
}
