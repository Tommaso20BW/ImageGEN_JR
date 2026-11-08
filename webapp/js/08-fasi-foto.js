/* Mini App ImageGen JR. File caricati in ordine da index.html: l'ordine conta. */
/* ---------- HALF / END OF 90' / FULL TIME: sfondo + persona ---------- */
// Stessa pagina dei livelli del bot (1086x1448) e stessi calcoli di
// livescore/graphics/phase_layers.py (box): l'anteprima coincide con la grafica.
// persona.follow = scontornata dallo sfondo e ferma su di esso (combacia esattamente).
const PP_W = 1086, PP_H = 1448;
const ppState = {bg:null, person:null, mode:'both', uploading:false, pick:'photo', cleanUrl:'', cleanFor:'', cleaning:false, ghostUrl:'', ghostBusy:false};

function ppRevoke(url) { if (url) { try { URL.revokeObjectURL(url); } catch (_) {} } }

function clearPhase() {
  if (ppState.bg) ppRevoke(ppState.bg.url);
  if (ppState.person) ppRevoke(ppState.person.url);
  ppState.cleanUrl = ppRevoke(ppState.cleanUrl) || '';
  Object.assign(ppState,{bg:null, person:null, mode:'both', uploading:false, cleaning:false, cleanFor:''});
  ['ppBg','ppPerson'].forEach(id => { $(id).hidden = true; $(id).removeAttribute('src'); });
  $('ppEmpty').hidden = false;
  $('ppSummary').textContent = '';
}

function ppBox(o, f, cover) {
  const fit = Math.max(PP_W / o.w, PP_H / o.h);
  const zoom = Math.min(6, Math.max(cover ? 1 : .2, f.zoom));
  const w = o.w * fit * zoom, h = o.h * fit * zoom;
  let left = (PP_W - w) / 2 + f.x * PP_W, top = (PP_H - h) / 2 + f.y * PP_H;
  if (cover) {
    left = Math.min(0, Math.max(PP_W - w, left));
    top = Math.min(0, Math.max(PP_H - h, top));
  }
  return {left, top, w, h, zoom};
}

// Riporta x/y/zoom nei limiti (come fa il server), così trascinare oltre il bordo non accumula.
function ppNormalize(o, cover) {
  const b = ppBox(o, o, cover);
  o.zoom = b.zoom;
  o.x = (b.left - (PP_W - b.w) / 2) / PP_W;
  o.y = (b.top - (PP_H - b.h) / 2) / PP_H;
  return b;
}

function ppPlace(img, b) {
  img.style.left = `${b.left / PP_W * 100}%`; img.style.top = `${b.top / PP_H * 100}%`;
  img.style.width = `${b.w / PP_W * 100}%`; img.style.height = `${b.h / PP_H * 100}%`;
}

function layoutPhase() {
  const frame = $('ppFrame'), stage = $('stage');
  if (frame.offsetParent) {
    const free = stage.getBoundingClientRect().bottom - frame.getBoundingClientRect().top - 34;
    const width = Math.max(200, Math.min(frame.parentElement.clientWidth, free * 0.75));
    frame.style.maxWidth = 'none';
    frame.style.width = `${Math.floor(width)}px`;
  }
  const {bg, person} = ppState;
  if (!bg) return;
  // Sfondo sempre fermo e a pagina piena. Se la persona e' stata cancellata, l'immagine
  // del server e' gia' la pagina intera (1086x1448).
  bg.x = 0; bg.y = 0; bg.zoom = 1;
  ppPlace($('ppBg'), ppState.cleanFor === bg.id && $('ppBg').dataset.clean === '1'
    ? {left:0, top:0, w:PP_W, h:PP_H} : ppBox(bg, bg, true));
  if (person && person.w) ppPlace($('ppPerson'), ppNormalize(person, false));
  ppSyncClean();
}

// Persona della stessa foto spostata: lo sfondo mostra la versione senza di lei
// (ricostruita dal servizio, una volta sola per foto); tornata al suo posto, l'originale.
function ppMoved(person) {
  return !!person && (Math.abs(person.x) > .0005 || Math.abs(person.y) > .0005 || Math.abs(person.zoom - 1) > .0005);
}

