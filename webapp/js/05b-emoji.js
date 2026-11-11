/* ---------- Impostazioni › squadra › Emoji ----------
   Emoji della squadra avversaria nel testo del Matchday. Riga "Emoji" nella pagina della squadra,
   pagina 'emoji': in alto quella scelta, poi le consigliate (le più simili al logo) e tutti i pack.
   La scelta va in team_overrides/emoji.json (repo degli asset) e vince su quella automatica. */
const emoSheets = {};          // pack -> griglia {sprite, cell, cols, items}

const emoTeamPayload = T => ({name:T.team.name, display_name:T.team.display_name || '', override_key:T.key || '',
  aliases:T.team.aliases || []});

// Dati emoji della squadra aperta (T.emo): emoji in uso, automatica, consigliate, pack.
function emoLoadTeam(T, force = false) {
  if (!T || T.isNew || !T.team || (T.emo && !force)) return Promise.resolve();
  return setPost({action:'emoji_team', team:emoTeamPayload(T)})
    .then(body => { T.emo = body; })
    .catch(() => { T.emo = {error:true}; })
    .finally(() => { if (setTeam === T && ['team', 'emoji'].includes(setStack[setStack.length - 1])) renderSetPage(); });
}

function emoSheet(pack) {
  if (emoSheets[pack]) return Promise.resolve(emoSheets[pack]);
  return setPost({action:'emoji_pack', pack}).then(s => { emoSheets[pack] = s; return s; });
}

// Una emoji presa dalla griglia del pack: posizione dentro l'immagine unica.
function emoCellStyle(sheet, n) {
  const cols = sheet.cols, rows = Math.max(1, Math.ceil(sheet.items.length / cols));
  const x = cols > 1 ? (n % cols) / (cols - 1) * 100 : 0, y = rows > 1 ? Math.floor(n / cols) / (rows - 1) * 100 : 0;
  return `background-image:url('${sheet.sprite}');background-size:${cols * 100}% ${rows * 100}%;background-position:${x}% ${y}%`;
}
const emoImg = (cell, size) => cell && (cell.thumb || cell.style)
  ? `<span class="emo-th" style="width:${size}px;height:${size}px;${cell.thumb ? `background-image:url('${cell.thumb}')` : cell.style}"></span>`
  : `<span class="emo-th emo-vs" style="width:${size}px;height:${size}px;font-size:${Math.round(size * .8)}px">🆚</span>`;
const emoSame = (a, b) => !!a && !!b && a.pack === b.pack && a.index === b.index;

// Valore della riga "Emoji" nella pagina della squadra.
function emoRowValue(T) {
  if (!T.emo) return '…';
  if (T.emo.error) return 'Non disponibile';
  return emoImg(T.emo.current, 28);
}

// Apre la pagina: false se i dati non ci sono ancora (li ricarica).
function emoOpen() {
  const T = setTeam, E = T.emo;
  if (!E || E.error) { emoLoadTeam(T, true); return false; }
  const cur = E.current;
  setDraft = {sel:cur, none:!cur, pack:(cur && cur.pack) || (E.auto && E.auto.pack) || (E.packs[0] || {}).pack};
  return true;
}

// Riga stile Impostazioni: emoji, nome, valore grigio e spunta se è quella scelta.
const emoRow = (cell, label, value, on, attrs) =>
  `<button type="button" class="sp-item emo-row" ${attrs}>${emoImg(cell, 30)}<span>${setEsc(label)}</span>
    <span class="sp-v">${setEsc(value)}</span><span class="emo-ck">${on ? '✓' : ''}</span></button>`;

