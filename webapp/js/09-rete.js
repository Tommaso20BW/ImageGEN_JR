/* Mini App ImageGen JR. File caricati in ordine da index.html: l'ordine conta. */
/* ---------- Payload / network ---------- */
function scorePair(a,b,required=true) {
  const av = $(a).value.trim();
  const bv = $(b).value.trim();
  if (!av && !bv && !required) return null;
  if (!av || !bv) throw new Error('Inserisci entrambi i valori del risultato.');
  const pair = [Number(av),Number(bv)];
  if (!pair.every(Number.isInteger) || pair.some(v => v < 0 || v > 99)) {
    throw new Error('Risultato non valido.');
  }
  return pair;
}

// ghost=true: anteprima nell'editor, valida anche senza foto (id segnaposto).
function buildPayload(ghost=false) {
  if (LIVE) {
    if (!session) throw new Error('Sessione non attiva: riapri il pulsante del bot.');
    return {v:1, action:'render', session, data:{slot:LIVE_SLOT, kind:LIVE_PHASE, ...phasePhotoData(ghost)}};
  }
  const photoId = photoState.id || (ghost ? '0'.repeat(16) : '');
  if (isQuoteKind(kind)) {
    const photo = iq.story ? {photo_id:photoId} : iq.photos[iq.sel];
    if (!photo || !photo.photo_id) throw new Error(iq.story ? 'Carica la foto della storia (Scegli foto).' : 'Scegli la foto del post.');
    // Foto del post, o quella caricata a mano nell'editor ("Scegli foto"). Storia: sempre a mano.
    return {v:1, action:'render', session, data:{kind, photo_id:photoState.id || photo.photo_id, ...(iq.story ? {story:true} : {}),
      text:$('iqText').value.trim(), name:$('iqName').value.trim(), ...(iq.avatar ? {avatar_id:iq.avatar} : {}),
      handle:$('iqHandle').value.trim(), verified:!!iq.verified,
      frame:{x:photoState.x, y:photoState.y, zoom:photoState.zoom}}};
  }
  if (kind === 'igbn') {
    const text = $('igText').value.trim();
    if (!text && !igb.id) throw new Error('Scrivi un testo o scegli una foto.');
    return {v:1, action:'render', session, data:{kind:'igbn', text, color:igColor, ...(igb.id ? {photo_id:igb.id} : {})}};
  }
  if (kind === 'conv') return convPayload();
  if (kind === 'table') {
    if (!tableComp) throw new Error('Scegli la competizione.');
    if (!tableViewOf()) throw new Error('Scegli classifica o tabellone.');
    return {v:1, action:'render', session, data:{kind:'table', competition:tableComp, view:tableViewOf()}};
  }
  if (kind === 'cal') {
    return {v:1, action:'render', session, data:{
      kind:'cal', month:calMonth, year:Number($('calYear').value),
      matches:calRows.map(r => ({day:Number(r.day), side:r.side, opponent:{name:r.team}}))
    }};
  }
  if (kind === 'jr' && jrb.style === 'collage') {
    const cells = jrCollageCells();
    if (cells.length < 2) throw new Error('Scegli almeno 2 foto.');
    return {v:1, action:'render', session, data:{kind:'jr', style:'collage', color:jrColor, cells}};
  }
  if (kind === 'jr' && jrb.style === 'blur') {
    if (!jrb.cards.length) throw new Error('Carica almeno una foto.');
    return {v:1, action:'render', session, data:{
      kind:'jr', style:'blur', color:jrColor,
      background_id:jrb.bg || jrb.cards[0].id,
      cards:jrb.cards.map(c => ({photo_id:c.id, x:+c.x.toFixed(5), y:+c.y.toFixed(5), w:+c.w.toFixed(5)}))
    }};
  }
  if (kind === 'jr' && jrb.style === 'title') {
    if (!photoId) throw new Error('Scegli una foto.');
    if (!jrb.title.trim()) throw new Error('Scrivi il titolo.');
    return {v:1, action:'render', session, data:{
      kind:'jr', style:'title', color:jrColor, title:jrb.title.trim(), title_color:jrb.tcolor,
      photo_id:photoId, frame:{x:photoState.x, y:photoState.y, zoom:photoState.zoom}
    }};
  }
  if (kind === 'jr') {
    if (!photoId) throw new Error('Scegli una foto.');
    return {v:1, action:'render', session, data:{
      kind:'jr', color:jrColor, photo_id:photoId, ratio:jrb.ratio,
      frame:{x:photoState.x, y:photoState.y, zoom:photoState.zoom}
    }};
  }
  if (!nat && !selectedTeam) throw new Error('Avversario mancante.');

  const data = nat ? natPayload() : {
    // KICK OFF non chiede la maglia: in quel caso vale home (non viene mostrata).
    kind: realKind(), competition, kit: kit || 'home', side,
    opponent:{ name:selectedTeam.name, id:String(selectedTeam.espn_id || '') }
  };
  if (!nat && needsShirt()) data.shirt = shirt;

  if (nat && (kind === 'goal' || kind === 'saved')) {
    // dati già pronti (natPayload)
  } else if (kind === 'goal' && (goalType === 'own' || goalType === 'nophoto')) {
    // Autogol o gol senza foto: nome scritto a mano, niente foto e niente posa.
    data.goal_type = goalType;
    data.player = natPlayerName();
    data.minute = $('minute').value.trim();
    data.score = scorePair('evHomeScore','evAwayScore',true);
  } else if (kind === 'goal' || kind === 'saved') {
    if (!selectedPlayer) throw new Error('Giocatore mancante.');
    data.player = selectedPlayer.name;
    data.minute = $('minute').value.trim();
    data.score = scorePair('evHomeScore','evAwayScore',true);
    data.pose = pose;
    if (kind === 'goal' && goalType === 'penalty') data.goal_type = 'penalty';
  } else if (kind === 'match' && phase !== 'kick') {
    data.score = scorePair('homeScore','awayScore',true);
    if (phase === 'full' && etOn) data.extra_time = true;
    if (phase === 'full' && pensOn) {
      data.shootout = scorePair('homePens','awayPens',true);
    }
    if (PHOTO_PHASES.has(phase) && !isFriendly() && !nat) Object.assign(data, phasePhotoData(ghost));
  } else if (kind === 'xi') {
    if (!photoId) throw new Error('Scegli una foto.');
    data.lineup = lineupRows().map(p => ({number:p.number, name:p.name}));
    data.photo_id = photoId;
    data.frame = {x:photoState.x, y:photoState.y, zoom:photoState.zoom};
  } else if (kind === 'md') {
    if (!photoId) throw new Error('Scegli una foto.');
    data.photo_id = photoId;
    data.frame = {x:photoState.x, y:photoState.y, zoom:photoState.zoom};
    data.stadium = $('matchStadium').value;
    data.time = $('matchTime').value;
    data.date = $('matchDate').value;
  } else if (kind === 'pxi') {
    data.module = pxiModule;
    data.players = pxiPicks.slice();
    if (pxiLay.layouts[pxiModule]) data.layout = pxiLay.layouts[pxiModule];
  } else if (kind === 'squad') {
    data.squad = $('squadText').value;
  } else if (kind === 'stats') {
    collectStats();
    data.moment = moment;
    data.rows = STATS
      .map(label => ({
        label,
        home:String(statRows[label]?.home || '').trim(),
        away:String(statRows[label]?.away || '').trim()
      }))
      .filter(row => row.home || row.away);
    if (!data.rows.length) throw new Error('Inserisci almeno una statistica.');
    if (data.rows.some(row => !row.home || !row.away)) {
      throw new Error('Completa entrambi i valori delle statistiche.');
    }
  }

  if (!session) throw new Error('Sessione non attiva. Avvia ImageGen e apri il pulsante del bot.');
  return {v:1,action:'render',session,data};
}