// Sfondo senza la persona, ricostruito dal servizio (una volta sola per foto).
// true = pronto in ppState.cleanUrl, false = non riuscito o foto cambiata.
async function ppFetchClean(id) {
  if (ppState.cleanUrl && ppState.cleanFor === id) return true;
  try {
    const response = await netFetch(`${directBase}/clean?session=${encodeURIComponent(session)}&id=${id}`,{}, 120000);
    if (!response.ok) return false;
    const url = URL.createObjectURL(await response.blob());
    if (!ppState.bg || ppState.bg.id !== id) { ppRevoke(url); return false; }
    ppRevoke(ppState.cleanUrl);
    ppState.cleanUrl = url;
    ppState.cleanFor = id;
    return true;
  } catch (_) { return false; }
}

async function ppSyncClean() {
  const {bg, person} = ppState;
  const img = $('ppBg');
  if (!bg || !person || person.id !== bg.id) {
    if (img.dataset.clean === '1') { img.dataset.clean = ''; img.src = bg ? bg.url : ''; }
    return;
  }
  const want = ppMoved(person);
  if (!want) {
    if (img.dataset.clean === '1') { img.dataset.clean = ''; img.src = bg.url; layoutPhase(); }
    return;
  }
  if (img.dataset.clean === '1' && ppState.cleanFor === bg.id) return;
  if (ppState.cleaning) return;
  if (ppState.cleanUrl && ppState.cleanFor === bg.id) {
    img.dataset.clean = '1'; img.src = ppState.cleanUrl; layoutPhase();
    return;
  }
  ppState.cleaning = true;
  const id = bg.id;
  $('ppSummary').textContent = 'Cancello la persona dallo sfondo…';
  try {
    const response = await netFetch(`${directBase}/clean?session=${encodeURIComponent(session)}&id=${id}`,{}, 120000);
    if (!response.ok) throw new Error('Cancellazione dallo sfondo non riuscita.');
    const url = URL.createObjectURL(await response.blob());
    if (!ppState.bg || ppState.bg.id !== id) { ppRevoke(url); return; }
    ppRevoke(ppState.cleanUrl);
    ppState.cleanUrl = url;
    ppState.cleanFor = id;
  } catch (err) {
    showError(err && err.message ? err.message : 'Cancellazione dallo sfondo non riuscita.');
  } finally {
    ppState.cleaning = false;
    if ($('ppSummary').textContent === 'Cancello la persona dallo sfondo…') $('ppSummary').textContent = '';
  }
  if (ppState.bg && ppState.bg.id === id && ppMoved(ppState.person)) {
    img.dataset.clean = '1'; img.src = ppState.cleanUrl; layoutPhase();
  }
}

// Si muove solo la persona: lo sfondo non e' mai un bersaglio.
function ppTargets() {
  const {bg, person} = ppState;
  return bg && person ? [person] : [];
}

function phasePhotoData(ghost) {
  const {bg, person} = ppState;
  if (!bg) {
    if (!ghost) throw new Error('Scegli una foto.');
    return {photo_id:'0'.repeat(16), frame:{x:0, y:0, zoom:1}};
  }
  const out = {photo_id:bg.id, frame:{x:0, y:0, zoom:1}};
  if (person && person.id !== bg.id) out.person_id = person.id;
  if (person) out.person_frame = {x:person.x, y:person.y, zoom:person.zoom};
  return out;
}

// Sagoma fissa (dati finti: Juventus - Juventus 0-0) di cornice, scritta, risultato e
// stemmi, semitrasparente: immagine statica per fase e sfondo, scaricata in anticipo.
// Fatte da tools/phase_placeholders.py; sfondo come theme() di portrait.py.
function phaseTheme(competition, kit) {
  const c = String(competition || '').toLowerCase();
  if (c === 'uefa.super_cup') return 'usc';
  if (c === 'fifa.cwc') return 'cwc';
  if (c === 'ita.super_cup') return 'supercoppa';
  if (c === 'ita.coppa_italia') return 'coppa';
  if (c.includes('conf')) return 'conference';
  if (c.includes('champions')) return 'ucl';
  if (c.includes('europa')) return 'uel';
  return ['home','away','third'].includes(kit) ? kit : 'home';
}

