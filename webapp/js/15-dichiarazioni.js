/* Mini App ImageGen JR. File caricati in ordine da index.html: l'ordine conta. */
/* ---------- DICHIARAZIONI (solo testo) ----------
   Testo già scritto (conferenza, intervista), anche diviso in blocchi COMPLETO / 240 -> il servizio
   (app/dichiarazioni.py) fa per ogni blocco la versione Telegram (emoji del canale, nomi e temi in
   grassetto, firma) e quella per X (hashtag, @SkySport). Si toccano i blocchi da mandare (nessuno è
   già scelto) e vanno nel bot: prima Telegram, poi X in risposta. Stato in `dich`. */
const dich = {posts:[], sel:[], busy:false, key:''};

function dichReset() {
  Object.assign(dich, {posts:[], sel:[], busy:false, key:''});
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
  if (dich.key === text && dich.posts.length) return true;
  if (dich.busy) return false;
  if (!directBase || !session) { showError('Sessione vecchia. Riavvia ImageGen dal workflow.'); return false; }
  dich.busy = true;
  $('nextButton').disabled = true;
  try {
    const body = await dichPost({text}, 20000);
    Object.assign(dich, {posts:body.posts || [], sel:[], key:text});
    if (!dich.posts.length) throw new Error('Nessun testo trovato.');
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

// Una scheda per blocco: Telegram e X uno sotto l'altro, con i caratteri contati come X.
function dichRender() {
  const box = $('dichList');
  box.innerHTML = '';
  dich.posts.forEach((p, i) => {
    const card = document.createElement('div');
    card.className = 'dich-card' + (dich.sel.includes(i) ? ' sel' : '');
    card.setAttribute('role', 'button');
    card.tabIndex = 0;
    const count = n => `<span class="dich-n${p.limit && n > p.limit ? ' over' : ''}">${p.limit ? `${n}/${p.limit}` : n}</span>`;
    card.innerHTML = `<div class="dich-top"><span class="dich-tema"></span><span class="dich-ck"></span></div>` +
      `<div class="dich-lab">Telegram ${count(p.tg_len)}</div><div class="dich-txt dich-tg"></div>` +
      `<div class="dich-lab">X ${count(p.x_len)}</div><div class="dich-txt dich-x"></div>`;
    card.querySelector('.dich-tema').textContent = p.tema || `Testo ${i + 1}`;
    card.querySelector('.dich-tg').innerHTML = p.tg;          // HTML di Telegram fatto dal servizio (testo già con l'escape)
    card.querySelector('.dich-x').textContent = p.x;
    card.addEventListener('click', () => {
      haptic('select');
      dich.sel = dich.sel.includes(i) ? dich.sel.filter(n => n !== i) : [...dich.sel, i].sort((a, b) => a - b);
      dichRender();
    });
    box.appendChild(card);
  });
}

// "Invia al bot": i blocchi scelti arrivano in chat, per ognuno Telegram e poi X in risposta.
async function dichSend() {
  if (!dich.sel.length) { showError(dich.posts.length > 1 ? 'Tocca i testi da mandare.' : 'Tocca il testo da mandare.'); return; }
  if (dich.busy) return;
  dich.busy = true;
  $('nextButton').disabled = true;
  try {
    for (const i of dich.sel) await dichPost({post:{raw:dich.posts[i].raw}}, 30000);
    haptic('success');
    showToastSafe('Nel bot: Telegram e, in risposta, X.');
  } catch (error) {
    showError(error.message || 'Invio non riuscito.');
  } finally {
    dich.busy = false;
    $('nextButton').disabled = sessionExpired();
  }
}