// Richiesta al workflow con nuovo tentativo automatico se la rete si interrompe
// (sul telefono, attraverso il tunnel, capita: il server ha già fatto il lavoro
// e ripetere è sicuro, anche l'invio a Telegram non crea doppioni).
// Il collegamento passa da un tunnel Cloudflare gratuito: ogni tanto la rete cade o il
// tunnel risponde 502/503/504/52x/530 per un attimo. In quei casi si riprova da soli.
// Tutte le chiamate si possono ripetere senza danni: il servizio riconosce lo stesso
// invio (niente doppioni su Telegram) e riusa l'anteprima già pronta.
// retryAbort: anche l'attesa scaduta si riprova (anteprima e invio).
const TUNNEL_HICCUP = new Set([502,503,504,520,521,522,523,524,530]);
async function netFetch(url, options, timeoutMs=90000, tries=5, retryAbort=false) {
  let lastAbort = null;
  for (let attempt = 1; attempt <= tries; attempt++) {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), timeoutMs);
    try {
      const response = await fetch(url, {...options, mode:'cors', cache:'no-store', credentials:'omit', signal:controller.signal});
      if (TUNNEL_HICCUP.has(response.status) && attempt < tries) {
        await new Promise(resolve => setTimeout(resolve, 1200 * attempt));
        continue;
      }
      return response;
    } catch (error) {
      if (error && error.name === 'AbortError') {
        if (!retryAbort || attempt >= tries) throw error;
        lastAbort = error;
      }
      if (attempt < tries) await new Promise(resolve => setTimeout(resolve, Math.min(3000, 700 * attempt)));
    } finally { clearTimeout(timer); }
  }
  if (lastAbort) throw lastAbort;
  throw new Error('Connessione con ImageGEN instabile. Riprova tra qualche secondo.');
}

