/* ---------- Compleanno ----------
   Passi: Giocatore (lista con ricerca) → Foto (le sue pose con la maglia home in quadretti, divise
   in Matchday, Starting e Goal, o Saved per i portieri) → Dati (nome sulla striscia, data di nascita
   ed età) → Posizione (trascina il giocatore, due dita per lo zoom). La data arriva da sola (asset o Wikidata) insieme alle foto; si può sempre correggere. */
// Un solo Compleanno, due tipi: Rosa attuale (pose degli asset) o Ex giocatore (foto caricata).
const BD_MODES = [['now','Rosa attuale'],['old','Ex giocatore']];
// manual: giocatore non in elenco, aggiunto a mano con una foto caricata (scontornata dal servizio).
// births: date di nascita della rosa (nome -> AAAA-MM-GG) per ordinare l'elenco dal prossimo compleanno.
const bd = {mode:'', manual:false, player:'', photos:[], photo:'', loading:false, key:'', birth:'', page:null,
  frame:{x:0, y:0, zoom:1}, ghostKey:'', ghostUrl:'', births:null, birthsBusy:false};

// Giorni al prossimo compleanno (0 = oggi); Infinity se la data non c'è.
function bdDaysTo(iso) {
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(iso || '');
  if (!m) return Infinity;
  const today = new Date(); today.setHours(0,0,0,0);
  let next = new Date(today.getFullYear(), Number(m[2]) - 1, Number(m[3]));
  if (next < today) next = new Date(today.getFullYear() + 1, Number(m[2]) - 1, Number(m[3]));
  return Math.round((next - today) / 864e5);
}
// Data del compleanno (gg.mm) e quanto manca, per l'elenco: [data, mancano] o null.
function bdWhen(iso) {
  const n = bdDaysTo(iso);
  if (n === Infinity) return null;
  return [`${iso.slice(8,10)}.${iso.slice(5,7)}`, n === 0 ? 'Oggi' : n === 1 ? 'Domani' : `${n} gg`];
}
async function bdLoadBirths() {
  if (bd.births || bd.birthsBusy || !directBase || !session) return;
  bd.birthsBusy = true;
  try {
    const response = await netFetch(`${directBase}/bdaybirths`,{
      method:'POST', headers:{'Content-Type':'application/json','X-ImageGEN-Session':session},
      body:JSON.stringify({v:1, session})
    }, 20000, 2);
    const body = await response.json().catch(() => ({}));
    if (response.ok && body.ok) { bd.births = body.births || {}; bdRender(); }
  } catch (_) {
  } finally {
    bd.birthsBusy = false;
  }
}

function bdAge(iso) {
  const m = /^(\d{4})-\d{2}-\d{2}$/.exec(iso || '');
  return m ? String(new Date().getFullYear() - Number(m[1])) : '';
}
function bdSetBirth(iso) {
  $('bdBirth').value = iso || '';
  $('bdAge').value = bdAge(iso);
}
function bdPhotoOf(id) { return bd.photos.find(p => p.id === id); }

/* Ex giocatore (grafica 'bdold' del servizio): Nome → Foto (caricata e scontornata dal servizio)
   → Posizione (stesso editor: trascina, due dita per lo zoom). */
