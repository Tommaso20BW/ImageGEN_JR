/* Mini App ImageGen JR. File caricati in ordine da index.html: l'ordine conta. */
/* ---------- CITAZIONE IG ----------
   Link del post -> il servizio legge la pagina embed ufficiale di Instagram (app/instagram.py) e
   tiene le foto come foto caricate. Se le foto sono più di una si sceglie quale usare; testo e nome
   arrivano già compilati e si possono cambiare. Stato in `iq` (02-navigazione.js). */
const iqThumb = id => `${directBase}/photothumb?session=${encodeURIComponent(session)}&id=${encodeURIComponent(id)}`;

// "Avanti" sul link: legge il post (una volta per link). false = resta sulla pagina.
async function iqLoad() {
  const url = $('iqUrl').value.trim();
  if (!url) { showError('Incolla il link del post Instagram.'); return false; }
  if (iq.url === url && iq.photos.length) return true;
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
      avatar:body.avatar_id || ''});
    $('iqText').value = body.text || '';
    $('iqName').value = body.user || '';
    $('iqAvatar').style.backgroundImage = iq.avatar ? `url("${iqThumb(iq.avatar)}")` : '';
    $('iqHint').textContent = '';
    haptic('success');
    buildFlow();
    return true;
  } catch (error) {
    $('iqHint').textContent = '';
    showError(error && error.name === 'AbortError' ? 'Instagram non risponde. Riprova tra poco.' : (error.message || 'Post non leggibile.'));
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
    b.innerHTML = `<span>${i + 1}</span>`;
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
$('iqPaste').addEventListener('click', async () => {
  try {
    const text = await navigator.clipboard.readText();
    if (text) { $('iqUrl').value = text.trim(); $('iqUrl').dispatchEvent(new Event('input')); }
  } catch (_) { showError('Non posso leggere gli appunti: tieni premuto nel campo e scegli Incolla.'); }
});