/* ---------- PROBABILE XI: Modifica posizioni e grandezza ----------
   Le card si spostano solo sui punti della griglia (servizio: graphics/probabili.py).
   Ogni modulo ha posizioni e grandezza sue, salvate per sempre nel repository. */
const CARD = {left:-117, right:117, top:-175.4, bottom:58.9};   // card rispetto a (centro x, alto etichetta)
const CARD_MID = (CARD.top + CARD.bottom) / 2;                   // centro visivo della card
// Come fit_card in graphics/probabili.py: la card disegnata resta dentro la pagina
// (12 px dal bordo) anche sulle colonne esterne; la posizione salvata non cambia.
const CARD_MARGIN = 12;
const layFit = ([x, top], s) => [
  Math.min(Math.max(x, CARD_MARGIN - CARD.left * s), 1080 - CARD_MARGIN - CARD.right * s),
  Math.min(Math.max(top, CARD_MARGIN - CARD.top * s), 1440 - CARD_MARGIN - CARD.bottom * s),
];
// Come place_cards in graphics/probabili.py: barre del nome ad almeno 12 px; due card
// troppo vicine si allontanano quanto basta, la spinta passa ai vicini e al bordo si
// sposta di più l'altra.
const LABEL_H = 58.9, LABEL_GAP = 12;
function layPlace(cards, s) {
  const width = (CARD.right - CARD.left) * s, height = LABEL_H * s;
  let pos = cards.map(c => layFit(c, s));
  for (let round = 0; round < 200; round++) {
    let moved = false;
    for (let i = 0; i < pos.length; i++) {
      for (let j = i + 1; j < pos.length; j++) {
        const [xi, ti] = pos[i], [xj, tj] = pos[j];
        if (Math.abs(ti - tj) >= height + LABEL_GAP) continue;
        const need = width + LABEL_GAP - Math.abs(xi - xj);
        if (need <= 0.01) continue;
        const side = (xj > xi || (xj === xi && j > i)) ? 1 : -1;
        pos[i][0] -= side * need / 2;
        pos[j][0] += side * need / 2;
        moved = true;
      }
    }
    pos = pos.map(p => layFit(p, s));
    if (!moved) break;
  }
  // File impossibili (troppe card per la larghezza): a spazi uguali fra i due bordi.
  const lo = CARD_MARGIN - CARD.left * s, hi = 1080 - CARD_MARGIN - CARD.right * s;
  const parent = pos.map((_, i) => i);
  const root = a => { while (parent[a] !== a) a = parent[a]; return a; };
  for (let i = 0; i < pos.length; i++)
    for (let j = i + 1; j < pos.length; j++)
      if (Math.abs(pos[i][1] - pos[j][1]) < height + LABEL_GAP && Math.abs(pos[i][0] - pos[j][0]) < width + LABEL_GAP - 0.5)
        parent[root(j)] = root(i);
  const rows = new Map();
  pos.forEach((_, i) => { const r = root(i); if (!rows.has(r)) rows.set(r, []); rows.get(r).push(i); });
  for (const row of rows.values()) {
    if (row.length > 1 && (width + LABEL_GAP) * (row.length - 1) > hi - lo) {
      row.sort((a, b) => pos[a][0] - pos[b][0] || a - b);
      row.forEach((i, k) => { pos[i][0] = lo + k * (hi - lo) / (row.length - 1); });
    }
  }
  return pos;
}

