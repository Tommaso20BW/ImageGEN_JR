/* Mini App ImageGen JR. File caricati in ordine da index.html: l'ordine conta. */
/* ---------- DICHIARAZIONI (solo testo) ----------
   Conferenza o intervista incollata -> il servizio la manda a Claude con le regole delle news
   (app/dichiarazioni.py) -> 1-3 proposte, ognuna in due versioni: Telegram (nomi in grassetto) e X
   (hashtag). Si tocca la proposta da usare (nessuna è già scelta) e va nel bot: prima il testo
   Telegram, poi quello per X in risposta. Stato in `dich`. */
const dich = {posts:[], sel:-1, busy:false, key:''};

function dichReset() {
  Object.assign(dich, {posts:[], sel:-1, busy:false, key:''});
  if ($('dichText')) { $('dichText').value = ''; $('dichNote').value = ''; $('dichHint').textContent = ''; }
}

// "Scrivi la notizia": chiede le proposte (una volta per testo). false = resta sulla pagina.
async function dichConvert() {
  const text = $('dichText').value.trim(), note = $('dichNote').value.trim();
  if (text.length < 20) { showError('Incolla il testo della conferenza o dell’intervista.'); return false; }
  const key = `${text}\n${note}`;
  if (dich.key === key && dich.posts.length) return true;
  if (dich.busy) return false;
  if (!directBase || !session) { showError('Sessione vecchia. Riavvia ImageGen dal workflow.'); return false; }
  dich.busy = true;
  $('nextButton').disabled = true;
  $('dichHint').textContent = 'Claude sta scrivendo… (di solito meno di un minuto)';
  const ask = async payload => {
    const response = await netFetch(`${directBase}/dichiarazioni`, {
      method:'POST', headers:{'Content-Type':'application/json','X-ImageGEN-Session':session},
      body:JSON.stringify({v:1, action:'dichiarazioni', session, ...payload})
    }, 30000, 3, true);
    const body = await response.json().catch(() => ({}));
    if (!response.ok || !body.ok) throw new Error(body.error || 'Notizia non scritta. Riprova.');
    return body;
  };
  try {
    // Claude lavora in sottofondo nel servizio: qui si chiede ogni 2 secondi se ha finito (max 4 minuti).
    const {job} = await ask({text, note});
    let body = {done:false};
    for (let i = 0; i < 120 && !body.done; i++) {
      await new Promise(resolve => setTimeout(resolve, 2000));
      body = await ask({job});
    }
    if (!body.done) throw new Error('Claude non risponde. Riprova tra poco.');
    Object.assign(dich, {posts:body.posts || [], sel:-1, key});
    $('dichHint').textContent = '';
    haptic('success');
    return true;
  } catch (error) {
    $('dichHint').textContent = '';
    showError(error && error.name === 'AbortError' ? 'Claude non risponde. Riprova tra poco.' : (error.message || 'Notizia non scritta.'));
    return false;
  } finally {
    dich.busy = false;
    $('nextButton').disabled = sessionExpired();
  }
}

// Una scheda per proposta: Telegram e X uno sotto l'altro, con i caratteri contati come X.
function dichRender() {
  const box = $('dichList');
  box.innerHTML = '';
  $('dichEmpty').hidden = dich.posts.length > 0;
  dich.posts.forEach((p, i) => {
    const card = document.createElement('div');
    card.className = 'dich-card' + (i === dich.sel ? ' sel' : '');
    card.setAttribute('role', 'button');
    card.tabIndex = 0;
    const count = n => `<span class="dich-n${n > p.limit ? ' over' : ''}">${n}/${p.limit}</span>`;
    card.innerHTML = `<div class="dich-top"><span class="dich-tema"></span><span class="dich-ck"></span></div>` +
      `<div class="dich-lab">Telegram ${count(p.tg_len)}</div><div class="dich-txt dich-tg"></div>` +
      `<div class="dich-lab">X ${count(p.x_len)}</div><div class="dich-txt dich-x"></div>`;
    card.querySelector('.dich-tema').textContent = p.tema || `Proposta ${i + 1}`;
    card.querySelector('.dich-tg').innerHTML = p.tg;          // HTML di Telegram fatto dal servizio (testo già con l'escape)
    card.querySelector('.dich-x').textContent = p.x;
    card.addEventListener('click', () => { haptic('select'); dich.sel = i; dichRender(); });
    box.appendChild(card);
  });
}

// "Invia al bot": la proposta scelta arriva in chat, Telegram e poi X in risposta.
async function dichSend() {
  const post = dich.posts[dich.sel];
  if (!post) { showError('Tocca la proposta da usare.'); return; }
  if (dich.busy) return;
  dich.busy = true;
  $('nextButton').disabled = true;
  try {
    const response = await netFetch(`${directBase}/dichiarazioni`, {
      method:'POST', headers:{'Content-Type':'application/json','X-ImageGEN-Session':session},
      body:JSON.stringify({v:1, action:'dichiarazioni', session, post:{raw:post.raw}})
    }, 30000, 2, false);
    const body = await response.json().catch(() => ({}));
    if (!response.ok || !body.ok) throw new Error(body.error || 'Invio non riuscito.');
    haptic('success');
    showToastSafe('Inviata al bot: Telegram e, in risposta, X.');
  } catch (error) {
    showError(error.message || 'Invio non riuscito.');
  } finally {
    dich.busy = false;
    $('nextButton').disabled = sessionExpired();
  }
}

$('dichRetry').addEventListener('click', async () => {
  haptic('select');
  dich.key = '';
  if (await dichConvert()) dichRender();
});
