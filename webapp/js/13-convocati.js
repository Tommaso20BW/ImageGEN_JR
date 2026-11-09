/* Mini App ImageGen JR. File caricati in ordine da index.html: l'ordine conta. */
/* ---------- CONVOCATI IN NAZIONALE ----------
   Elenco incollato, una riga per giocatore: "Nome (Nazione)" (vanno bene anche "Nome - Nazione",
   "Nome, Nazione" e "Nome 🇧🇦 Nazione"; con la sola bandierina vale quella). "Under 21" / "U21"
   segnano le giovanili. Il giocatore si cerca nella rosa (serve la sua foto); la nazione la
   riconosce il servizio (data/convocati/nazioni.json), che mette i giocatori in ordine di
   nazionale. Il nome resta come è stato scritto. */
const CONV_FLAG = /([\u{1F1E6}-\u{1F1FF}]{2})/u;
const CONV_UNDER = /\b(?:under|u)\s*[-.]?\s*(\d{2})\b/i;
const flagCode = f => [...f].map(c => String.fromCharCode(c.codePointAt(0) - 0x1F1E6 + 97)).join('');
// "Italia Under 21" -> "Italia U21" (come esce sulla grafica)
// Solo bandierina: il codice ('xk') torna bandierina; il nome lo mette il servizio.
const codeFlag = c => [...c].map(ch => String.fromCodePoint(0x1F1E6 + ch.charCodeAt(0) - 97)).join('');
const convNationLabel = n => n.replace(/^([a-z]{2})(?=\s|$)/, (_m, c) => codeFlag(c))
  .replace(CONV_UNDER, 'U$1').replace(/\s+/g, ' ').trim();
let convRows = [];
// Nome e cognome: quante parole del nome scritto sono il nome (bianco); le altre il cognome (oro).
// Salvati nel repository quando la grafica parte (data/name_splits.json, arrivano col pacchetto);
// convChosen: scelte fatte in questa sessione. Più di due parole e niente salvato: si chiede.
const convChosen = {};
const nameKey = n => String(n || '').toLowerCase()
  .replace(/ı/g,'i').replace(/ł/g,'l').replace(/[đð]/g,'d').replace(/ø/g,'o').replace(/ß/g,'ss')
  .normalize('NFD').replace(/[̀-ͯ]/g, '').replace(/[^a-z0-9]+/g, ' ').trim();
