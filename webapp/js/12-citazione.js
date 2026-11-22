/* Mini App ImageGen JR. File caricati in ordine da index.html: l'ordine conta. */
/* ---------- CITAZIONE IG ----------
   Link del post -> il servizio legge la pagina embed ufficiale di Instagram (app/instagram.py) e
   tiene le foto come foto caricate. Se le foto sono più di una si sceglie quale usare; testo e nome
   arrivano già compilati e si possono cambiare. Stato in `iq` (02-navigazione.js). */
const iqThumb = id => `${directBase}/photothumb?session=${encodeURIComponent(session)}&id=${encodeURIComponent(id)}`;

// "Avanti" sul link: legge il post (una volta per link). false = resta sulla pagina.
async function iqLoad() {
  const url = $('iqUrl').value.trim();
  if (iq.mode === 'story' && !url) { iqNoLink(); return true; }    // storia senza link: tutto dallo screenshot
  if (!url) { showError(`Incolla il link del post ${kind === 'xq' ? 'di X' : kind === 'thq' ? 'di Threads' : 'Instagram'}.`); return false; }
  if (iq.url === url && (iq.photos.length || iq.story)) return true;
  if (iq.loading) return false;          // già in lettura (incolla + Avanti insieme)
  if (!directBase || !session) { showError('Sessione vecchia. Riavvia ImageGen dal workflow.'); return false; }
  iq.loading = true;
  $('nextButton').disabled = true;
  $('iqHint').textContent = iq.mode === 'story' ? 'Leggo la storia…' : 'Leggo il post…';
  try {
    const response = await netFetch(`${directBase}/igpost`, {
      method:'POST', headers:{'Content-Type':'application/json','X-ImageGEN-Session':session},
      body:JSON.stringify({v:1, action:'igpost', session, url})
    }, 60000, 2, true);
    const body = await response.json().catch(() => ({}));
    if (!response.ok || !body.ok) throw new Error(body.error || 'Post non leggibile.');
    if (kind === 'igq' && iq.mode === 'story' && !body.story) throw new Error('Questo è il link di un post: torna indietro e scegli Post.');
    if (iqIsComment() && body.story) throw new Error('Serve il link di un post, non di una storia.');
    if (kind === 'igq' && !iqIsComment()) iq.mode = body.story ? 'story' : 'post';     // link di una storia in "Post": passa a Storia
    Object.assign(iq, {url, photos:body.photos || [], sel:(body.photos || []).length === 1 ? 0 : -1,
      avatar:body.avatar_id || '', verified:!!body.verified, story:!!body.story});
    if (iq.story) clearPhoto();           // storia: la foto la carichi tu nell'editor
    $('iqText').value = body.text || '';
    iqTrReset();
    $('iqName').value = body.user || '';
    $('iqHandle').value = body.handle || '';
    $('iqAvatar').style.backgroundImage = iq.avatar ? `url("${iqThumb(iq.avatar)}")` : '';
    $('iqHint').textContent = '';
    haptic('success');
    buildFlow();
    return true;
  } catch (error) {
    $('iqHint').textContent = '';
    showError(error && error.name === 'AbortError' ? `${kind === 'xq' ? 'X' : kind === 'thq' ? 'Threads' : 'Instagram'} non risponde. Riprova tra poco.` : (error.message || 'Post non leggibile.'));
    return false;
  } finally {
    iq.loading = false;
    $('nextButton').disabled = sessionExpired();
  }
}