function emoRender() {
  const page = setStack[setStack.length - 1];
  const box = $('setPage'), T = setTeam, E = T.emo, D = setDraft;
  const sel = D.none ? null : D.sel;
  const packName = pack => (E.packs.find(p => p.pack === pack) || {}).name || pack;

  if (page === 'emoji-pack') {            // tutte le emoji di un pack, in griglia
    const sheet = emoSheets[D.pack];
    let grid = '<div class="set-empty">Carico…</div>';
    if (sheet) {
      grid = '<div class="sp-list emo-grid">' + sheet.items.map((e, n) =>
        `<button type="button" class="emo-cell${sel && sel.pack === D.pack && sel.index === e.index ? ' on' : ''}" data-emo="pick" data-n="${n}" aria-label="Emoji ${e.index}">
          <span class="emo-th" style="width:38px;height:38px;${emoCellStyle(sheet, n)}"></span></button>`).join('') + '</div>';
    } else emoSheet(D.pack).then(() => { if (setDraft === D) renderSetPage(); })
      .catch(err => { if ($('setErr')) $('setErr').textContent = err.message; });
    box.innerHTML = spNav(packName(D.pack)) + `<div class="sp-body emo-page">
      ${grid}<p class="sp-note">Tocca un'emoji per sceglierla.</p><div id="setErr" class="sp-err"></div></div>`;
    return;
  }

  const cur = E.current;
  const changed = D.none ? !!cur || !E.manual : !emoSame(D.sel, cur);
  const sugg = [];
  [sel, E.auto, ...E.suggest].forEach(c => { if (c && !sugg.some(x => emoSame(x, c))) sugg.push(c); });
  const tag = c => [emoSame(c, E.auto) ? 'Automatica' : '', `n. ${c.index}`].filter(Boolean).join(' · ');
  const rows = sugg.map(c => emoRow(c, c.name, tag(c), emoSame(sel, c),
    `data-emo="sugg" data-pack="${setEsc(c.pack)}" data-index="${c.index}"`)).join('');
  const packs = E.packs.map(p => `<button type="button" class="sp-item" data-emo="pack" data-pack="${setEsc(p.pack)}">
      <span>${setEsc(p.name)}</span><span class="sp-v">${p.count || ''}</span><span class="sp-chev">›</span></button>`).join('');
  const keep = box.querySelector('.emo-page') && page === D.shownPage ? box.querySelector('.emo-page').scrollTop : 0;
  D.shownPage = page;
  box.innerHTML = spNav('Emoji', {save:true, cancel:true, saveOff:!changed}) + `<div class="sp-body emo-page">
    <div class="sp-hero">${emoImg(sel, 64)}<p>${D.none ? 'Nel testo del Matchday resta 🆚' : 'Accanto al nome nel testo del Matchday'}</p></div>
    <div class="sp-lbl">Consigliate</div>
    <div class="sp-list">${rows}${emoRow(null, 'Nessuna emoji', '', D.none, 'data-emo="none"')}</div>
    <p class="sp-note">Le più simili al logo della squadra.</p>
    <div class="sp-lbl">Tutti i pack</div>
    <div class="sp-list">${packs}</div>
    ${E.manual ? '<div class="sp-list emo-acts"><button type="button" class="sp-item sp-act" data-emo="reset">Ripristina la scelta automatica</button></div>' : ''}
    <div id="setErr" class="sp-err"></div></div>`;
  box.querySelector('.emo-page').scrollTop = keep;
}

async function emoSave(change) {
  const T = setTeam;
  setBusy = true; renderSetPage();
  try {
    const body = await setPost({action:'emoji_save', emoji:{key:T.emo.key, name:setShownName(T), ...change}});
    setBusy = false;
    haptic('success');
    if (body.remote) setToast('Salvato.'); else setToast(`Salvato solo per questa sessione: ${body.warning || 'GitHub non raggiungibile'}.`, true);
    await emoLoadTeam(T, true);
    spPop();
  } catch (ex) {
    setBusy = false; renderSetPage();
    if ($('setErr')) $('setErr').textContent = ex.message || String(ex);
    haptic('error');
  }
}
function emoOnSave() {
  const D = setDraft;
  if (D.none) emoSave({none:true});
  else if (D.sel) emoSave({pack:D.sel.pack, index:D.sel.index});
}

function initEmoji() {
  $('setPage').addEventListener('click', ev => {
    const page = setStack[setStack.length - 1];
    if (page !== 'emoji' && page !== 'emoji-pack') return;
    const btn = ev.target.closest('[data-emo]');
    if (!btn || setBusy) return;
    const act = btn.dataset.emo, D = setDraft, E = setTeam.emo;
    haptic('select');
    if (act === 'sugg') {
      const c = [D.sel, E.auto, ...E.suggest].find(x => x && x.pack === btn.dataset.pack && x.index === Number(btn.dataset.index));
      if (c) { D.sel = c; D.none = false; }
    } else if (act === 'pick') {        // scelta dalla griglia: torna alla pagina Emoji con la spunta
      const sheet = emoSheets[D.pack], n = Number(btn.dataset.n);
      const name = (E.packs.find(p => p.pack === D.pack) || {}).name || D.pack;
      D.sel = {pack:D.pack, name, index:sheet.items[n].index, style:emoCellStyle(sheet, n)}; D.none = false;
      setStack.pop();
    } else if (act === 'pack') { D.pack = btn.dataset.pack; setStack.push('emoji-pack'); }
    else if (act === 'none') { D.none = true; D.sel = null; }
    else if (act === 'reset') { emoSave({reset:true}); return; }
    renderSetPage();
  });
}
document.addEventListener('DOMContentLoaded', () => { if ($('setPage')) initEmoji(); });