function convFirst(name) {
  const n = name.split(/\s+/).filter(Boolean).length;
  if (n < 2) return 0;
  const k = nameKey(name);
  const v = convChosen[k] !== undefined ? convChosen[k] : nameSplitBook[k];
  if (Number.isInteger(v) && v >= 1 && v < n) return v;
  return n > 2 ? null : 1;          // null: da chiedere
}
// Popup: le possibili divisioni del nome (es. PAPE | MATAR SARR, PAPE MATAR | SARR).
function askSplit(name) {
  return new Promise(resolve => {
    const words = name.toUpperCase().split(/\s+/).filter(Boolean);
    const box = document.createElement('div');
    box.className = 'ask open';
    box.setAttribute('role', 'dialog');
    box.innerHTML = '<div class="ios-alert"><div class="ia-body"><h2>Nome e cognome</h2><p></p></div>' +
      '<div class="ia-btns one ia-opts"></div><div class="ia-btns one"><button type="button">Annulla</button></div></div>';
    box.querySelector('p').textContent = `Qual è il nome di ${words.join(' ')}? Il resto è il cognome (in oro).`;
    const opts = box.querySelector('.ia-opts');
    const done = value => { box.remove(); resolve(value); };
    for (let k = 1; k < words.length; k++) {
      const b = document.createElement('button');
      b.type = 'button';
      b.style.cssText = 'height:auto;min-height:44px;padding:8px 12px;border-bottom:1px solid var(--line)';
      b.innerHTML = '<span></span> <b style="color:var(--text)"></b>';
      b.children[0].textContent = words.slice(0, k).join(' ');
      b.children[1].textContent = words.slice(k).join(' ');
      b.onclick = () => { haptic('select'); done(k); };
      opts.appendChild(b);
    }
    box.querySelector('.ia-btns:last-child button').onclick = () => done(null);
    document.body.appendChild(box);
  });
}
async function changeSplit(r) {
  if (r.name.split(/\s+/).filter(Boolean).length < 2) return;
  const k = await askSplit(r.name);
  if (k === null) return;
  convChosen[nameKey(r.name)] = k;
  readConv();
}
// Prima di andare avanti: chiede i nomi con più di due parole non ancora salvati.
async function askConvNames() {
  readConv();
  for (const r of convRows) {
    if (!r.player || r.first !== null) continue;
    const k = await askSplit(r.name);
    if (k === null) { readConv(); return false; }
    convChosen[nameKey(r.name)] = k;
  }
  readConv();
  return true;
}
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
    // Bandierina: tra nome e nazione fa da separatore; da sola vale come nazione.
    let flag = '';
    const f = line.match(CONV_FLAG);
    if (f) {
      flag = flagCode(f[1]);
      const before = line.slice(0, f.index).trim(), after = line.slice(f.index + f[1].length).trim();
      line = before && after && !after.includes('(') ? `${before} (${after})` : `${before} ${after}`.trim();
      line = line.replace(new RegExp(CONV_FLAG.source, 'gu'), '').trim();
    }
    const m = line.match(/^(.+?)\s*(?:\(([^)]*)\)?|\s[-–—]\s|,)\s*(.*)$/);
    const name = (m ? m[1] : line).replace(/^[\d.\-•*\s]+/, '').trim();
    let nation = m ? (m[2] !== undefined ? m[2] : m[3]).trim() : '';
    if (flag && !nation.replace(CONV_UNDER, '').trim()) nation = `${flag} ${nation}`.trim();
    return {name, nation, first: convFirst(name), player: playersLoaded ? convPlayer(name) : null};
  });
  // In ordine di nazionale, come sulla grafica.
  convRows.sort((a, b) => norm(convNationLabel(a.nation)).localeCompare(norm(convNationLabel(b.nation))));
  const box = $('convParsed');
  box.innerHTML = '';
  convRows.forEach(r => {
    const row = document.createElement('div');
    const ok = r.player && r.nation;
    row.className = 'parsed-row' + (ok ? '' : ' new');
    row.innerHTML = '<span class="pr-num"></span><span class="pr-name"></span><span class="pr-role"></span>';
    row.children[0].textContent = String(convRows.indexOf(r) + 1);
    // Nome normale, cognome in grassetto; tocco sulla riga: cambia nome/cognome.
    const words = r.name.toUpperCase().split(/\s+/).filter(Boolean);
    const k = r.first === null ? 0 : r.first;
    row.children[1].innerHTML = '<span></span> <b></b>';
    row.children[1].children[0].textContent = words.slice(0, k).join(' ');
    row.children[1].children[1].textContent = words.slice(k).join(' ');
    row.children[1].style.fontWeight = '500';
    row.children[2].textContent = !r.player ? (playersLoaded ? 'non in rosa' : '…') : !r.nation ? 'manca la nazione'
      : r.first === null ? 'nome? tocca' : convNationLabel(r.nation);
    if (words.length > 1) { row.style.cursor = 'pointer'; row.onclick = () => changeSplit(r); }
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
    players:convRows.map(r => ({name:r.player.name, shown:r.name, nation:r.nation,
      // parole del nome: solo se scelte a mano o se il nome ha più di due parole
      ...(r.first && (r.name.split(/\s+/).filter(Boolean).length > 2 || convChosen[nameKey(r.name)] !== undefined)
        ? {first:r.first} : {})}))}};
}

$('convText').addEventListener('input', () => { clearError(); readConv(); });
$('convFoot').value = convFooterDefault();