// STORIA: screenshot del telefono -> il servizio ritaglia la storia (senza ora, barrette, nome e barra
// dei messaggi) e la foto profilo, che si usa se il link non l'ha data.
function iqShotRefresh() {
  const p = iq.photos[0];
  $('iqShotThumb').hidden = !p;
  $('iqShotThumb').style.backgroundImage = p ? `url("${iqThumb(p.photo_id)}")` : '';
  $('iqShotPick').textContent = iq.shotLoading ? 'Caricamento…' : p ? 'Cambia screenshot' : 'Allega screenshot';
  $('iqShotPick').disabled = !!iq.shotLoading;
  $('iqShotHint').textContent = p && !iq.shotCropped ? 'Non sembra uno screenshot di una storia: uso l’immagine intera.' : '';
}
async function iqUploadShot(file) {
  if (!file) return;
  clearError();
  if (!directBase || !session) { showError('Sessione vecchia. Riavvia ImageGen dal workflow.'); return; }
  iq.shotLoading = true; iqShotRefresh();
  try {
    const {blob, type} = await preparePhoto(file);
    const response = await netFetch(`${directBase}/upload`, {
      method:'POST', headers:{'Content-Type':type, 'X-ImageGEN-Session':session, 'X-ImageGEN-Crop':'story'}, body:blob
    }, 60000);
    const body = await response.json().catch(() => ({}));
    if (!response.ok || !body.ok) throw new Error(body.error || 'Caricamento non riuscito.');
    clearPhoto();
    Object.assign(iq, {photos:[{photo_id:body.photo_id, width:body.width, height:body.height}], sel:0, shotCropped:!!body.cropped,
      bars:Array.isArray(body.bars) ? body.bars : null});
    if (!iq.avatar && body.avatar_id) {
      iq.avatar = body.avatar_id;
      $('iqAvatar').style.backgroundImage = `url("${iqThumb(iq.avatar)}")`;
    }
    haptic('success');
    iq.shotLoading = false; iqShotRefresh();
    renderSteps();
    if (iq.shotCropped && flow[flowIndex] === 'iqshot') nextField(true);
  } catch (err) {
    showError(err && err.message ? err.message : 'Caricamento non riuscito.');
  } finally {
    iq.shotLoading = false; iqShotRefresh();
  }
}
$('iqVerRow').addEventListener('click', () => {
  haptic('select');
  iq.verified = !iq.verified;
  $('iqVerCk').textContent = iq.verified ? '✓' : '';
});
$('iqShotPick').addEventListener('click', () => { if (!iq.shotLoading) $('iqShotFile').click(); });
$('iqShotFile').addEventListener('change', e => { iqUploadShot(e.target.files && e.target.files[0]); e.target.value = ''; });

function renderIqPick() {
  const box = $('iqPhotos');
  box.innerHTML = '';
  iq.photos.forEach((p, i) => {
    const b = document.createElement('button');
    b.type = 'button';
    b.className = 'iq-ph' + (i === iq.sel ? ' on' : '');
    b.style.backgroundImage = `url("${iqThumb(p.photo_id)}")`;
    b.setAttribute('aria-label', `Foto ${i + 1}`);
    b.innerHTML = p.bg ? '<span class="bg">Sfondo</span>' : `<span>${i + 1}</span>`;
    b.addEventListener('click', () => {
      haptic('select');
      iq.sel = i;
      renderIqPick();
      nextField(true);
    });
    box.appendChild(b);
  });
}

// Link cambiato: il post letto prima non vale più.
$('iqUrl').addEventListener('input', () => {
  clearError();
  if ((iq.url || iq.noLink) && $('iqUrl').value.trim() !== iq.url) {
    Object.assign(iq, {url:'', photos:[], sel:-1, avatar:'', story:iq.mode === 'story', noLink:false, bars:null});
    iqcReset();
    buildFlow();
    renderSteps();
  }
});
// Post o Storia (solo Citazione Instagram): cambiando tipo si riparte dal link.
function iqReset(story, noLink) {
  Object.assign(iq, {url:'', photos:[], sel:-1, avatar:'', verified:false, story, noLink, bars:null, shotCropped:false});
  $('iqUrl').value = '';
  $('iqText').value = '';
  iqTrReset();
  $('iqName').value = '';
  $('iqHandle').value = '';
  $('iqAvatar').style.backgroundImage = '';
  iqcReset();
  clearPhoto();
}
function iqSetMode(mode) {
  iq.mode = mode;
  iqReset(mode === 'story', false);
  buildFlow();
  renderSteps();
}
// Storia di cui il link non si legge (scaduta, account privato…): solo screenshot, nome e @ a mano.
function iqNoLink() {
  clearError();
  iqReset(true, true);
  buildFlow();
}
$('iqNoLink').addEventListener('click', () => { iqNoLink(); nextField(true); });
$('iqUrl').addEventListener('keydown', e => { if (e.key === 'Enter') { e.preventDefault(); nextField(true); } });
// Link incollato nel campo: il post si legge subito, senza "Avanti".
const looksIg = v => /instagram\.com\/|instagr\.am\/|(?:^|\/\/|\.)(?:x|twitter)\.com\/[^/\s]+\/status\/|threads\.(?:com|net)\/(?:@[\w.]+\/post|share)\//i.test(v);
function iqUseLink(text) {
  const link = (String(text || '').match(/https?:\/\/\S+/) || [String(text || '').trim()])[0];
  $('iqUrl').value = link;
  $('iqUrl').dispatchEvent(new Event('input'));
  if (looksIg(link) && flow[flowIndex] === 'iqurl') nextField(true);
}
$('iqUrl').addEventListener('paste', () => setTimeout(() => {
  if (looksIg($('iqUrl').value)) iqUseLink($('iqUrl').value);
}, 0));