function phaseOverlayUrl() {
  if (LIVE || !directBase || !session || kind !== 'match' || !PHOTO_PHASES.has(phase)) return '';
  return `${directBase}/overlay?session=${encodeURIComponent(session)}&name=phase_${phase}`
    + `&kit=${phaseTheme(competition, kit)}`;
}

// In live il LiveScore non ha /overlay: la sagoma la disegna lui al momento (/ghost).
async function ppGhostFromServer(overlay) {
  if (ppState.ghostBusy) return;
  ppState.ghostBusy = true;
  try {
    const response = await netFetch(`${directBase}/ghost`,{
      method:'POST', headers:{'Content-Type':'application/json','X-ImageGEN-Session':session},
      body:JSON.stringify(buildPayload(true))
    }, 60000, 2);
    if (!response.ok) throw new Error('Segnaposto non disponibile.');
    const url = URL.createObjectURL(await response.blob());
    ppRevoke(ppState.ghostUrl);
    ppState.ghostUrl = url;
    overlay.src = url;
    overlay.hidden = false;
  } catch (_) {
  } finally {
    ppState.ghostBusy = false;
  }
}

async function loadPpGhost() {
  if (!directBase || !session) return;
  const overlay = $('ppOverlay');
  if (LIVE) {
    if (ppState.ghostUrl) { overlay.src = ppState.ghostUrl; overlay.hidden = false; }
    else ppGhostFromServer(overlay);
    return;
  }
  const url = phaseOverlayUrl();
  if (!url || overlay.getAttribute('src') === url) { overlay.hidden = !url; return; }
  overlay.hidden = true;
  if (await fetchEditorImage(url) && phaseOverlayUrl() === url) { overlay.src = url; overlay.hidden = false; }
}

async function ppSend(blob, type) {
  const response = await netFetch(`${directBase}/upload`,{
    method:'POST', headers:{'Content-Type':type, 'X-ImageGEN-Session':session}, body:blob
  }, 60000);
  const body = await response.json().catch(() => ({}));
  if (!response.ok || !body.ok) throw new Error(body.error || 'Caricamento non riuscito.');
  return body.photo_id;
}

// Persona scontornata dal servizio (o il PNG trasparente caricato, così com'è).
// Lo scontorno gira sul servizio: se ne chiede lo stato con richieste brevi (una sola richiesta
// lunga attraverso il tunnel cade) e il PNG si scarica solo a scontorno finito.
// Non mostra nulla da sola. true = pronta, false = nel frattempo la foto è cambiata,
// eccezione = scontorno non riuscito.
const sleep = ms => new Promise(resolve => setTimeout(resolve, ms));
async function ppLoadCutout(person) {
  const q = `session=${encodeURIComponent(session)}&id=${person.id}`;
  const t0 = performance.now();
  let lastOk = t0;
  for (;;) {
    if (ppState.person !== person) return false;
    let state = '';
    try {
      const response = await netFetch(`${directBase}/cutout_state?${q}&start=1`, {}, 10000, 1);
      const body = await response.json().catch(() => ({}));
      if (response.ok && body.ok) { lastOk = performance.now(); state = body.state; if (state === 'error') throw new Error(body.error || 'Scontorno non riuscito.'); }
      else if (response.status === 404) break;     // servizio senza /cutout_state (bot vecchio): lo scontorno si scarica direttamente
      else if (!TUNNEL_HICCUP.has(response.status)) throw new Error(body.error || 'Scontorno non riuscito.');
    } catch (err) {
      if (err && err.message && !/fetch|network|load failed|abort|connessione/i.test(err.message)) throw err;
    }
    if (state === 'ready') break;
    const now = performance.now();
    if (now - lastOk > 120000) throw new Error('ImageGEN non risponde da oltre 2 minuti. Riprova.');
    if (now - t0 > 600000) throw new Error('Lo scontorno sta impiegando troppo. Riprova.');
    await sleep(1200);
  }
  const response = await netFetch(`${directBase}/cutout?${q}`, {}, 60000, 5, true);
  if (!response.ok) throw new Error('Scontorno non riuscito.');
  const url = URL.createObjectURL(await response.blob());
  if (ppState.person !== person) { ppRevoke(url); return false; }
  ppRevoke(person.url);
  person.url = url;
  $('ppPerson').src = url;
  return true;
}