// undo[modulo] = disposizioni prima di ogni modifica: Ripristina torna indietro di una.
const pxiLay = {layouts:{}, defaults:{}, grid:null, min:.7, max:1.3, loaded:null, sel:-1, before:'', undo:{}};
function layRemember() { (pxiLay.undo[pxiModule] = pxiLay.undo[pxiModule] || []).push(layCopy(pxiLay.layouts[pxiModule])); }

function loadLayouts() {
  if (!directBase || !session) return Promise.resolve();
  if (!pxiLay.loaded) {
    pxiLay.loaded = netFetch(`${directBase}/layouts?session=${encodeURIComponent(session)}`,{},20000)
      .then(r => r.json())
      .then(body => {
        if (!body.ok) throw new Error();
        // Le modifiche fatte in questa sessione restano (anche cambiando modulo).
        pxiLay.layouts = {...body.layouts, ...pxiLay.layouts};
        pxiLay.defaults = body.defaults;
        pxiLay.grid = body.grid;
        pxiLay.min = body.scale.min; pxiLay.max = body.scale.max;
      })
      .catch(() => { pxiLay.loaded = null; });
  }
  return pxiLay.loaded;
}

const layCopy = layout => JSON.parse(JSON.stringify(layout));

async function openLayoutEditor() {
  clearError();
  await loadLayouts();
  if (!pxiLay.grid || !pxiLay.layouts[pxiModule]) { setPreviewError('Posizioni non disponibili. Riprova.'); return; }
  pxiLay.sel = -1;
  pxiLay.before = JSON.stringify(pxiLay.layouts[pxiModule]);
  $('layTitle').textContent = `Posizioni · ${pxiModule}`;
  $('layBg').src = `${directBase}/pxibg?session=${encodeURIComponent(session)}&kit=${encodeURIComponent(kit || 'home')}`;
  $('lay').classList.add('open');
  try { if (tg && tg.disableVerticalSwipes) tg.disableVerticalSwipes(); } catch (_) {}
  renderLayout(true);
}

function renderLayout(rebuild=false) {
  const layout = pxiLay.layouts[pxiModule];
  const s = layout.scale;
  // Griglia sul centro delle card (cambia con la grandezza).
  const ys = pxiLay.grid.y.map(y => y + CARD_MID * s);
  // Una riga su due più marcata (la griglia originale), le righe nuove quasi invisibili.
  $('layGrid').innerHTML =
    pxiLay.grid.x.map(x => `<line class="${Math.abs(Math.round((x - 120) / 52.5)) % 2 ? '' : 'main'}" x1="${x}" y1="0" x2="${x}" y2="1440"/>`).join('') +
    ys.map((y,i) => `<line class="${i % 2 ? 'fine' : 'main'}" x1="0" y1="${y}" x2="1080" y2="${y}"/>`).join('') +
    pxiLay.grid.x.map(x => ys.map((y,i) => `<circle class="${i % 2 ? 'fine' : ''}" cx="${x}" cy="${y}" r="${i % 2 ? 3 : 4}"/>`).join('')).join('');
  const box = $('layCards');
  if (rebuild || box.children.length !== 11) {
    box.innerHTML = '';
    const roles = rolesOf(pxiModule);
    layout.cards.forEach((_c,i) => {
      const card = document.createElement('button');
      card.type = 'button';
      card.className = 'lay-card';
      const player = players.find(pl => pl.name === pxiPicks[i]);
      card.innerHTML = '<span class="role"></span><span class="nm"></span>';
      card.querySelector('.role').textContent = roles[i] || '';
      card.querySelector('.nm').textContent = String(player ? surnameOf(player) : pxiPicks[i] || '').toUpperCase();
      card.addEventListener('click',e => {
        e.stopPropagation();
        haptic('select');
        pxiLay.sel = pxiLay.sel === i ? -1 : i;
        renderLayout();
      });
      box.appendChild(card);
    });
  }
  const drawn = layPlace(layout.cards, s);
  [...box.children].forEach((card,i) => {
    const [x, top] = drawn[i];
    card.style.left = `${(x + CARD.left * s) / 1080 * 100}%`;
    card.style.top = `${(top + CARD.top * s) / 1440 * 100}%`;
    card.style.width = `${(CARD.right - CARD.left) * s / 1080 * 100}%`;
    card.style.height = `${(CARD.bottom - CARD.top) * s / 1440 * 100}%`;
    card.classList.toggle('sel', i === pxiLay.sel);
  });
  $('layFrame').classList.toggle('picking', pxiLay.sel >= 0);
  $('layRoleBox').hidden = pxiLay.sel < 0;
  if (pxiLay.sel >= 0 && document.activeElement !== $('layRole')) $('layRole').value = rolesOf(pxiModule)[pxiLay.sel] || '';
  $('layScale').textContent = `${Math.round(s * 100)}%`;
  $('layReset').disabled = !(pxiLay.undo[pxiModule] || []).length;
  $('layMinus').disabled = s <= pxiLay.min + 1e-6;
  $('layPlus').disabled = s >= pxiLay.max - 1e-6;
  document.querySelectorAll('.lay-pad button').forEach(b => {
    const [dx, dy] = b.dataset.move.split(',').map(Number);
    b.disabled = pxiLay.sel < 0 || gridStep(layout.cards[pxiLay.sel], dx, dy) === null;
  });
  $('layHint').textContent = pxiLay.sel >= 0
    ? `${box.children[pxiLay.sel].querySelector('.nm').textContent || 'Card'}: spostala con le frecce.`
    : 'Tocca una card, poi spostala con le frecce.';
}

