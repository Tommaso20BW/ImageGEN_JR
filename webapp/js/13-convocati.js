/* Mini App ImageGen JR. File caricati in ordine da index.html: l'ordine conta. */
/* ---------- CONVOCATI IN NAZIONALE ----------
   Elenco incollato, una riga per giocatore: "Nome (Nazione)" (vanno bene anche "Nome - Nazione"
   e "Nome, Nazione"). Il giocatore si cerca nella rosa (serve la sua foto); la nazione la
   riconosce il servizio (data/convocati/nazioni.json). Il nome resta come è stato scritto. */
let convRows = [];
const CONV_MONTHS = ['gennaio','febbraio','marzo','aprile','maggio','giugno','luglio','agosto','settembre','ottobre','novembre','dicembre'];
const convFooterDefault = () => { const d = new Date(); return `Pausa nazionali · ${CONV_MONTHS[d.getMonth()]} ${d.getFullYear()}`; };

// Giocatore della rosa per un nome scritto a mano ("Nico Gonzalez" -> Nicolas Gonzalez).
function convPlayer(text) {
  const hit = findPlayer(text);
  if (hit) return hit;
  const words = norm(text).split(' ').filter(w => w.length > 2);
  const found = players.filter(p => {
    const keys = [p.name, ...(p.aliases || [])].map(norm).join(' ');
    return words.length && words.every(w => keys.split(' ').some(k => k.startsWith(w) || w.startsWith(k)));
  });
  if (found.length === 1) return found[0];
  const last = words[words.length - 1];
  const bySurname = last ? players.filter(p => norm(p.name).split(' ').includes(last)) : [];
  return bySurname.length === 1 ? bySurname[0] : null;
}

function readConv() {
  const lines = $('convText').value.split('\n').map(l => l.replace(/\s+/g, ' ').trim()).filter(Boolean);
  convRows = lines.map(line => {
    const m = line.match(/^(.+?)\s*(?:\(([^)]*)\)?|\s[-–—]\s|,)\s*(.*)$/);
    const name = (m ? m[1] : line).replace(/^[\d.\-•*\s]+/, '').trim();
    const nation = m ? (m[2] !== undefined ? m[2] : m[3]).trim() : '';
    return {name, nation, player: playersLoaded ? convPlayer(name) : null};
  });
  const box = $('convParsed');
  box.innerHTML = '';
  convRows.forEach(r => {
    const row = document.createElement('div');
    const ok = r.player && r.nation;
    row.className = 'parsed-row' + (ok ? '' : ' new');
    row.innerHTML = '<span class="pr-num"></span><span class="pr-name"></span><span class="pr-role"></span>';
    row.children[0].textContent = String(convRows.indexOf(r) + 1);
    row.children[1].textContent = r.name.toUpperCase();
    row.children[2].textContent = !r.player ? (playersLoaded ? 'non in rosa' : '…') : r.nation ? r.nation : 'manca la nazione';
    box.appendChild(row);
  });
  $('convSummary').textContent = convRows.length ? `${convRows.length} giocator${convRows.length === 1 ? 'e' : 'i'}` : '';
  renderSteps();
}

function convValidate() {
  readConv();
  if (!convRows.length) { showError('Incolla i convocati: una riga per giocatore, es. Douglas Luiz (Brasile).'); return false; }
  if (convRows.length > 20) { showError('Al massimo 20 giocatori.'); return false; }
  const noPlayer = convRows.find(r => !r.player);
  if (noPlayer) { showError(`${noPlayer.name} non è nella rosa: serve la sua foto.`); return false; }
  const noNation = convRows.find(r => !r.nation);
  if (noNation) { showError(`Scrivi la nazione di ${noNation.name}, es. ${noNation.name} (Italia).`); return false; }
  if (new Set(convRows.map(r => r.player.name)).size !== convRows.length) { showError('Lo stesso giocatore compare due volte.'); return false; }
  return true;
}

function convPayload() {
  if (!convValidate()) throw new Error('Controlla l’elenco dei convocati.');
  return {v:1, action:'render', session, data:{kind:'conv', footer:$('convFoot').value.trim(),
    players:convRows.map(r => ({name:r.player.name, shown:r.name, nation:r.nation}))}};
}

$('convText').addEventListener('input', () => { clearError(); readConv(); });
$('convFoot').value = convFooterDefault();
