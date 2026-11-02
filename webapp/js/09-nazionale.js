/* Mini App ImageGen JR. File caricati in ordine da index.html: l'ordine conta. */
/* ---------- Italia (Nazionale) e tipo di gol ----------
   Voce "Italia" in fondo alla Home: le grafiche LiveScore della Nazionale (senza foto, tema
   azzurro Home o bianco Away, nomi delle squadre al posto degli stemmi). Prima si sceglie la
   grafica, poi competizione, campo, avversaria (scritta a mano) e maglia.
   Gol (Juventus e Italia): Gol / Rigore / Autogol / Senza foto (Senza foto solo Juventus). */
let nat = false;          // true = voce "Italia"
let natSel = '';          // grafica scelta: kick, half, second, end_of_90, full, goal, saved, stats
let goalType = 'goal';    // goal | penalty | own | nophoto

const NAT_KINDS = [['kick','Kick off'],['half','Half time'],['second','2nd half'],['end_of_90','End of 90’'],
  ['full','Full time'],['goal','Gol'],['saved','Parata'],['stats','Statistiche']];
const NAT_COMPETITIONS = [['fifa.friendly','Amichevole'],['uefa.nations','Nations League'],
  ['fifa.worldq.uefa','Qualificazioni Mondiali'],['fifa.world','Mondiali'],
  ['uefa.euroq','Qualificazioni Europei'],['uefa.euro','Europei']];
const NAT_KITS = [['ita_home','Home · azzurra'],['ita_away','Away · bianca']];
// Gol: con foto (Juventus). Rigore: con foto e “(RIGORE)”. Autogol: giocatore avversario, senza foto.
// Senza foto: marcatore scritto a mano, card senza foto. L'Italia è sempre senza foto.
const GOAL_TYPES = [['goal','Gol'],['penalty','Rigore'],['own','Autogol'],['nophoto','Senza foto']];
const goalTypeOptions = () => nat ? GOAL_TYPES.filter(([v]) => v !== 'nophoto') : GOAL_TYPES;
const NAT_PHASES = new Set(['kick','half','second','end_of_90','full']);

const natOppName = () => $('natOpp').value.replace(/\s+/g,' ').trim();
const natPlayerName = () => $('natPlayer').value.replace(/\s+/g,' ').trim();
// Il nome si scrive a mano: Italia (Gol/Parata) o autogol (anche della Juventus).
const needsTypedName = () => (nat && (kind === 'saved' || kind === 'goal')) || (kind === 'goal' && (goalType === 'own' || goalType === 'nophoto'));

function natPickKind(v) {              // grafica dell'Italia scelta: tipo e fase come le altre grafiche
  natSel = v;
  kind = NAT_PHASES.has(v) ? 'match' : v;
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
  return phase === 'kick' ? base : [...base,'score'];
}

// Gol della Juventus: dopo la maglia si sceglie il tipo; autogol e senza marcatore senza foto (niente posa).
function juveGoalSteps(friendly) {
  if (kind !== 'goal') return friendly ? ['player','minute'] : ['player','minute','pose'];
  if (goalType === 'own' || goalType === 'nophoto') return ['goaltype','natplayer','minute'];
  return ['goaltype','player','minute',...(friendly ? [] : ['pose'])];
}

function natStepValue(step) {
  if (step === 'natkind') return labelOf(NAT_KINDS,natSel);
  if (step === 'natopp') return natOppName();
  if (step === 'natplayer') return natPlayerName();
  if (step === 'goaltype') return labelOf(goalTypeOptions(),goalType);
  return null;
}

function natValidate(step) {
  if (step === 'natkind' && !natSel) { showError('Scegli la grafica.'); return false; }
  if (step === 'goaltype' && !goalType) { showError('Scegli il tipo di gol.'); return false; }
  if (step === 'natopp' && !natOppName()) { showError('Scrivi la squadra avversaria.'); return false; }
  if (step === 'natplayer' && !natPlayerName()) {
    showError(kind === 'saved' ? 'Scrivi il nome del portiere.' : goalType === 'own' ? "Scrivi chi ha fatto l'autogol." : 'Scrivi il nome del marcatore.');
    return false;
  }
  return true;
}

function natRender() {
  renderOptions('natKindOpts',NAT_KINDS,natSel,natPickKind);
  if (nat && goalType === 'nophoto') goalType = 'goal';
  renderOptions('goalTypeOpts',goalTypeOptions(),goalType,v => { goalType = v; buildFlow(); });
  $('natPlayerTitle').textContent = kind === 'saved' ? 'Portiere' : goalType === 'own' ? 'Chi ha fatto autogol' : 'Marcatore';
  $('natPlayerLead').textContent = kind === 'saved' ? 'Scrivi nome e cognome del portiere.'
    : goalType === 'own' ? 'Scrivi il giocatore avversario: nella grafica compare con “(AUTOGOL)”.'
    : goalType === 'penalty' ? 'Scrivi nome e cognome del giocatore: nella grafica compare con “(RIGORE)”.'
    : 'Scrivi nome e cognome del giocatore.';
}

function natReset() {
  natSel = ''; goalType = 'goal';
  $('natOpp').value = ''; $('natPlayer').value = '';
}

// Dati della richiesta (buildPayload): Italia o gol senza giocatore della rosa.
function natPayload() {
  const data = {team:'italy', kind:realKind(), competition, kit, side, opponent:{name:natOppName()}};
  if (!data.opponent.name) throw new Error('Scrivi la squadra avversaria.');
  if (kind === 'goal' || kind === 'saved') {
    if (kind === 'goal') data.goal_type = goalType;
    data.player = natPlayerName();
    data.minute = $('minute').value.trim();
    data.score = scorePair('evHomeScore','evAwayScore',true);
  }
  return data;
}

function natInit() {
  ['natOpp','natPlayer'].forEach(id => $(id).addEventListener('input',() => renderSteps()));
  ['natOpp','natPlayer'].forEach(id => $(id).addEventListener('keydown',e => { if (e.key === 'Enter') { e.preventDefault(); nextField(true); } }));
}