// Punto di griglia successivo nella direzione (solo lungo quell'asse);
// una card ancora nella posizione Canva scatta sul primo punto oltre la sua.
function gridStep([x, top], dx, dy) {
  const next = (list, v, dir) => dir > 0 ? list.find(g => g > v + .5) : [...list].reverse().find(g => g < v - .5);
  if (dx) { const nx = next(pxiLay.grid.x, x, dx); return nx === undefined ? null : [nx, top]; }
  const ny = next(pxiLay.grid.y, top, dy);
  return ny === undefined ? null : [x, ny];
}

// Freccia: la card scelta va al punto di griglia vicino (resta selezionata);
// se lì c'è già un'altra card, si scambiano di posto.
function moveSelected(dx, dy) {
  if (pxiLay.sel < 0) return;
  const layout = pxiLay.layouts[pxiModule];
  const from = layout.cards[pxiLay.sel];
  const to = gridStep(from, dx, dy);
  if (!to) return;
  const other = layout.cards.findIndex((c,i) => i !== pxiLay.sel && Math.abs(c[0] - to[0]) < 1 && Math.abs(c[1] - to[1]) < 1);
  layRemember();
  if (other >= 0) layout.cards[other] = from.slice();
  layout.cards[pxiLay.sel] = to;
  haptic('select');
  renderLayout();
}

function stepScale(dir) {
  const layout = pxiLay.layouts[pxiModule];
  const next = Math.min(pxiLay.max, Math.max(pxiLay.min, Math.round((layout.scale + dir * .01) * 100) / 100));  // 1% alla volta
  if (next === layout.scale) return;
  layRemember();
  layout.scale = next;
  haptic('select');
  renderLayout();
}

async function closeLayoutEditor() {
  $('lay').classList.remove('open');
  try { if (tg && tg.enableVerticalSwipes) tg.enableVerticalSwipes(); } catch (_) {}
  const layout = pxiLay.layouts[pxiModule];
  readPxiText();                      // etichette nuove anche nell'elenco
  if (JSON.stringify(layout) === pxiLay.before) return;
  // Salvataggio per sempre (repository) e nuova anteprima con le posizioni nuove.
  // Anche l'anteprima porta le posizioni e il servizio le salva se sono nuove,
  // quindi se questa richiesta si perde il salvataggio parte comunque.
  netFetch(`${directBase}/layout`,{
    method:'POST', headers:{'Content-Type':'application/json','X-ImageGEN-Session':session},
    body:JSON.stringify({v:1, action:'layout', session, module:pxiModule, layout})
  }, 30000).catch(() => {});
  await previewGraphic();
}

