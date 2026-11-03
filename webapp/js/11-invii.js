/* Mini App ImageGen JR. File caricati in ordine da index.html: l'ordine conta. */
/* ---------- Ultimi invii e ultime scelte ----------
   - "Ultimi invii" in Home (sezione "Altro"): le ultime grafiche mandate in questa sessione (il
     servizio tiene PNG e miniatura). Elenco, poi la grafica: "Rimanda" (stesso PNG, subito) o
     "Modifica i dati" (riapre la grafica compilata, per correggere minuto, risultato o giocatore).
   - Ultime scelte: per la stessa partita la Mini App ricorda risultato e maglia dell'ultimo
     invio. Scegliendo di nuovo quella partita si ritrovano già messi. */
const SENT_KEY = 'imagegen-jr-sent-v1';       // {session, items:{message_id: dati per "Modifica"}}
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
    const store = saved && saved.session === session ? saved : {session, items:{}};
    store.items[messageId] = {
      kind, phase, goalType, competition, side, kit, mdPick, kitFromMatch,
      opponent: selectedTeam ? selectedTeam.name : '',
      player: selectedPlayer ? selectedPlayer.name : '',
      typed: $('natPlayer').value, pose, minute: $('minute').value,
      ev, sc, pens: [$('homePens').value, $('awayPens').value], pensOn, etOn,
    };
    const ids = Object.keys(store.items);
    ids.slice(0, Math.max(0, ids.length - 20)).forEach(id => delete store.items[id]);
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
const hhmm = ms => new Date(ms).toLocaleTimeString('it-IT', {hour:'2-digit', minute:'2-digit'});
// Sempre due righe (tutte le righe dell'elenco alte uguali): giocatore e minuto; risultato e
// avversario. Senza giocatore (Kick Off, fasi...) "risultato · avversario" sale sulla prima.
const sentLines = item => {
  const who = [item.player, item.minute].filter(Boolean).join(' · ');
  const match = [item.score, item.opponent].filter(Boolean).join(' · ');
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
}

function renderSentList() {
  const list = $('sentList');
  list.innerHTML = '';
  $('sentEmpty').hidden = recentItems.length > 0;
  $('sentGroup').hidden = !recentItems.length;
  recentItems.forEach(item => {
    const b = document.createElement('button');
    b.type = 'button';
    b.className = 'hm-item hm-recent';
    b.innerHTML = '<img class="hm-thumb" alt="" loading="lazy"><span class="hm-txt">' +
      '<span class="hm-top"><span class="hm-name"></span><span class="hm-time"></span></span>' +
      '<span class="hm-desc"></span><span class="hm-desc"></span></span>' +
      '<svg class="hm-go" viewBox="0 0 24 24" aria-hidden="true"><path d="M9 6l6 6-6 6"/></svg>';
    b.querySelector('.hm-thumb').src = sentUrl('thumb', item.id);
    b.querySelector('.hm-name').textContent = item.name;
    const [who, match] = sentLines(item);
    const desc = b.querySelectorAll('.hm-desc');
    desc[0].textContent = who || ' ';      // riga vuota: spazio, così l'altezza resta uguale
    desc[1].textContent = match || ' ';
    b.querySelector('.hm-time').textContent = hhmm(item.at);
    b.addEventListener('click', () => {
      haptic('select');
      recentPick = item;
      navDir = 1;
      flowIndex = flow.indexOf('sentitem');
      renderFlow();
    });
    list.appendChild(b);
  });
}

function renderSentItem() {
  const item = recentPick;
  if (!item) return;
  $('sentTitle').textContent = item.name;
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
  return saved && saved.session === session && saved.items ? saved.items[id] || null : null;
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

/* ----- ImageGEN sta per spegnersi ----- */
// Ultimi 5 minuti al limite dei 60 (la sessione non si allunga più): riquadro come quelli di
// errore ma neutro, in alto su ogni pagina, fino alla chiusura. Niente messaggi su Telegram.
function updateEndNotice() {
  const box = $('notice');
  const left = sessionExpiresAt - Date.now();
  const show = !LIVE && sessionExpiresAt && sessionMaxAt && left > 0 && left <= 300000
    && sessionExpiresAt >= sessionMaxAt - 60000;
  if (!show) { box.style.display = 'none'; return; }
  const text = `ImageGEN si spegne alle ${clock(sessionExpiresAt)}: è il limite di 60 minuti. ` +
    'Invia le ultime grafiche; per continuare dopo, riavvia il workflow.';
  if (box.textContent !== text) box.textContent = text;
  box.style.display = 'block';
}
setInterval(updateEndNotice, 5000);

if (!LIVE) updateEndNotice();