// pick: 'photo' = foto nuova (sfondo + persona scontornata da lei),
// 'bg' = cambia solo lo sfondo, 'person' = cambia solo la persona.
async function uploadPhasePhoto(file, pick) {
  if (!file) return;
  clearError();
  if (!directBase || !session) { showError('Sessione vecchia. Riavvia ImageGen dal workflow.'); return; }
  ppState.uploading = true;
  // Con una persona da scontornare la foto compare solo a scontorno finito: fino ad allora
  // resta la schermata di caricamento, che si chiude quando la persona è davvero pronta.
  const needsCutout = pick !== 'bg' || !ppState.bg;
  let myBusy = null;
  if (needsCutout) {
    showBusy('Scontorno la persona…', 'Carico la foto…', 'ppcut');
    myBusy = busy;
  } else $('ppSummary').textContent = 'Caricamento foto…';
  try {
    const {blob, w, h, type} = await preparePhoto(file, pick === 'person');
    const id = await ppSend(blob, type);
    const item = {id, w, h, url:URL.createObjectURL(blob), x:0, y:0, zoom:1};
    let person = null;
    if (pick === 'person') {
      if (ppState.person) ppRevoke(ppState.person.url);
      person = ppState.person = {...item, url:'', x:0, y:0, zoom:1, follow:false};
      ppRevoke(item.url);
      ppState.mode = 'person';
      $('ppPerson').hidden = true;
    } else if (pick === 'bg' && ppState.bg) {
      // La persona resta quella di prima, ferma dov'era: cambia solo lo stadio dietro.
      ppRevoke(ppState.bg.url);
      ppRevoke(ppState.cleanUrl); ppState.cleanUrl = ''; ppState.cleanFor = '';
      ppState.bg = item;
      ppState.mode = 'bg';
    } else {
      if (ppState.bg) ppRevoke(ppState.bg.url);
      if (ppState.person) ppRevoke(ppState.person.url);
      ppRevoke(ppState.cleanUrl); ppState.cleanUrl = ''; ppState.cleanFor = '';
      ppState.bg = item;
      person = ppState.person = {id, w, h, url:'', x:0, y:0, zoom:1, follow:false};
      ppState.mode = 'both';
      $('ppPerson').hidden = true;
      $('ppBg').hidden = true;
    }
    if (person) {
      if (busy === myBusy) $('busySub').textContent = 'Separo la persona dallo sfondo: ci vogliono alcuni secondi.';
      let cut = false;
      try { cut = await ppLoadCutout(person); }
      catch (err) {
        // Senza persona scontornata non si mostra mezza foto: si torna a com'era.
        if (ppState.person === person) {
          if (pick === 'person') { ppState.person = null; $('ppPerson').hidden = true; }
          else clearPhase();
        }
        throw err;
      }
      if (!cut) return;     // foto cambiata o svuotata nel frattempo
      // Sfondo ripulito già adesso, dietro la schermata di caricamento: spostando la persona
      // la foto è subito a posto. Se non riesce resta la pulizia al primo spostamento.
      if (ppState.bg && ppState.bg.id === person.id) {
        if (busy === myBusy) $('busySub').textContent = 'Pulisco lo sfondo dietro la persona…';
        ppState.cleaning = true;
        await ppFetchClean(person.id);
        ppState.cleaning = false;
        if (ppState.person !== person) return;
      }
    }
    $('ppBg').dataset.clean = '';
    $('ppBg').src = ppState.bg.url;
    // Immagini già decodificate prima di mostrarle: niente comparsa a pezzi.
    if (person) await Promise.all(['ppBg','ppPerson'].map(el => { const img = $(el); return img.decode ? img.decode().catch(() => {}) : null; }));
    layoutPhase();
    if (person) {
      await finishBusy();
      if (ppState.person !== person) return;
      $('ppPerson').hidden = false;
    }
    $('ppBg').hidden = false;
    $('ppEmpty').hidden = true;
    if ($('ppSummary').textContent === 'Caricamento foto…') $('ppSummary').textContent = '';
    layoutPhase();
    haptic('success');
  } catch (err) {
    $('ppSummary').textContent = '';
    showError(err && err.message ? err.message : 'Caricamento non riuscito.');
  } finally {
    if (myBusy && busy === myBusy) hideBusy();
    ppState.uploading = false;
    renderSteps();
  }
}