function initLayoutEditor() {
  $('modOv').addEventListener('click',e => { if (e.target.id === 'modOv') closeModSheet(); });
  // Etichetta della card scelta (vale per ogni modulo, anche quelli già esistenti).
  $('layRole').addEventListener('input',e => {
    const layout = pxiLay.layouts[pxiModule];
    if (pxiLay.sel < 0 || !layout) return;
    if (!layout.roles) layout.roles = [...rolesOf(pxiModule)];
    layout.roles[pxiLay.sel] = e.target.value.toUpperCase().slice(0,5);
    const span = $('layCards').children[pxiLay.sel];
    if (span) span.querySelector('.role').textContent = layout.roles[pxiLay.sel];
  });
  // Tocco sul campo vuoto: deseleziona.
  $('layFrame').addEventListener('click',() => { if (pxiLay.sel >= 0) { pxiLay.sel = -1; renderLayout(); } });
  document.querySelectorAll('.lay-pad button').forEach(b => {
    const [dx, dy] = b.dataset.move.split(',').map(Number);
    b.addEventListener('click',() => moveSelected(dx, dy));
  });
  $('layMinus').addEventListener('click',() => stepScale(-1));
  $('layPlus').addEventListener('click',() => stepScale(1));
  $('layDone').addEventListener('click',closeLayoutEditor);
  // Ripristina: annulla l'ultima modifica (spostamento o grandezza).
  $('layReset').addEventListener('click',() => {
    const stack = pxiLay.undo[pxiModule] || [];
    if (!stack.length) return;
    haptic('select');
    pxiLay.layouts[pxiModule] = stack.pop();
    renderLayout();
  });
  $('lay').addEventListener('touchmove',e => { if (e.target.closest('#layFrame')) e.preventDefault(); },{passive:false});
}

async function previewGraphic() {
  clearError();
  try {
    if (!directBase) throw new Error('Sessione vecchia. Riavvia ImageGen dal workflow.');

    if (kind === 'pxi') await loadLayouts();
    const raw = JSON.stringify(buildPayload());
    if (new TextEncoder().encode(raw).length > 4096) throw new Error('Troppi dati per ImageGEN.');

    $('nextButton').disabled = true;
    $('backButton').disabled = true;
    $('nextButton').textContent = 'Anteprima…';
    const bracket = kind === 'table' && tableViewOf() === 'bracket';    // tempi e testo a parte: ci mette di più
    showBusy('Genero l’anteprima…',bracket ? 'Leggo il tabellone aggiornato da Diretta.it.' : BUSY_SUB[realKind()] || '',bracket ? 'bracket' : realKind());

    // Il servizio può aspettare un'altra richiesta (fino a 75 s) e poi fare il render.
    const response = await netFetch(`${directBase}/preview`, {
      method:'POST', headers:{'Content-Type':'application/json','X-ImageGEN-Session':session}, body:raw
    }, 150000, 2, true);

    if (!response.ok) {
      let answer = {};
      try { answer = await response.json(); } catch (_) {}
      throw new Error(answer.error || `Anteprima non riuscita (${response.status}).`);
    }

    const blob = await response.blob();
    if (!blob || !String(blob.type || '').startsWith('image/')) throw new Error('Anteprima non valida.');

    await finishBusy();
    previewPayloadText = raw;
    openPreview(URL.createObjectURL(blob));
  } catch (error) {
    const message = sessionExpired()
      ? EXPIRED_MESSAGE
      : (error && error.name === 'AbortError'
        ? 'Anteprima lenta o non disponibile. Riprova tra qualche secondo.'
        : (error.message || 'Dati non validi.'));
    showError(message);
  } finally {
    hideBusy();
    $('nextButton').disabled = sessionExpired();
    $('backButton').disabled = backLocked();
    $('nextButton').textContent = previewMode ? SEND_LABEL : (isLastStep() ? 'Anteprima' : 'Avanti ›');
  }
}

