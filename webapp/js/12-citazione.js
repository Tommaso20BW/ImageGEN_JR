/* Mini App ImageGen JR. File caricati in ordine da index.html: l'ordine conta. */
/* ---------- CITAZIONE IG ----------
   Link del post -> il servizio legge la pagina embed ufficiale di Instagram (app/instagram.py) e
   tiene le foto come foto caricate. Se le foto sono più di una si sceglie quale usare; testo e nome
   arrivano già compilati e si possono cambiare. Stato in `iq` (02-navigazione.js). */
const iqThumb = id => `${directBase}/photothumb?session=${encodeURIComponent(session)}&id=${encodeURIComponent(id)}`;

// "Avanti" sul link: legge il post (una volta per link). false = resta sulla pagina.
async function iqLoad() {
  const url = $('iqUrl').value.trim();
  if (!url) { showError(`Incolla il link del post ${kind === 'xq' ? 'di X' : kind === 'thq' ? 'di Threads' : 'Instagram'}.`); return false; }
  if (iq.url === url && iq.photos.length) return true;
  if (iq.loading) return false;          // già in lettura (incolla + Avanti insieme)
  if (!directBase || !session) { showError('Sessione vecchia. Riavvia ImageGen dal workflow.'); return false; }
  iq.loading = true;
  $('nextButton').disabled = true;
  $('iqHint').textContent = 'Leggo il post…';
  try {
    const response = await netFetch(`${directBase}/igpost`, {
      method:'POST', headers:{'Content-Type':'application/json','X-ImageGEN-Session':session},
      body:JSON.stringify({v:1, action:'igpost', session, url})
    }, 60000, 2, true);
    const body = await response.json().catch(() => ({}));
    if (!response.ok || !body.ok) throw new Error(body.error || 'Post non leggibile.');
    Object.assign(iq, {url, photos:body.photos || [], sel:(body.photos || []).length === 1 ? 0 : -1,
      avatar:body.avatar_id || '', verified:!!body.verified});
    $('iqText').value = body.text || '';
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
  if (iq.url && $('iqUrl').value.trim() !== iq.url) {
    Object.assign(iq, {url:'', photos:[], sel:-1, avatar:''});
    buildFlow();
    renderSteps();
  }
});
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
  Object.assign(photoState, {id:p.photo_id, w:p.width, h:p.height, url:`${iqThumb(p.photo_id)}&big=1`, x:0, y:0, zoom:1});
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
  try {
    const response = await netFetch(`${directBase}/ghost`, {
      method:'POST', headers:{'Content-Type':'application/json','X-ImageGEN-Session':session}, body
    }, 60000, 2);
    if (!response.ok || iqGhostKey !== key) return;
    const url = URL.createObjectURL(await response.blob());
    if (iqGhostUrl) { try { URL.revokeObjectURL(iqGhostUrl); } catch (_) {} }
    iqGhostUrl = url;
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
    : 'Tieni premuto nel campo e incolla il link di un post Instagram: foto, testo, nome e foto profilo arrivano da soli.';
  $('iqUrl').placeholder = x ? 'https://x.com/…/status/…' : th ? 'https://www.threads.com/@…/post/…' : 'https://www.instagram.com/p/…';
  $('iqPickLead').textContent = x || th
    ? 'Tocca la foto da usare come sfondo, oppure "Sfondo".'
    : 'Il post ha più foto: tocca quella da usare come sfondo.';
  $('iqTextLead').textContent = x || th
    ? 'Testo preso dal post, senza emoji e link finali: puoi cambiarlo.'
    : 'Testo preso dal post, senza emoji e hashtag finali: puoi cambiarlo.';
  $('iqHandleRow').hidden = false;      // @username: X e Instagram
}