/* ----- Editor della foto (lo stesso di Matchday / Post): sposta e ingrandisci lo sfondo ----- */
// La foto scelta del post entra nell'editor; sopra, la sagoma vera (riquadro, testo, account, JR)
// fatta dal servizio senza foto. Cambiando foto si riparte dal centro.
function iqSyncPhoto() {
  const p = iq.photos[iq.sel];
  if (!p) return;
  if (photoState.id === p.photo_id) return;
  // Foto caricata a mano nell'editor: resta quella (non è una del post).
  if (photoState.id && !iq.photos.some(x => x.photo_id === photoState.id)) return;
  clearPhoto();
  Object.assign(photoState, {id:p.photo_id, w:p.width, h:p.height, url:`${iqThumb(p.photo_id)}&big=1`, x:0, y:0, zoom:1, rot:0});
  $('photoImg').src = photoState.url;
  $('photoImg').hidden = false;
  $('photoEmpty').hidden = true;
}

let iqGhostKey = '', iqGhostUrl = '';
async function iqGhost(overlay) {
  let body;
  try { body = JSON.stringify(buildPayload(true)); } catch (_) { return; }
  const key = body.replace(/"frame":\{[^}]*\}/, '');
  if (key === iqGhostKey && iqGhostUrl) { overlay.src = iqGhostUrl; overlay.style.visibility = ''; return; }
  iqGhostKey = key;
  overlay.style.visibility = 'hidden';
  let real = false;
  showReadyGhost(overlay, () => real || iqGhostKey !== key, () => { overlay.style.visibility = ''; });
  try {
    const response = await netFetch(`${directBase}/ghost`, {
      method:'POST', headers:{'Content-Type':'application/json','X-ImageGEN-Session':session}, body
    }, 60000, 2);
    if (!response.ok || iqGhostKey !== key) return;
    const url = URL.createObjectURL(await response.blob());
    if (iqGhostUrl) { try { URL.revokeObjectURL(iqGhostUrl); } catch (_) {} }
    iqGhostUrl = url;
    real = true;
    overlay.src = url;
    overlay.style.visibility = '';
  } catch (_) {}
}

/* ----- Citazione X: stesse pagine della Citazione IG, testi e campo @account diversi ----- */
function iqTexts() {
  const x = kind === 'xq', th = kind === 'thq';
  const net = x ? 'X' : th ? 'Threads' : 'Instagram';
  document.querySelectorAll('[data-screen^="iq"] .eyebrow').forEach(e => { e.textContent = `Citazione ${net}`; });
  $('iqUrlLead').textContent = x || th
    ? `Tieni premuto nel campo e incolla il link di un post di ${x ? 'X' : 'Threads'}: testo, nome, account, foto profilo e foto arrivano da soli.`
    : iq.mode === 'story' ? 'Incolla il link della storia: arrivano nome e foto profilo. Se non ce l’hai o non funziona, continua senza link.'
    : 'Tieni premuto nel campo e incolla il link di un post Instagram: foto, testo, nome e foto profilo arrivano da soli.';
  $('iqUrlTitle').textContent = kind === 'igq' && iq.mode === 'story' ? 'Link della storia' : 'Link del post';
  $('iqUrl').placeholder = x ? 'https://x.com/…/status/…' : th ? 'https://www.threads.com/@…/post/…'
    : iq.mode === 'story' ? 'https://www.instagram.com/stories/… (facoltativo)' : 'https://www.instagram.com/p/…';
  $('iqPickLead').textContent = x || th
    ? 'Tocca la foto da usare come sfondo, oppure "Sfondo".'
    : 'Il post ha più foto: tocca quella da usare come sfondo.';
  $('iqTextLead').textContent = x || th
    ? 'Testo preso dal post, senza emoji e link finali: puoi cambiarlo.'
    : iq.noLink ? 'Scrivi nome e @account della storia e tocca la spunta blu se è verificato: la foto profilo arriva dallo screenshot.'
    : iq.story ? 'Account della storia: nome, @account e spunta blu (il link non dice se è verificato).'
    : 'Testo preso dal post, senza emoji e hashtag finali: puoi cambiarlo.';
  $('iqText').hidden = iq.story;
  $('iqNoLinkBox').hidden = kind !== 'igq' || iq.mode !== 'story';
  $('iqTextTitle').textContent = iq.story ? 'Account' : 'Testo e account';
  $('iqVerRow').hidden = !iq.story;
  $('iqVerCk').textContent = iq.verified ? '✓' : '';
  $('iqHandleRow').hidden = false;      // @username: X e Instagram
}

