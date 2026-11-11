/* ---------- Impostazioni › Emoji squadre ----------
   Emoji della squadra avversaria nel testo del Matchday. Pagina 'emo': squadre divise per pack
   (JR Pack, Italia, Inghilterra…); pagina 'emo-pick': scegli l'emoji sfogliando i pack.
   Le scelte fatte qui vanno in team_overrides/emoji.json (repo degli asset) e vincono su quelle
   automatiche, che il controllo dei pack di inizio stagione tiene aggiornate. */
let emoData = null, emoJob = null;
const emoSheets = {};          // pack -> griglia {sprite, cell, cols, items}

function emoLoad(force = false) {
  if ((emoData && !force) || emoJob) return emoJob;
  emoJob = setPost({action:'emoji_list'})
    .then(body => { emoData = body; })
    .catch(err => setToast(err.message || 'Emoji non caricate.', true))
    .finally(() => { emoJob = null; if (String(setStack[setStack.length - 1] || '').startsWith('emo')) renderSetPage(); });
  return emoJob;
}

function emoSheet(pack) {
  if (emoSheets[pack]) return Promise.resolve(emoSheets[pack]);
  return setPost({action:'emoji_pack', pack}).then(s => { emoSheets[pack] = s; return s; });
}

const emoPackName = pack => ((emoData && emoData.packs.find(p => p.pack === pack)) || {}).name || pack;
const emoTeamName = t => t.display_name || displayTeamName(t.name);
const emoThumb = (uri, size = 30) => uri
  ? `<span class="emo-th" style="width:${size}px;height:${size}px;background-image:url('${uri}')"></span>`
  : `<span class="emo-th emo-vs" style="width:${size}px;height:${size}px;font-size:${Math.round(size * .6)}px">🆚</span>`;

function openEmoji() {
  haptic('select');
  setTeam = {emoQ:''};
  setDraft = null;
  setStack = ['emo'];
  emoLoad();
  renderSetPage();
}

function emoOpenTeam(key) {
  const t = emoData.teams.find(x => x.key === key);
  if (!t) return;
  haptic('select');
  setDraft = {team:t, pack:t.pack || 'AroundJuventus', sel:t.pack ? {pack:t.pack, index:t.index} : null, none:!t.pack && t.manual};
  setStack.push('emo-pick');
  renderSetPage();
}

