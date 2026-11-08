/* Mini App ImageGen JR. File caricati in ordine da index.html: l'ordine conta. */
/* ---------- Italia (Nazionale) e tipo di gol ----------
   Voce "Italia" nella sezione "Nazionale" in fondo alla Home: le grafiche LiveScore della Nazionale (senza foto, tema
   azzurro Home o bianco Away, nomi delle squadre al posto degli stemmi). Prima si sceglie la
   grafica, poi competizione, campo, avversaria (scritta a mano) e maglia.
   Gol (Juventus e Italia): Gol / Rigore / Autogol / Senza foto (Senza foto solo Juventus, non nelle amichevoli). */
let nat = false;          // true = voce "Italia"
let natSel = '';          // grafica scelta: kick, half, second, end_of_90, full, goal, saved, stats
let goalType = 'goal';    // goal | penalty | own | nophoto
// Starting XI dell'Italia: modulo e 11 cognomi (portiere, poi le linee dalla difesa all'attacco).
let natModule = '';
let natXi = Array(11).fill('');
let natXiBuilt = '';
// Moduli della grafica (stessi di livescore/graphics/lineup.py FORMATIONS).
const NAT_MODULES = ['4-3-3','4-2-3-1','4-4-2','4-1-4-1','4-5-1','4-4-1-1','3-4-2-1','3-4-3','3-4-1-2',
  '3-5-2','3-1-4-2','5-4-1','5-3-2'];

const NAT_KINDS = [['natxi','Starting XI'],['kick','Kick Off'],['half','Half Time'],['second','2nd Half'],['end_of_90','End Of 90’'],
  ['full','Full Time'],['goal','Gol'],['saved','Parata'],['stats','Statistiche']];
const NAT_COMPETITIONS = [['fifa.friendly','Amichevole'],['uefa.nations','Nations League'],
  ['fifa.worldq.uefa','Qualificazioni Mondiali'],['fifa.world','Mondiali'],
  ['uefa.euroq','Qualificazioni Europei'],['uefa.euro','Europei']];
const NAT_KITS = [['ita_home','Home · azzurra'],['ita_away','Away · bianca']];
// Gol: con foto (Juventus). Rigore: con foto e “(RIGORE)”. Autogol: giocatore avversario, senza foto.
// Senza foto: marcatore scritto a mano, card senza foto. L'Italia è sempre senza foto.
const GOAL_TYPES = [['goal','Gol'],['penalty','Rigore'],['own','Autogol'],['nophoto','Senza foto']];
// Italia e amichevoli: il gol è già sempre senza foto, "Senza foto" non serve.
const noPhotoAlways = () => nat || isFriendly();
const goalTypeOptions = () => noPhotoAlways() ? GOAL_TYPES.filter(([v]) => v !== 'nophoto') : GOAL_TYPES;
const NAT_PHASES = new Set(['kick','half','second','end_of_90','full']);

const natOppName = () => $('natOpp').value.replace(/\s+/g,' ').trim();
const natPlayerName = () => $('natPlayer').value.replace(/\s+/g,' ').trim();
// Il nome si scrive a mano: Italia (Gol/Parata) o autogol (anche della Juventus).
const needsTypedName = () => (nat && (kind === 'saved' || kind === 'goal')) || (kind === 'goal' && (goalType === 'own' || goalType === 'nophoto'));

function natPickKind(v) {              // grafica dell'Italia scelta: tipo e fase come le altre grafiche
  natSel = v;
  kind = NAT_PHASES.has(v) ? 'match' : v;   // 'natxi': Starting XI senza foto (non quella Juventus)
  phase = NAT_PHASES.has(v) ? v : '';
  if (kind !== 'goal') goalType = 'goal';
  buildFlow();
}

// Passaggi della voce "Italia" (buildFlow).
function natFlow() {
  const base = ['natkind','competition','side','natopp','kit'];
  if (!natSel) return base;            // grafica non ancora scelta: i passaggi comuni
  if (kind === 'goal') return [...base,'goaltype','natplayer','minute'];
  if (kind === 'saved') return [...base,'natplayer','minute'];
  if (kind === 'stats') return [...base,'moment','stats'];
  if (kind === 'natxi') return [...base,'natxi'];
  return phase === 'kick' ? base : [...base,'score'];
}

// Gol della Juventus: dopo la maglia si sceglie il tipo; autogol e senza marcatore senza foto (niente posa).
function juveGoalSteps(friendly) {
  if (friendly && goalType === 'nophoto') goalType = 'goal';
  if (kind !== 'goal') return friendly ? ['player','minute'] : ['player','minute','pose'];
  if (goalType === 'own' || goalType === 'nophoto') return ['goaltype','natplayer','minute'];
  return ['goaltype','player','minute',...(friendly ? [] : ['pose'])];
}

function natStepValue(step) {
  if (step === 'natkind') return labelOf(NAT_KINDS,natSel);
  if (step === 'natopp') return natOppName();
  if (step === 'natplayer') return natPlayerName();
  if (step === 'goaltype') return labelOf(goalTypeOptions(),goalType);
  if (step === 'natxi') return natModule ? `${natModule} · ${natXi.filter(n => n.trim()).length}/11` : '';
  return null;
}