/* ----- Traduttore: il testo del post in italiano con un tocco (app/translate.py) -----
   Dopo la traduzione lo stesso pulsante rimette il testo originale. */
const iqTr = {orig:null, busy:false};
function iqTrRefresh() {
  const b = $('iqTranslate');
  b.textContent = iqTr.busy ? 'Traduco…' : iqTr.orig !== null ? 'Rimetti il testo originale' : 'Traduci in italiano';
  b.disabled = iqTr.busy;
}
function iqTrReset() { iqTr.orig = null; iqTrRefresh(); }
async function iqTranslate() {
  clearError();
  if (iqTr.busy) return;
  if (iqTr.orig !== null) { $('iqText').value = iqTr.orig; iqTrReset(); haptic('select'); return; }
  const text = $('iqText').value.trim();
  if (!text) { showError('Non c’è testo da tradurre.'); return; }
  if (!directBase || !session) { showError('Sessione vecchia. Riavvia ImageGen dal workflow.'); return; }
  haptic('select');
  iqTr.busy = true; iqTrRefresh();
  try {
    const response = await netFetch(`${directBase}/translate`, {
      method:'POST', headers:{'Content-Type':'application/json','X-ImageGEN-Session':session},
      body:JSON.stringify({v:1, action:'translate', session, text})
    }, 30000, 2, true);
    const body = await response.json().catch(() => ({}));
    if (!response.ok || !body.ok) throw new Error(body.error || 'Traduzione non riuscita.');
    if (body.source === 'it') { showError('Il testo è già in italiano.'); return; }
    iqTr.orig = $('iqText').value;
    $('iqText').value = body.text;
    haptic('success');
  } catch (error) {
    showError(error && error.name === 'AbortError' ? 'ImageGEN non risponde. Riprova.' : (error.message || 'Traduzione non riuscita.'));
  } finally {
    iqTr.busy = false; iqTrRefresh();
  }
}
$('iqTranslate').addEventListener('click', iqTranslate);


/* ----- Commento IG: foto del post con UN commento scelto -----
   Screenshot dei commenti -> il servizio li legge (app/ig_comments.py) -> si tocca quello da usare
   (nessuno è già scelto) -> testo correggibile -> nell'editor il riquadro va sotto, al centro o sopra. */