const bdo = {id:'', thumb:'', height:0, page:null, loading:false};
const bdOld = () => kind === 'bday' && bd.mode === 'old';
// Foto caricata dall'utente: Ex giocatore, o giocatore della rosa aggiunto a mano.
const bdUploaded = () => bdOld() || kind === 'motm' || kind === 'potm' || (kind === 'bday' && bd.manual);
function bdClearUpload() {
  Object.assign(bdo,{id:'', thumb:'', height:0, page:null, loading:false});
  $('bdoPreview').hidden = true;
  $('bdoStatus').textContent = '';
}
// Testi della schermata Foto caricata: diversi per Ex giocatore e giocatore aggiunto a mano.
function bdoTexts() {
  if (kind === 'motm' || kind === 'potm') {
    $('bdoEyebrow').textContent = kind === 'potm' ? 'Player of the Month' : 'Man of the Match';
    $('bdoLead').textContent = "Carica la foto del giocatore, meglio se a figura intera: lo scontorno lo fa l'app.";
    return;
  }
  const old = bd.mode === 'old';
  $('bdoEyebrow').textContent = old ? 'Compleanno · Ex giocatore' : 'Compleanno · Rosa attuale';
  $('bdoLead').textContent = old ? "Carica la foto del giocatore: scontorno e filtro d'epoca li fa l'app."
    : "Carica la foto del giocatore: lo scontorno lo fa l'app.";
}
function bdSetMode(v) {
  if (v !== bd.mode) { bd.mode = v; bd.frame = {x:0, y:0, zoom:1}; bd.ghostKey = ''; bdClearUpload(); }
  bdoTexts();
  buildFlow();
  renderSteps();
}
// Giocatore non in elenco: si salta la scelta delle pose e si carica la foto.
function bdManualStart() {
  haptic('select');
  clearError();
  if (!bd.manual) {
    Object.assign(bd,{manual:true, player:'', photos:[], photo:'', key:'', birth:'', frame:{x:0, y:0, zoom:1}, ghostKey:''});
    $('bdName').value = '';
    bdSetBirth('');
    bdClearUpload();
  }
  bdoTexts();
  buildFlow();
  bdRender();
  renderSteps();
  nextField(true);
}
// Persona e pagina dell'editor: posa degli asset o foto caricata e scontornata.
function bdCur() { return bdUploaded() ? (bdo.id ? {id:bdo.id, thumb:bdo.thumb, height:bdo.height} : null) : bdPhotoOf(bd.photo); }
function bdCurPage() { return bdUploaded() ? bdo.page : bd.page; }

async function bdoUpload(file) {
  if (!file) return;
  clearError();
  if (!directBase || !session) { showError('Sessione vecchia. Riavvia ImageGen dal workflow.'); return; }
  bdo.loading = true;
  $('bdoStatus').textContent = '';
  renderSteps();
  // stessa schermata di caricamento delle altre grafiche, fino a scontorno finito
  showBusy('Scontorno il giocatore…', 'Carico la foto…', 'ppcut');
  const myBusy = busy;
  try {
    const {blob,type} = await preparePhoto(file, true);
    const up = await netFetch(`${directBase}/upload`,{
      method:'POST', headers:{'Content-Type':type,'X-ImageGEN-Session':session}, body:blob
    }, 60000);
    const ub = await up.json().catch(() => ({}));
    if (!up.ok || !ub.ok) throw new Error(ub.error || 'Caricamento non riuscito.');
    if (busy === myBusy) $('busySub').textContent = 'Separo il giocatore dallo sfondo: ci vogliono alcuni secondi.';
    const cut = await netFetch(`${directBase}/bdoldcut`,{
      method:'POST', headers:{'Content-Type':'application/json','X-ImageGEN-Session':session},
      body:JSON.stringify({v:1, session, photo_id:ub.photo_id, mode:kind === 'motm' || kind === 'potm' ? kind : bdOld() ? 'old' : 'now'})
    }, 120000);
    const cb = await cut.json().catch(() => ({}));
    if (!cut.ok || !cb.ok) throw new Error(cb.error || 'Scontorno non riuscito.');
    Object.assign(bdo,{id:ub.photo_id, thumb:cb.thumb, height:cb.height, page:cb.page});
    if (busy === myBusy) await finishBusy();
    bd.frame = {x:0, y:0, zoom:1};
    $('bdoPreview').src = cb.thumb;
    $('bdoPreview').hidden = false;
    $('bdoStatus').textContent = 'Fatto: tocca la foto per cambiarla.';
    haptic('success');
    setTimeout(() => { if (flow[flowIndex] === 'bdophoto') nextField(true); }, 250);
  } catch (err) {
    $('bdoStatus').textContent = bdo.id ? 'Tocca la foto per cambiarla.' : '';
    showError(err && err.message ? err.message : 'Caricamento non riuscito.');
  } finally {
    if (busy === myBusy) hideBusy();
    bdo.loading = false;
    $('bdoFile').value = '';
    renderSteps();
  }
}

function bdoPayload() {
  const name = $('bdoName').value.trim();
  if (!name) throw new Error('Scrivi il nome.');
  if (!bdo.id) throw new Error('Carica la foto.');
  return {v:1, action:'render', session, data:{kind:'bdold', name, photo_id:bdo.id, frame:{...bd.frame},
    ...(bdo.vintage === false ? {vintage:false} : {})}};
}

/* Man of the Match: partita scelta dal calendario (squadre e campionato compilati da soli, sempre
   modificabili), nome e cognome, foto caricata e scontornata, posizione nello stesso editor. */