function initPhaseEditor() {
  const frame = $('ppFrame');
  const pointers = new Map();
  let last = null;
  const snapshot = () => {
    const pts = [...pointers.values()];
    if (pts.length === 1) return {x:pts[0].x, y:pts[0].y, d:0};
    const [a,b] = pts;
    return {x:(a.x + b.x) / 2, y:(a.y + b.y) / 2, d:Math.hypot(a.x - b.x, a.y - b.y)};
  };
  const pick = which => { ppState.pick = which; $('ppFile').click(); };
  frame.addEventListener('pointerdown',e => {
    if (!ppState.bg) { pick('photo'); return; }
    frame.setPointerCapture(e.pointerId);
    pointers.set(e.pointerId,{x:e.clientX, y:e.clientY});
    last = snapshot();
    frame.classList.add('dragging');
  });
  frame.addEventListener('pointermove',e => {
    if (!pointers.has(e.pointerId) || !last) return;
    pointers.set(e.pointerId,{x:e.clientX, y:e.clientY});
    const now = snapshot();
    // La pagina dei livelli è larga 972/1086 del riquadro (e alta 1296/1448).
    const pw = frame.clientWidth * 972 / PP_W, ph = frame.clientHeight * 1296 / PP_H;
    const zoom = now.d && last.d ? now.d / last.d : 1;
    // Il primo livello mosso decide l'aggancio; gli altri lo seguono dello stesso passo.
    const [lead, ...rest] = ppTargets();
    let snap = [false, false];
    if (lead) {
      const x0 = lead.x, y0 = lead.y;
      snap = snapMove(lead, (now.x - last.x) / pw, (now.y - last.y) / ph, SNAP_PX / pw, SNAP_PX / ph);
      rest.forEach(o => { o.x += lead.x - x0; o.y += lead.y - y0; });
      ppTargets().forEach(o => { o.zoom *= zoom; });
    }
    last = now;
    layoutPhase();
    if (lead) { snapSync(lead, snap); snapShow(frame, snap); }
  });
  const end = e => {
    pointers.delete(e.pointerId);
    last = pointers.size ? snapshot() : null;
    if (!pointers.size) {
      frame.classList.remove('dragging');
      [ppState.bg, ppState.person].forEach(snapEnd);
      snapClear(frame);
    }
  };
  frame.addEventListener('pointerup',end);
  frame.addEventListener('pointercancel',end);
  frame.addEventListener('wheel',e => {
    if (!ppState.bg) return;
    e.preventDefault();
    ppTargets().forEach(o => { o.zoom *= Math.exp(-e.deltaY * 0.0015); });
    layoutPhase();
  },{passive:false});
  $('ppPick').addEventListener('click',() => pick('photo'));
  $('ppFile').addEventListener('change',e => { uploadPhasePhoto(e.target.files && e.target.files[0], ppState.pick); e.target.value = ''; });
  window.addEventListener('resize',layoutPhase);
  frame.addEventListener('touchmove',e => e.preventDefault(),{passive:false});
}

// Nomi per il conteggio (il servizio tiene anche i numeri di maglia): via numeri e simboli, righe vuote e doppioni.
function squadNames() {
  const seen = new Set();
  return $('squadText').value.split(/\r?\n/)
    .map(line => line.replace(/^[\s\d#.\-–—)]+|[\s\d#.\-–—(]+$/g,'').replace(/\s+/g,' ').trim())
    .filter(name => name && !name.endsWith(':') && !seen.has(name.toLocaleLowerCase('it')) && seen.add(name.toLocaleLowerCase('it')));
}

function updateSquadSummary() {
  const n = squadNames().length;
  $('squadSummary').textContent = n === 1 ? '1 giocatore' : `${n} giocatori`;
}

function saveCurrentStatDraft() {
  if (flow[flowIndex] === 'stats') collectStats();
}

function clearStats() {
  statRowEls().forEach(r => {
    r.querySelectorAll('input').forEach(i => { i.value = ''; });
    r.classList.remove('bad');
  });
  collectStats();
}