function natValidate(step) {
  if (step === 'natkind' && !natSel) { showError('Scegli la grafica.'); return false; }
  if (step === 'goaltype' && !goalType) { showError('Scegli il tipo di gol.'); return false; }
  if (step === 'natxi' && !natModule) { showError('Scegli il modulo.'); return false; }
  if (step === 'natxi' && natXi.some(n => !n.trim())) { showError('Scrivi tutti gli 11 titolari.'); return false; }
  if (step === 'natopp' && !natOppName()) { showError('Scrivi la squadra avversaria.'); return false; }
  if (step === 'natplayer' && !natPlayerName()) {
    showError(kind === 'saved' ? 'Scrivi il nome del portiere.' : goalType === 'own' ? "Scrivi chi ha fatto l'autogol." : 'Scrivi il nome del marcatore.');
    return false;
  }
  return true;
}

function natRender() {
  // Due gruppi come nella Home: eventi della partita (fasi) e in partita (gol, parata, statistiche).
  renderOptions('natPreOpts',NAT_KINDS.filter(([v]) => v === 'natxi'),natSel,natPickKind);
  renderOptions('natKindOpts',NAT_KINDS.filter(([v]) => NAT_PHASES.has(v)),natSel,natPickKind);
  renderOptions('natPlayOpts',NAT_KINDS.filter(([v]) => !NAT_PHASES.has(v) && v !== 'natxi'),natSel,natPickKind);
  if ($('natModule').value !== natModule) $('natModule').value = natModule;
  natXiRender();
  if (noPhotoAlways() && goalType === 'nophoto') goalType = 'goal';
  renderOptions('goalTypeOpts',goalTypeOptions(),goalType,v => { goalType = v; buildFlow(); });
  $('natPlayerTitle').textContent = kind === 'saved' ? 'Portiere' : goalType === 'own' ? 'Chi ha fatto autogol' : 'Marcatore';
  $('natPlayerLead').textContent = kind === 'saved' ? 'Scrivi nome e cognome del portiere.'
    : goalType === 'own' ? 'Scrivi il giocatore avversario: nella grafica compare con “(AUTOGOL)”.'
    : goalType === 'penalty' ? 'Scrivi nome e cognome del giocatore: nella grafica compare con “(RIGORE)”.'
    : 'Scrivi nome e cognome del giocatore.';
}

function natReset() {
  natSel = ''; goalType = 'goal';
  natModule = ''; natXi = Array(11).fill(''); natXiBuilt = ''; $('natXiRows').innerHTML = '';
  $('natOpp').value = ''; $('natPlayer').value = '';
}

// Dati della richiesta (buildPayload): Italia o gol senza giocatore della rosa.
function natPayload() {
  const data = {team:'italy', kind:realKind(), competition, kit, side, opponent:{name:natOppName()}};
  if (!data.opponent.name) throw new Error('Scrivi la squadra avversaria.');
  if (kind === 'natxi') {
    if (!natModule) throw new Error('Scegli il modulo.');
    if (natXi.some(n => !n.trim())) throw new Error('Scrivi tutti gli 11 titolari.');
    data.kind = 'xi';
    data.formation = natModule;
    data.players = natXi.map(n => n.replace(/\s+/g,' ').trim());
  }
  if (kind === 'goal' || kind === 'saved') {
    if (kind === 'goal') data.goal_type = goalType;
    data.player = natPlayerName();
    data.minute = $('minute').value.trim();
    data.score = scorePair('evHomeScore','evAwayScore',true);
  }
  return data;
}

// Campi dei titolari: rifatti solo quando cambia il modulo (i nomi già scritti restano al loro posto).
function natXiRender() {
  const box = $('natXiRows');
  if (!natModule || natXiBuilt === natModule) return;
  natXiBuilt = natModule;
  const rows = natModule.split('-').map(Number);
  const middle = rows.length === 3 ? ['Centrocampo'] : rows.length === 4 ? ['Centrocampo','Trequarti'] : ['Centrocampo'];
  const names = ['Difesa',...middle,'Attacco'];
  const lines = [['Portiere',1],...rows.map((n,i) => [names[Math.min(i,names.length - 1)] + (i > 0 && i < rows.length - 1 && rows.length > 4 ? ` ${i}` : ''),n])];
  box.innerHTML = '';
  let idx = 0;
  lines.forEach(([label,count]) => {
    const head = document.createElement('div');
    head.className = 'field-label gap';
    head.textContent = count > 1 ? `${label} · da sinistra a destra` : label;
    const list = document.createElement('div');
    list.className = 'ios-list';
    for (let k = 0; k < count; k++, idx++) {
      const i = idx;
      const row = document.createElement('label');
      row.className = 'ios-row';
      row.innerHTML = '<span></span><input class="ios-in" maxlength="30" autocomplete="off" autocapitalize="words" spellcheck="false" enterkeyhint="next" placeholder="Cognome">';
      row.querySelector('span').textContent = count > 1 ? String(k + 1) : 'GK';
      const input = row.querySelector('input');
      input.value = natXi[i];
      input.addEventListener('input',() => { natXi[i] = input.value; renderSteps(); });
      input.addEventListener('keydown',e => {
        if (e.key !== 'Enter') return;
        e.preventDefault();
        const all = [...box.querySelectorAll('input')];
        const next = all[all.indexOf(input) + 1];
        if (next) next.focus(); else nextField(true);
      });
      list.appendChild(row);
    }
    box.append(head,list);
  });
}

function natInit() {
  const sel = $('natModule');
  NAT_MODULES.forEach(m => sel.add(new Option(m,m)));
  sel.addEventListener('change',() => { natModule = sel.value; natXiRender(); renderSteps(); });
  ['natOpp','natPlayer'].forEach(id => $(id).addEventListener('input',() => renderSteps()));
  ['natOpp','natPlayer'].forEach(id => $(id).addEventListener('keydown',e => { if (e.key === 'Enter') { e.preventDefault(); nextField(true); } }));
}