async function submitPreviewGraphic() {
  setPreviewError('');
  try {
    if (!directBase) throw new Error('Sessione vecchia. Riavvia ImageGen dal workflow.');

    const raw = previewPayloadText || JSON.stringify(buildPayload());

    $('nextButton').disabled = true;
    $('backButton').disabled = true;
    $('nextButton').textContent = 'Invio…';
    if (LIVE) showBusy('Confermo la foto…','Il bot la userà per la grafica.','submit');
    else showBusy('Invio su Telegram…','La foto arriva nella chat del bot.','submit');

    // Il servizio può aspettare l'anteprima in corso (fino a 75 s) e Telegram (fino a 60 s).
    // Ripetere è sicuro: lo stesso invio non parte due volte.
    const response = await netFetch(`${directBase}/submit`, {
      method:'POST', headers:{'Content-Type':'application/json','X-ImageGEN-Session':session}, body:raw
    }, 150000, 2, true);

    let answer = {};
    try { answer = await response.json(); } catch (_) {}
    if (!response.ok || answer.ok === false) {
      throw new Error(answer.error || `Invio non riuscito (${response.status}).`);
    }

    if (!LIVE && typeof rememberSent === 'function') rememberSent(answer.message_id);
    await finishBusy();
    $('nextButton').textContent = LIVE ? 'Confermata ✓' : 'Inviato ✓';
    $('busyTitle').textContent = LIVE ? 'Confermata ✓' : 'Inviata ✓';
    $('busySub').textContent = LIVE ? 'Il bot la userà per la grafica al fischio.' : 'Trovi la foto nella chat del bot.';
    haptic('success');
    setTimeout(() => {
      try { if (tg && typeof tg.disableClosingConfirmation === 'function') tg.disableClosingConfirmation(); } catch (_) {}
      try { if (tg && typeof tg.close === 'function') tg.close(); } catch (_) {}
    }, 700);
  } catch (error) {
    hideBusy();
    $('nextButton').disabled = sessionExpired();
    $('backButton').disabled = false;
    $('nextButton').textContent = SEND_LABEL;
    const message = sessionExpired()
      ? EXPIRED_MESSAGE
      : (error && error.name === 'AbortError'
        ? 'ImageGEN non risponde. Controlla la chat del bot: la foto potrebbe essere arrivata.'
        : (error.message || 'Invio non riuscito.'));
    setPreviewError(message);
  }
}


/* ---------- Live: stato dal LiveScore ---------- */
// Titolo e risultato dal bot; se avevi gia' confermato una foto, l'editor riparte da li'.
async function loadLiveState() {
  try {
    const response = await netFetch(`${directBase}/phase?session=${encodeURIComponent(session)}&slot=${encodeURIComponent(LIVE_SLOT)}`,{}, 30000);
    const body = await response.json();
    if (!response.ok || !body.ok) throw new Error(body.error || 'Sessione non valida.');
    liveTitle = body.score ? `${body.title} · ${body.score}` : body.title;
    $('ppEyebrow').textContent = liveTitle;
    const state = body.state;
    if (state && state.bg && !ppState.bg) {
      const q = `session=${encodeURIComponent(session)}`;
      ppState.bg = {...state.bg, x:0, y:0, zoom:1, url:`${directBase}/photo?${q}&id=${state.bg.id}`};
      ppState.person = {...state.person, follow:false, url:`${directBase}/cutout?${q}&id=${state.person.id}`};
      ppState.mode = 'both';
      $('ppBg').src = ppState.bg.url; $('ppBg').hidden = false;
      $('ppPerson').src = ppState.person.url; $('ppPerson').hidden = false;
      $('ppEmpty').hidden = true;
      layoutPhase(); renderSteps();
    }
  } catch (err) {
    showError(err && err.message ? err.message : 'LiveScore non raggiungibile.');
  }
}

/* ---------- Catalogs ---------- */
function decodeGithubContent(payload) {
  if (!payload || typeof payload !== 'object' || !payload.content) return null;
  try {
    const clean = String(payload.content).replace(/\s+/g,'');
    const binary = atob(clean);
    const bytes = Uint8Array.from(binary, char => char.charCodeAt(0));
    return JSON.parse(new TextDecoder('utf-8').decode(bytes));
  } catch (_) { return null; }
}

function normalizeCatalogs(playerRows, teamRows) {
  if (Array.isArray(playerRows) && playerRows.length) {
    players = playerRows;
    players.sort((a,b) => String(a.name || '').localeCompare(String(b.name || ''),'it',{sensitivity:'base'}));
    playersLoaded = true;
  }
  if (Array.isArray(teamRows) && teamRows.length) {
    teams = teamRows
      .filter(team => team && team.name)
      .filter(team => !namesFor(team).some(name => norm(name) === 'juventus'));
    resolveTeamAliases();
    teamsLoaded = teams.length > 0;
  }
}

