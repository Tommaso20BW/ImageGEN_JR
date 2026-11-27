/* Mini App ImageGen JR. File caricati in ordine da index.html: l'ordine conta. */
/* ---------- DICHIARAZIONI (solo testo) ----------
   Testo già scritto (conferenza, intervista), anche in due blocchi COMPLETO / 240 -> il servizio
   (app/dichiarazioni.py) fa la versione Telegram dal completo (emoji del canale, nomi e temi in
   grassetto, parlato in corsivo, firma) e quella per X dal 240 (hashtag, @SkySport); con un blocco
   solo, lo stesso testo per tutti e due. Si vedono le due versioni e "Invia al bot" le manda:
   prima Telegram, poi X in risposta. Stato in `dich`. */
const dich = {post:null, busy:false, key:''};

function dichReset() {
  Object.assign(dich, {post:null, busy:false, key:''});
  if ($('dichText')) { $('dichText').value = ''; $('dichHint').textContent = ''; }
}

function dichPost(payload, timeout) {
  return netFetch(`${directBase}/dichiarazioni`, {
    method:'POST', headers:{'Content-Type':'application/json','X-ImageGEN-Session':session},
    body:JSON.stringify({v:1, action:'dichiarazioni', session, ...payload})
  }, timeout, 2, false).then(async response => {
    const body = await response.json().catch(() => ({}));
    if (!response.ok || !body.ok) throw new Error(body.error || 'Non riuscito. Riprova.');
    return body;
  });
}

// "Prepara i testi": versioni Telegram e X (una volta per testo). false = resta sulla pagina.
async function dichConvert() {
  const text = $('dichText').value.trim();
  if (text.length < 5) { showError('Incolla il testo da sistemare.'); return false; }
  if (dich.key === text && dich.post) return true;
  if (dich.busy) return false;
  if (!directBase || !session) { showError('Sessione vecchia. Riavvia ImageGen dal workflow.'); return false; }
  dich.busy = true;
  $('nextButton').disabled = true;
  try {
    const body = await dichPost({text}, 20000);
    if (!body.post) throw new Error('Nessun testo trovato.');
    Object.assign(dich, {post:body.post, key:text});
    haptic('success');
    return true;
  } catch (error) {
    showError(error && error.name === 'AbortError' ? 'Il servizio non risponde. Riprova.' : (error.message || 'Non riuscito.'));
    return false;
  } finally {
    dich.busy = false;
    $('nextButton').disabled = sessionExpired();
  }
}

// Telegram e X uno sotto l'altro, con il blocco da cui vengono e i caratteri contati come X.
function dichRender() {
  const box = $('dichList');
  box.innerHTML = '';
  const p = dich.post;
  if (!p) return;
  const card = document.createElement('div');
  card.className = 'dich-card';
  // il limite (240) vale solo per X
  const count = (n, limit) => `<span class="dich-n${limit && n > limit ? ' over' : ''}">${limit ? `${n}/${limit}` : n}</span>`;
  const from = label => label ? ` · ${label}` : '';
  card.innerHTML = `<div class="dich-lab">Telegram${from(p.tg_label)} ${count(p.tg_len, 0)}</div><div class="dich-txt dich-tg"></div>` +
    `<div class="dich-lab">X${from(p.x_label)} ${count(p.x_len, p.limit)}</div><div class="dich-txt dich-x"></div>`;
  card.querySelector('.dich-tg').innerHTML = p.tg;            // HTML di Telegram fatto dal servizio (testo già con l'escape)
  card.querySelector('.dich-x').textContent = p.x;
  box.appendChild(card);
}

// "Invia al bot": Telegram e poi X in risposta.
async function dichSend() {
  if (!dich.post || dich.busy) return;
  dich.busy = true;
  $('nextButton').disabled = true;
  try {
    await dichPost({post:{raw:dich.post.raw}}, 30000);
    haptic('success');
    showToastSafe('Nel bot: Telegram e, in risposta, X.');
  } catch (error) {
    showError(error.message || 'Invio non riuscito.');
  } finally {
    dich.busy = false;
    $('nextButton').disabled = sessionExpired();
  }
}