const IQC_POS = [['sopra','Sopra'],['centro','Centro'],['sotto','Sotto']];
const iqc = {list:[], sel:-1, busy:false, picking:false, pos:'sotto', avatar:'', verified:false};
function iqIsComment() { return kind === 'igq' && iq.mode === 'comment'; }
function iqcReset() {
  Object.assign(iqc, {list:[], sel:-1, busy:false, picking:false, pos:'sotto', avatar:'', verified:false});
  ['iqcText','iqcName','iqcTime','iqcLikes'].forEach(id => { $(id).value = ''; });
  $('iqcHint').textContent = '';
}
function iqcRender() {
  $('iqcPick').textContent = iqc.busy ? 'Leggo i commenti…' : iqc.list.length ? 'Aggiungi altro screenshot' : 'Allega screenshot';
  $('iqcPick').disabled = iqc.busy;
  const box = $('iqcList');
  box.hidden = !iqc.list.length;
  box.innerHTML = '';
  iqc.list.forEach((c, i) => {
    const b = document.createElement('button');
    b.type = 'button';
    b.className = 'iqc-row' + (i === iqc.sel ? ' on' : '');
    const av = document.createElement('span');
    av.className = 'iq-av';
    if (c.avatar) av.style.backgroundImage = `url("data:image/jpeg;base64,${c.avatar}")`;
    const body = document.createElement('span');
    body.className = 'iqc-body';
    const who = document.createElement('b');
    who.textContent = [c.user, c.time].filter(Boolean).join(' · ');
    const text = document.createElement('span');
    text.textContent = c.text;
    body.append(who, text);
    b.append(av, body);
    if (c.likes) {
      const likes = document.createElement('em');
      likes.textContent = `♡ ${c.likes}`;
      b.append(likes);
    }
    b.addEventListener('click', () => iqcChoose(i));
    box.appendChild(b);
  });
}
async function iqcUpload(files) {
  if (!files.length || iqc.busy) return;
  clearError();
  if (!directBase || !session) { showError('Sessione vecchia. Riavvia ImageGen dal workflow.'); return; }
  iqc.busy = true; $('iqcHint').textContent = ''; iqcRender();
  try {
    for (const file of files) {
      const {blob, type} = await preparePhoto(file);
      const response = await netFetch(`${directBase}/upload`, {
        method:'POST', headers:{'Content-Type':type, 'X-ImageGEN-Session':session, 'X-ImageGEN-Crop':'comments'}, body:blob
      }, 90000);
      const body = await response.json().catch(() => ({}));
      if (!response.ok || !body.ok) throw new Error(body.error || 'Screenshot non leggibile.');
      const seen = new Set(iqc.list.map(iqcKey));
      (body.comments || []).forEach(c => { if (!seen.has(iqcKey(c))) { seen.add(iqcKey(c)); iqc.list.push(c); } });
    }
    haptic('success');
    $('iqcHint').textContent = iqc.list.length ? 'Le emoji non si leggono: nel passaggio dopo puoi correggere il testo.'
      : 'Non ho trovato commenti: prova con un altro screenshot o scrivilo a mano.';
  } catch (err) {
    showError(err && err.name === 'AbortError' ? 'Lettura troppo lenta. Riprova.' : (err.message || 'Screenshot non leggibile.'));
  } finally {
    iqc.busy = false; iqcRender();
  }
}
const iqcKey = c => `${c.user} ${c.text}`.toLocaleLowerCase().replace(/[^\p{L}\p{N}]+/gu, '');
async function iqcAvatarId(base64) {
  if (!base64) return '';
  try {
    const bytes = Uint8Array.from(atob(base64), ch => ch.charCodeAt(0));
    const response = await netFetch(`${directBase}/upload`, {
      method:'POST', headers:{'Content-Type':'image/jpeg', 'X-ImageGEN-Session':session}, body:new Blob([bytes], {type:'image/jpeg'})
    }, 30000);
    const body = await response.json().catch(() => ({}));
    return response.ok && body.ok ? body.photo_id : '';
  } catch (_) { return ''; }
}
async function iqcChoose(i) {
  if (iqc.picking) return;
  haptic('select');
  iqc.picking = true;
  iqc.sel = i;
  iqcRender();
  const c = iqc.list[i];
  $('iqcText').value = c.text;
  $('iqcName').value = c.user;
  $('iqcTime').value = c.time || '';
  $('iqcLikes').value = c.likes || '';
  iqc.verified = false;
  iqc.avatar = await iqcAvatarId(c.avatar);
  iqc.picking = false;
  renderSteps();
  if (flow[flowIndex] === 'iqcshot') nextField(true);
}
function iqcRefreshVerified() { $('iqcVerCk').textContent = iqc.verified ? '✓' : ''; }
function iqcRenderPos() {
  $('iqcPos').querySelectorAll('button').forEach(b => {
    const on = b.dataset.v === iqc.pos;
    b.classList.toggle('on', on);
    b.setAttribute('aria-checked', on ? 'true' : 'false');
  });
}
IQC_POS.forEach(([v, label]) => {
  const b = document.createElement('button');
  b.type = 'button';
  b.dataset.v = v;
  b.setAttribute('role', 'radio');
  b.textContent = label;
  b.addEventListener('click', () => {
    if (iqc.pos === v) return;
    haptic('select');
    iqc.pos = v;
    iqcRenderPos();
    updatePhotoOverlay();
  });
  $('iqcPos').appendChild(b);
});
$('iqcPick').addEventListener('click', () => { if (!iqc.busy) $('iqcFile').click(); });
$('iqcFile').addEventListener('change', e => { iqcUpload([...(e.target.files || [])]); e.target.value = ''; });
$('iqcManual').addEventListener('click', () => {
  haptic('select');
  Object.assign(iqc, {sel:-2, avatar:'', verified:false});
  ['iqcText','iqcName','iqcTime','iqcLikes'].forEach(id => { $(id).value = ''; });
  iqcRender();
  nextField(true);
});
$('iqcVerRow').addEventListener('click', () => {
  haptic('select');
  iqc.verified = !iqc.verified;
  iqcRefreshVerified();
});