function restoreCatalogCache() {
  try {
    const cached = JSON.parse(localStorage.getItem(CATALOG_CACHE_KEY) || 'null');
    if (!cached || typeof cached !== 'object') return;
    setTeamNames(cached.teamNames);
    normalizeCatalogs(cached.players,cached.teams);
  } catch (_) {}
}

function saveCatalogCache() {
  try {
    localStorage.setItem(CATALOG_CACHE_KEY,JSON.stringify({savedAt:Date.now(),players,teams,teamNames:teamNamesRaw}));
  } catch (_) {}
}

async function fetchOneCatalog(url,label,timeoutMs=2600) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(),timeoutMs);
  const freshUrl = `${url}${url.includes('?') ? '&' : '?'}_=${Date.now()}`;
  try {
    const response = await fetch(freshUrl,{
      cache:'no-store', signal:controller.signal,
      headers:{'Accept': url.includes('api.github.com') ? 'application/vnd.github+json' : 'application/json'}
    });
    if (!response.ok) throw new Error(`${label}: HTTP ${response.status}`);
    const payload = await response.json();
    const data = url.includes('api.github.com') ? (decodeGithubContent(payload) || payload) : payload;
    if (!data || typeof data !== 'object') throw new Error(`${label}: JSON non valido`);
    return data;
  } finally { clearTimeout(timer); }
}

function fetchCatalogFast(urls,label) {
  return Promise.any(urls.map(url => fetchOneCatalog(url,label)));
}

async function loadCatalogs() {
  if (catalogLoadPromise) return catalogLoadPromise;
  catalogLoadPromise = (async () => {
    if (!playersLoaded) $('playerSummary').textContent = 'Caricamento giocatori…';
    if (!teamsLoaded) $('opponentSummary').textContent = 'Caricamento squadre…';

    // Squadre, loghi e calciatori arrivano già pronti dal workflow; GitHub resta solo come riserva.
    const bundle = (directBase && session)
      ? fetchOneCatalog(`${directBase}/catalog?session=${encodeURIComponent(session)}`,'Catalogo workflow',10000)
      : Promise.reject(new Error('Workflow non collegato'));
    bundle.catch(() => null);
    const fromBundle = key => bundle.then(data => {
      if (!Array.isArray(data[key]) || !data[key].length) throw new Error(`${key} mancanti`);
      return data;
    });
    const [playersResult,teamsResult,namesResult] = await Promise.allSettled([
      fromBundle('players').catch(() => fetchCatalogFast(PLAYERS_URLS,'Giocatori')),
      fromBundle('teams').catch(() => fetchCatalogFast(TEAMS_URLS,'Squadre')),
      bundle.then(data => {
        if (!data.team_names || !Object.keys(data.team_names).length) throw new Error('nomi mancanti');
        return data;
      }).catch(() => fetchCatalogFast(TEAM_NAMES_URLS,'Nomi squadre'))
    ]);

    // I nomi italiani vanno applicati prima delle squadre, che si ordinano per nome mostrato.
    if (namesResult.status === 'fulfilled') {
      const value = namesResult.value;
      setTeamNames(value && value.team_names ? value.team_names : value);
    }

    if (playersResult.status === 'fulfilled') {
      const book = playersResult.value.shirts;
      if (book && typeof book === 'object') Object.assign(shirtBook, book);
      const splits = playersResult.value.name_splits;      // convocati: nome/cognome salvati
      if (splits && typeof splits === 'object') Object.assign(nameSplitBook, splits);
      const rows = Array.isArray(playersResult.value.players) ? playersResult.value.players : [];
      if (rows.length) normalizeCatalogs(rows,null);
    }
    if (teamsResult.status === 'fulfilled') {
      const rows = Array.isArray(teamsResult.value.teams) ? teamsResult.value.teams : [];
      if (rows.length) normalizeCatalogs(null,rows);
    }

    if (playersLoaded || teamsLoaded) saveCatalogCache();
    refreshSearchSummaries();
    updateSetBadge();
    loadEspnTeams();
  })().finally(() => { catalogLoadPromise = null; });
  return catalogLoadPromise;
}