const MOTM_FIELDS = ['motmName','motmSurname','motmHome','motmAway','motmComp'];
const motm = {key:''};
// Giornata di Serie A: partite di campionato della Juventus dall'inizio della stagione a quella scelta
// (ESPN non la dà; con i recuperi può sbagliare, per questo la riga resta modificabile).
async function motmMatchday(date) {
  const [y, m] = date.split('-').map(Number);
  const rows = await fetchFixtures(`${m >= 7 ? y : y - 1}-07-01`, date).catch(() => []);
  return rows.filter(r => r.competition === 'ita.1' && r.date <= date).length || '';
}
async function motmFill() {
  const opp = selectedTeam ? displayTeamName(selectedTeam.name) : '';
  const date = $('matchDate').value || '';
  const key = [mdPick, competition, side, opp, date].join('|');
  if (key === motm.key) return;
  motm.key = key;
  if (opp) {
    $('motmHome').value = side === 'away' ? opp : 'Juventus';
    $('motmAway').value = side === 'away' ? 'Juventus' : opp;
  }
  const comp = COMP_SHORT[competition] || '';
  $('motmComp').value = comp;
  renderSteps();
  if (competition === 'ita.1' && /^\d{4}-\d{2}-\d{2}$/.test(date)) {
    const n = await motmMatchday(date);
    if (n && motm.key === key) { $('motmComp').value = `${comp} – Matchday ${n}`; renderSteps(); }
  }
}
const motmName = v => v.trim().toLowerCase().replace(/(^|[^a-zà-ÿ'])([a-zà-ÿ])/g, (_, a, b) => a + b.toUpperCase());
const POTM_FIELDS = ['potmName','potmSurname'];
// Mesi in ordine di stagione; se ne possono scegliere più di uno (nessuno scelto all'inizio).
const POTM_MONTHS = ['Agosto','Settembre','Ottobre','Novembre','Dicembre','Gennaio','Febbraio','Marzo','Aprile','Maggio','Giugno','Luglio'];
const potmSel = new Set();
const potmMonths = () => POTM_MONTHS.filter(m => potmSel.has(m)).map(m => m.toUpperCase());
function potmMonthRender() {
  const box = $('potmMonthOpts');
  if (!box.childElementCount) {
    POTM_MONTHS.forEach(m => {
      const b = document.createElement('button');
      b.type = 'button'; b.className = 'opt'; b.dataset.v = m; b.setAttribute('role','checkbox');
      b.innerHTML = '<span class="radio"></span><span class="opt-label"></span>';
      b.querySelector('.opt-label').textContent = m;
      b.addEventListener('click',() => {
        haptic('select');
        potmSel.has(m) ? potmSel.delete(m) : potmSel.add(m);
        potmMonthRender(); renderSteps();
      });
      box.appendChild(b);
    });
  }
  box.querySelectorAll('.opt').forEach(b => {
    const on = potmSel.has(b.dataset.v);
    b.classList.toggle('selected',on);
    b.setAttribute('aria-checked',on ? 'true' : 'false');
  });
}
function potmPayload() {
  const surname = $('potmSurname').value.trim(), months = potmMonths();
  if (!surname) throw new Error('Scrivi il cognome.');
  if (!months.length) throw new Error('Scegli il mese.');
  if (!bdo.id) throw new Error('Carica la foto.');
  return {v:1, action:'render', session, data:{kind:'potm', surname:surname.toUpperCase(), name:motmName($('potmName').value),
    months, photo_id:bdo.id}};
}
function motmPayload() {
  const surname = $('motmSurname').value.trim(), home = $('motmHome').value.trim(), away = $('motmAway').value.trim();
  if (!surname) throw new Error('Scrivi il cognome.');
  if (!home || !away) throw new Error('Scrivi le squadre.');
  if (!bdo.id) throw new Error('Carica la foto.');
  return {v:1, action:'render', session, data:{kind:'motm', surname:surname.toUpperCase(), name:motmName($('motmName').value), home, away,
    comp:$('motmComp').value.trim(), photo_id:bdo.id, frame:{...bd.frame}}};
}

function bdRender() {
  const q = $('bdPlayerSearch').value;
  let matches = playersLoaded ? searchItems(players,q) : [];
  // dal prossimo compleanno (oggi in cima); chi non ha la data in fondo
  const births = bd.births || {};
  if (bd.births) matches = matches.map((p,i) => [p,i]).sort((a,b) =>
    (bdDaysTo(births[a[0].name]) - bdDaysTo(births[b[0].name])) || (a[1] - b[1])).map(r => r[0]);
  const chosen = players.find(p => p.name === bd.player);
  $('bdPlayerSummary').textContent = bd.loading ? 'Caricamento foto…'
    : !playersLoaded ? 'Caricamento giocatori…' : !matches.length ? 'Nessun risultato.'
    : chosen ? `Selezionato: ${surnameOf(chosen)}` : bd.manual ? 'Aggiunto a mano: carica la sua foto.' : '';
  renderResults('bdPlayerList',matches,bd.player,item => surnameOf(item),item => { bdPick(item.name); },null,Infinity);
  // data e giorni che mancano: a parte, piccoli e grigi a destra del nome
  for (const row of $('bdPlayerList').children) {
    let tag = row.querySelector('.bd-when');
    if (!tag) {
      tag = document.createElement('span');
      tag.className = 'bd-when';
      row.insertBefore(tag,row.querySelector('.tick'));
    }
    const when = bdWhen(births[row.dataset.name]);
    tag.innerHTML = '';
    if (when) {
      const d = document.createElement('b'), n = document.createElement('small');
      d.textContent = when[0];
      n.textContent = when[1];
      if (when[1] === 'Oggi') n.className = 'today';
      tag.append(d, n);
    }
  }
}

// ---- Emoji del giocatore negli auguri (faccia del JR Pack) ----
// Se manca si avvisa e la si sceglie dal pack: resta salvata per sempre (si può cambiare).
let bdEmo = null, bdEmoBusy = false;
function bdEmoLoad() {
  const name = bd.player;
  if (kind !== 'bday' || bd.manual || !name) { bdEmo = null; bdEmoRender(); return; }
  if (bdEmo && bdEmo.name === name && !bdEmo.error) { bdEmoRender(); return; }
  bdEmo = {name, loading:true};
  bdEmoRender();
  setPost({action:'player_emoji', name})
    .then(body => { if (bd.player === name) { bdEmo = body; bdEmoRender(); if (!body.current) haptic('warning'); } })
    .catch(() => { if (bd.player === name) { bdEmo = {name, error:true}; bdEmoRender(); } });
}
function bdEmoRender() {
  const box = $('bdEmoBox');
  if (!box) return;
  box.hidden = !bdEmo;
  if (!bdEmo) return;
  const E = bdEmo, cur = E.current, note = $('bdEmoNote');
  const p = players.find(x => x.name === E.name), who = p ? surnameOf(p) : E.name;
  $('bdEmoVal').innerHTML = E.loading ? '…' : E.error ? 'Non disponibile'
    : cur && cur.thumb ? `<span class="emo-th" style="width:28px;height:28px;background-image:url('${cur.thumb}')"></span>`
    : cur ? setEsc(cur.emoji || '') : '<span class="bd-emo-miss">Manca</span>';
  note.classList.toggle('bd-emo-warn', !!(!E.loading && !E.error && !cur));
  note.textContent = E.loading || E.error ? '' : !cur
    ? `Manca l'emoji personalizzata di ${who}: toccala e sceglila dal JR Pack (resta salvata).`
    : E.manual ? 'Scelta da te: va prima della torta negli auguri. Toccala per cambiarla.'
    : 'Va prima della torta negli auguri. Toccala per cambiarla.';
}
async function bdEmoOpen() {
  if (!bdEmo || bdEmo.loading || bdEmo.error || bdEmoBusy) return;
  haptic('select');
  $('bdEmoSheet').hidden = false;
  $('bdEmoReset').hidden = !bdEmo.manual;
  const grid = $('bdEmoGrid');
  grid.innerHTML = '<div class="hint">Carico…</div>';
  try {
    const sheet = await emoSheet(bdEmo.pack || 'AroundJuventus');
    const cur = bdEmo.current;
    grid.innerHTML = sheet.items.map((e, n) =>
      `<button type="button" class="emo-cell${cur && cur.pack === sheet.pack && cur.index === e.index ? ' on' : ''}" data-n="${n}" aria-label="Emoji ${e.index}">
        <span class="emo-th" style="width:38px;height:38px;${emoCellStyle(sheet, n)}"></span></button>`).join('');
  } catch (err) {
    grid.innerHTML = `<div class="hint">${setEsc(err.message || 'Pack non disponibile.')}</div>`;
  }
}
async function bdEmoSave(change) {
  const name = bdEmo && bdEmo.name;
  if (!name || bdEmoBusy) return;
  bdEmoBusy = true;
  $('bdEmoSheet').hidden = true;
  $('bdEmoVal').textContent = '…';
  try {
    const body = await setPost({action:'player_emoji_save', emoji:{name, ...change}});
    haptic('success');
    if (bd.player === name) bdEmo = body;
    bdEmoRender();
    if (!body.remote) $('bdEmoNote').textContent = `Salvata solo per questa sessione: ${body.warning || 'GitHub non raggiungibile'}.`;
  } catch (err) {
    haptic('error');
    bdEmoRender();
    $('bdEmoNote').textContent = err.message || String(err);
  } finally {
    bdEmoBusy = false;
  }
}

function bdPick(name) {
  if (bd.manual) { bd.manual = false; bdClearUpload(); buildFlow(); }
  if (name !== bd.player) {
    Object.assign(bd,{player:name, photos:[], photo:'', key:'', birth:''});
    $('bdName').value = '';
    bdSetBirth('');
  }
  bdRender();
  bdLoad(true);
}

// Pose e data di nascita del giocatore scelto. advance: appena arrivano si passa alle foto.
async function bdLoad(advance=false) {
  if (!bd.player) return;
  if (bd.key === bd.player && bd.photos.length) { if (advance && flow[flowIndex] === 'bdplayer') nextField(true); return; }
  clearError();
  if (!directBase || !session) { showError('Sessione vecchia. Riavvia ImageGen dal workflow.'); return; }
  const key = bd.player;
  bd.loading = true; bdRender(); renderSteps();
  try {
    const response = await netFetch(`${directBase}/bdayphotos`,{
      method:'POST', headers:{'Content-Type':'application/json','X-ImageGEN-Session':session},
      body:JSON.stringify({v:1, session, player:key})
    }, 30000, 2);
    const body = await response.json().catch(() => ({}));
    if (!response.ok || !body.ok) throw new Error(body.error || 'Foto del giocatore non disponibili.');
    if (key !== bd.player) return;          // scelta cambiata mentre arrivava: vale l'ultima
    bd.photos = body.photos || [];
    bd.page = body.page || null;
    bd.key = key;
    bd.birth = body.birth || '';
    if (!$('bdName').value.trim()) $('bdName').value = body.name || key.toUpperCase();
    if (!$('bdBirth').value) bdSetBirth(bd.birth);
    haptic('success');
    if (advance && flow[flowIndex] === 'bdplayer') setTimeout(() => nextField(true), 180);
  } catch (err) {
    if (key === bd.player) { bd.player = ''; showError(err && err.message ? err.message : 'Foto del giocatore non disponibili.'); }
  } finally {
    if (key === bd.player || !bd.loading) bd.loading = false;
    bdRender(); renderSteps();
  }
}

function bdPhotosRender() {
  const box = $('bdPhotos');
  box.innerHTML = '';
  const chosen = players.find(p => p.name === bd.player);
  $('bdPhotoLead').textContent = chosen ? `Tocca la foto di ${surnameOf(chosen)} da mettere nel poster.` : 'Scegli prima il giocatore.';
  // Tutte le foto insieme, senza dividerle per Matchday / Starting / Goal.
  const grid = document.createElement('div');
  grid.className = 'iq-grid';
  bd.photos.forEach(p => {
    const b = document.createElement('button');
    b.type = 'button';
    b.className = 'iq-ph bd-ph' + (p.id === bd.photo ? ' on' : '');
    b.style.backgroundImage = `url("${p.thumb}")`;
    b.setAttribute('aria-label','Foto');
    b.addEventListener('click',() => {
      haptic('select');
      if (bd.photo !== p.id) bd.frame = {x:0, y:0, zoom:1};
      bd.photo = p.id;
      bdPhotosRender();
      renderSteps();
      setTimeout(() => { if (flow[flowIndex] === 'bdphoto') nextField(true); }, 180);
    });
    grid.appendChild(b);
  });
  box.appendChild(grid);
}

function bdValidate(step) {
  if (step === 'bdplayer' && !bd.manual) {
    if (!bd.player) { showError('Scegli il giocatore.'); return false; }
    if (!bd.photos.length) { if (!bd.loading) bdLoad(); showError('Attendi le foto del giocatore.'); return false; }
  }
  if (step === 'bdphoto' && !bdPhotoOf(bd.photo)) { showError('Tocca una foto.'); return false; }
  if (step === 'bdmode' && !bd.mode) { showError('Scegli il tipo.'); return false; }
  if (step === 'bdoname' && !$('bdoName').value.trim()) { showError('Scrivi il nome.'); return false; }
  if (step === 'potminfo') {
    if (!$('potmSurname').value.trim()) { showError('Scrivi il cognome.'); return false; }
    if (!potmSel.size) { showError('Scegli il mese.'); return false; }
  }
  if (step === 'motminfo') {
    if (!$('motmSurname').value.trim()) { showError('Scrivi il cognome.'); return false; }
    if (!$('motmHome').value.trim() || !$('motmAway').value.trim()) { showError('Scrivi le squadre.'); return false; }
  }
  if (step === 'bdophoto' && !bdo.id) { showError(bdo.loading ? 'Attendi lo scontorno.' : 'Carica la foto.'); return false; }
  if (step === 'bdinfo') {
    if (!$('bdName').value.trim()) { showError('Scrivi il nome.'); return false; }
    if (!/^\d{4}-\d{2}-\d{2}$/.test($('bdBirth').value)) { showError('Scrivi la data di nascita.'); return false; }
  }
  return true;
}

function bdStepValue(step) {
  if (step === 'bdplayer') {
    if (bd.manual) return 'Aggiunto a mano';
    const p = players.find(x => x.name === bd.player); return p ? surnameOf(p) : '';
  }
  if (step === 'bdphoto') {
    const p = bdPhotoOf(bd.photo);
    return p ? 'Scelta' : '';
  }
  if (step === 'bdmode') return labelOf(BD_MODES,bd.mode);
  if (step === 'bdoname') return $('bdoName').value.trim().toUpperCase();
  if (step === 'motminfo') return $('motmSurname').value.trim().toUpperCase();
  if (step === 'potminfo') return [$('potmSurname').value.trim().toUpperCase(), potmMonths().join('/')].filter(Boolean).join(' · ');
  if (step === 'bdophoto') return bdo.loading ? 'Scontorno…' : bdo.id ? 'Caricata' : '';
  if (step === 'bdpos') {
    const f = bd.frame;
    return f.x || f.y || f.zoom !== 1 ? `Zoom ${Math.round(f.zoom * 100)}%` : 'Automatica';
  }
  if (step === 'bdinfo') {
    const d = $('bdBirth').value, a = $('bdAge').value.trim();
    return d ? `${d.slice(8,10)}.${d.slice(5,7)}.${d.slice(0,4)}${a ? ` · ${a} anni` : ''}` : '';
  }
  return null;
}

function bdPayload() {
  const name = $('bdName').value.trim(), birth = $('bdBirth').value;
  if (bd.manual) {
    if (!bdo.id) throw new Error('Carica la foto.');
    if (!name) throw new Error('Scrivi il nome.');
    if (!birth) throw new Error('Scrivi la data di nascita.');
    return {v:1, action:'render', session, data:{kind:'bday', photo_id:bdo.id, name, birth,
      age:$('bdAge').value.trim(), frame:{...bd.frame}}};
  }
  if (!bd.player) throw new Error('Scegli il giocatore.');
  if (!bdPhotoOf(bd.photo)) throw new Error('Scegli la foto.');
  if (!name) throw new Error('Scrivi il nome.');
  if (!birth) throw new Error('Scrivi la data di nascita.');
  return {v:1, action:'render', session, data:{kind:'bday', player:bd.player, photo:bd.photo, name, birth,
    age:$('bdAge').value.trim(), frame:{...bd.frame}}};
}

function bdReset() {
  Object.assign(bd,{mode:'', manual:false, player:'', photos:[], photo:'', loading:false, key:'', birth:'', frame:{x:0, y:0, zoom:1}});
  ['bdPlayerSearch','bdName','bdBirth','bdAge','bdoName',...MOTM_FIELDS,...POTM_FIELDS].forEach(id => { $(id).value = ''; });
  motm.key = '';
  potmSel.clear(); potmMonthRender();
  bdClearUpload();
  bdoTexts();
  bdo.vintage = true;           // filtro d'epoca acceso a ogni nuova grafica
  $('bdoVintage').classList.add('selected');
  $('bdoVintage').setAttribute('aria-checked','true');
}

function initBirthday() {
  initBirthdayEditor();
  potmMonthRender();
  $('bdPlayerSearch').addEventListener('input',() => bdRender());
  $('bdBirth').addEventListener('change',() => { $('bdAge').value = bdAge($('bdBirth').value); renderSteps(); });
  ['bdName','bdAge','bdoName',...MOTM_FIELDS,...POTM_FIELDS].forEach(id => $(id).addEventListener('input',() => renderSteps()));
  // Nome in firma: iniziale maiuscola e resto minuscolo, come uscirà nel poster.
  ['motmName','potmName'].forEach(id => $(id).addEventListener('change',() => { $(id).value = motmName($(id).value); renderSteps(); }));
  $('bdoFile').addEventListener('change',e => bdoUpload(e.target.files && e.target.files[0]));
  $('bdManual').addEventListener('click',bdManualStart);
  $('bdoVintage').addEventListener('click',() => {
    haptic('select');
    bdo.vintage = bdo.vintage === false;
    $('bdoVintage').classList.toggle('selected', bdo.vintage);
    $('bdoVintage').setAttribute('aria-checked', bdo.vintage ? 'true' : 'false');
  });
  $('bdEmoRow').addEventListener('click',bdEmoOpen);
  $('bdEmoClose').addEventListener('click',() => { $('bdEmoSheet').hidden = true; });
  $('bdEmoSheet').addEventListener('click',e => { if (e.target === $('bdEmoSheet')) $('bdEmoSheet').hidden = true; });
  $('bdEmoReset').addEventListener('click',() => bdEmoSave({reset:true}));
  $('bdEmoGrid').addEventListener('click',e => {
    const btn = e.target.closest('[data-n]');
    const sheet = emoSheets[(bdEmo && bdEmo.pack) || 'AroundJuventus'];
    if (!btn || !sheet) return;
    haptic('select');
    bdEmoSave({pack:sheet.pack, index:sheet.items[Number(btn.dataset.n)].index});
  });
}

/* --- Posizione: il poster senza giocatore (sagoma del servizio) e sopra la sagoma del giocatore,
   tagliata alla striscia del nome come nella grafica. Stesse misure della pagina 1500x2000. */
function bdLayout() {
  const frame = $('bdFrame'), img = $('bdPlayer'), page = bdCurPage(), p = bdCur();
  if (!frame.offsetParent || !page || !p) return;
  const stage = $('stage');
  const free = stage.getBoundingClientRect().bottom - frame.getBoundingClientRect().top - 34;
  frame.style.width = `${Math.floor(Math.max(200, Math.min(frame.parentElement.clientWidth, free * page.w / page.h)))}px`;
  const [zmin, zmax] = page.zoom || [0.4, 2.5];
  const f = bd.frame;
  f.zoom = Math.min(zmax, Math.max(zmin, f.zoom));
  f.x = Math.min(0.6, Math.max(-0.6, f.x));
  f.y = Math.min(0.6, Math.max(-0.6, f.y));
  // Man of the Match: testa mai sopra page.top (logo Juventus), piedi mai sotto page.bottom (partita).
  if (page.top != null && page.bottom != null) {
    f.zoom = Math.min(f.zoom, (page.bottom - page.top) / p.height);
    const hh = p.height * f.zoom;
    f.y = Math.min((page.bottom - page.foot) / page.h, Math.max((page.top + hh - page.foot) / page.h, f.y));
  }
  const k = frame.clientWidth / page.w;
  const h = p.height * f.zoom, w = h * ((img.naturalWidth || 3) / (img.naturalHeight || 4));
  img.style.width = `${w * k}px`;
  img.style.height = `${h * k}px`;
  img.style.left = `${(page.cx + f.x * page.w - w * (page.ax != null ? page.ax : 0.5)) * k}px`;   // ax: baricentro
  img.style.top = `${(page.foot + f.y * page.h - h) * k}px`;
  $('bdClip').style.height = `${page.cut / page.h * 100}%`;
}

async function bdGhost() {
  let body;
  try { body = JSON.stringify(kind === 'motm' ? motmPayload() : bdOld() ? bdoPayload() : bdPayload()); } catch (_) { return; }
  const key = body.replace(/"frame":\{[^}]*\}/, '').replace(/"photo(_id)?":"[^"]*"/, '');
  const ghost = $('bdGhost');
  if (key === bd.ghostKey && bd.ghostUrl) { ghost.src = bd.ghostUrl; ghost.hidden = false; return; }
  bd.ghostKey = key;
  ghost.hidden = true;
  $('bdPosHint').textContent = 'Preparo il poster…';
  let real = false;
  showReadyGhost(ghost, () => real || bd.ghostKey !== key, () => { ghost.hidden = false; });
  try {
    const response = await netFetch(`${directBase}/ghost`, {
      method:'POST', headers:{'Content-Type':'application/json','X-ImageGEN-Session':session}, body
    }, 60000, 2);
    if (!response.ok || bd.ghostKey !== key) return;
    const url = URL.createObjectURL(await response.blob());
    if (bd.ghostUrl) { try { URL.revokeObjectURL(bd.ghostUrl); } catch (_) {} }
    bd.ghostUrl = url;
    real = true;
    ghost.src = url;
    ghost.hidden = false;
  } catch (_) {
  } finally {
    if (bd.ghostKey === key) $('bdPosHint').textContent = kind === 'motm' ? 'Il giocatore sta davanti al nome, tra il logo Juventus e la partita.' : bdOld() ? 'Il giocatore sta davanti a HAPPY BIRTHDAY.' : 'Il giocatore finisce sotto la striscia del nome.';
  }
}

function bdOpenPos() {
  const p = bdCur(), img = $('bdPlayer');
  $('bdFrame').classList.toggle('old', bdOld());
  if (p && img.dataset.src !== p.id) {
    img.dataset.src = p.id;
    img.onload = () => bdLayout();
    img.src = p.thumb;
  }
  requestAnimationFrame(bdLayout);
  bdGhost();
}

function initBirthdayEditor() {
  const frame = $('bdFrame');
  const pointers = new Map();
  let last = null;
  const snapshot = () => {
    const pts = [...pointers.values()];
    if (pts.length === 1) return {x:pts[0].x, y:pts[0].y, d:0};
    const [a,b] = pts;
    return {x:(a.x + b.x) / 2, y:(a.y + b.y) / 2, d:Math.hypot(a.x - b.x, a.y - b.y)};
  };
  frame.addEventListener('pointerdown',e => {
    frame.setPointerCapture(e.pointerId);
    pointers.set(e.pointerId,{x:e.clientX, y:e.clientY});
    last = snapshot();
    frame.classList.add('dragging');
  });
  frame.addEventListener('pointermove',e => {
    if (!pointers.has(e.pointerId) || !last) return;
    pointers.set(e.pointerId,{x:e.clientX, y:e.clientY});
    const now = snapshot();
    const fw = frame.clientWidth, fh = frame.clientHeight, page = bdCurPage(), p = bdCur();
    // Aggancio al centro come negli altri editor: il baricentro del giocatore sulla linea verticale
    // di mezzo, il centro della sagoma su quella orizzontale (linea rosa e vibrazione).
    const cx = page ? (page.w / 2 - page.cx) / page.w : 0;
    const cy = page && p ? (page.h / 2 + p.height * bd.frame.zoom / 2 - page.foot) / page.h : 0;
    const hit = snapMove(bd.frame, (now.x - last.x) / fw, (now.y - last.y) / fh, SNAP_PX / fw, SNAP_PX / fh, cx, cy);
    if (now.d && last.d) bd.frame.zoom *= now.d / last.d;
    last = now;
    bdLayout();
    snapSync(bd.frame, hit);
    snapShow(frame, hit);
  });
  const end = e => {
    pointers.delete(e.pointerId);
    last = pointers.size ? snapshot() : null;
    if (!pointers.size) { frame.classList.remove('dragging'); snapEnd(bd.frame); snapClear(frame); renderSteps(); }
  };
  frame.addEventListener('pointerup',end);
  frame.addEventListener('pointercancel',end);
  frame.addEventListener('wheel',e => {
    e.preventDefault();
    bd.frame.zoom *= Math.exp(-e.deltaY * 0.0015);
    bdLayout();
    renderSteps();
  },{passive:false});
  frame.addEventListener('touchmove',e => e.preventDefault(),{passive:false});
  $('bdPosReset').addEventListener('click',() => { haptic('select'); bd.frame = {x:0, y:0, zoom:1}; bdLayout(); renderSteps(); });
  window.addEventListener('resize',bdLayout);
}

// Caricato prima di 10-avvio.js (che disegna già i passi): si collega da solo, la pagina c'è già.
initBirthday();