function emoRender(page) {
  const box = $('setPage');
  if (page === 'emo') {
    const T = setTeam;
    let html = spNav('Emoji squadre') + `<div class="sp-body">
      <label class="sp-search">${spIco('search', 20)}<input id="emoQ" type="text" placeholder="Cerca squadra" autocomplete="off" autocapitalize="words" spellcheck="false" value="${setEsc(T.emoQ)}"></label>
      <p class="sp-note">Emoji della squadra avversaria nel testo del Matchday. Tocca una squadra per cambiarla.</p>`;
    if (!emoData) html += `<div class="set-empty">${emoJob ? 'Carico le emoji…' : 'Emoji non disponibili.'}</div>`;
    else {
      const q = norm(T.emoQ);
      const list = emoData.teams.filter(t => !q || [t.name, emoTeamName(t)].some(v => norm(v).includes(q)));
      const groups = [...emoData.packs.map(p => p.pack), null];
      groups.forEach(pack => {
        const rows = list.filter(t => (t.pack || null) === pack).sort((a, b) => emoTeamName(a).localeCompare(emoTeamName(b), 'it'));
        if (!rows.length) return;
        html += `<div class="sp-lbl">${setEsc(pack ? emoPackName(pack) : 'Senza emoji (🆚)')}</div><div class="sp-list">` + rows.map(t =>
          `<button type="button" class="sp-item" data-emo="team" data-key="${setEsc(t.key)}">${emoThumb(t.thumb)}<span>${setEsc(emoTeamName(t))}</span>
            <span class="sp-v">${t.manual ? 'Scelta tua' : (pack ? `n. ${t.index}` : '')}</span><span class="sp-chev">›</span></button>`).join('') + '</div>';
      });
      if (!list.length) html += '<div class="set-empty">Nessuna squadra trovata.</div>';
    }
    box.innerHTML = html + '<div id="setErr" class="sp-err"></div></div>';
    const q = $('emoQ');
    q.addEventListener('input', () => { T.emoQ = q.value; const pos = q.selectionStart; renderSetPage(); const n = $('emoQ'); n.focus(); n.setSelectionRange(pos, pos); });
    return;
  }
  // emo-pick: una squadra, griglia del pack scelto
  const D = setDraft, t = D.team;
  const changed = D.none ? !(t.manual && !t.pack) : !!D.sel && !(D.sel.pack === t.pack && D.sel.index === t.index);
  const sheet = emoSheets[D.pack];
  const chips = emoData.packs.map(p => `<button type="button" class="emo-chip${p.pack === D.pack ? ' on' : ''}" data-emo="pack" data-pack="${setEsc(p.pack)}">${setEsc(p.name)}</button>`).join('');
  let grid = `<div class="set-empty">Carico ${setEsc(emoPackName(D.pack))}…</div>`;
  if (sheet) {
    const cols = sheet.cols, cell = sheet.cell, rows = Math.ceil(sheet.items.length / cols);
    grid = '<div class="emo-grid">' + sheet.items.map((e, n) => {
      const on = !D.none && D.sel && D.sel.pack === D.pack && D.sel.index === e.index;
      return `<button type="button" class="emo-cell${on ? ' on' : ''}" data-emo="pick" data-index="${e.index}" aria-label="Emoji ${e.index}">
        <i style="background-image:url('${sheet.sprite}');background-size:${cols * 100}% ${rows * 100}%;background-position:${n % cols ? (n % cols) / (cols - 1) * 100 : 0}% ${rows > 1 ? Math.floor(n / cols) / (rows - 1) * 100 : 0}%"></i></button>`;
    }).join('') + '</div>';
  } else emoSheet(D.pack).then(() => { if (setDraft === D) renderSetPage(); }).catch(err => { if ($('setErr')) $('setErr').textContent = err.message; });
  const selName = D.none ? 'Nessuna (🆚)' : D.sel ? `${emoPackName(D.sel.pack)} · n. ${D.sel.index}` : 'Nessuna (🆚)';
  box.innerHTML = spNav(emoTeamName(t), {save:true, cancel:true, saveOff:!changed}) + `<div class="sp-body emo-pick">
    <div class="emo-head">${emoThumb(t.thumb, 44)}<div><b>${setEsc(selName)}</b><small>${t.manual ? 'Scelta tua' : 'Scelta automatica'}${t.auto ? ` · automatica: ${setEsc(emoPackName(t.auto.pack))} n. ${t.auto.index}` : ''}</small></div></div>
    <div class="emo-chips">${chips}</div>
    ${grid}
    <div class="sp-list emo-acts">
      ${t.manual ? '<button type="button" class="sp-item sp-act" data-emo="reset">Torna alla scelta automatica</button>' : ''}
      <button type="button" class="sp-item sp-act" data-emo="none">Nessuna emoji (🆚)</button>
    </div>
    <div id="setErr" class="sp-err"></div></div>`;
  const on = box.querySelector('.emo-chip.on');
  if (on) on.scrollIntoView({block:'nearest', inline:'center'});
}

async function emoSave(change) {
  const t = setDraft.team;
  setBusy = true; renderSetPage();
  try {
    const body = await setPost({action:'emoji_save', emoji:{key:t.key, name:emoTeamName(t), ...change}});
    setBusy = false;
    haptic('success');
    if (body.remote) setToast('Salvato.'); else setToast(`Salvato solo per questa sessione: ${body.warning || 'GitHub non raggiungibile'}.`, true);
    await emoLoad(true);
    spPop();
  } catch (ex) {
    setBusy = false; renderSetPage();
    if ($('setErr')) $('setErr').textContent = ex.message || String(ex);
    haptic('error');
  }
}

function initEmoji() {
  $('setPage').addEventListener('click', ev => {
    const btn = ev.target.closest('[data-emo]');
    const page = setStack[setStack.length - 1];
    if (page === 'emo-pick' && ev.target.closest('[data-sp="save"]') && !setBusy) {
      const D = setDraft;
      emoSave(D.none ? {none:true} : {pack:D.sel.pack, index:D.sel.index});
      return;
    }
    if (!btn) return;
    const act = btn.dataset.emo, D = setDraft;
    if (act === 'team') emoOpenTeam(btn.dataset.key);
    else if (act === 'pack') { D.pack = btn.dataset.pack; haptic('select'); renderSetPage(); }
    else if (act === 'pick') { D.sel = {pack:D.pack, index:Number(btn.dataset.index)}; D.none = false; haptic('select'); renderSetPage(); }
    else if (act === 'none') { D.none = true; D.sel = null; haptic('select'); renderSetPage(); }
    else if (act === 'reset') emoSave({reset:true});
  });
}
document.addEventListener('DOMContentLoaded', () => { if ($('setPage')) initEmoji(); });
