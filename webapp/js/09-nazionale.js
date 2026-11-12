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
// Si incolla come la Probabile XI dei club: il modulo si trova dal testo (o si sceglie dal pannello).
let natModule = '';
let natModuleManual = false;
let natXi = Array(11).fill('');
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

// Cognomi uguali senza iniziali diverse che li distinguano ("Esposito" e "P. Esposito",
// oppure due "Esposito"): si chiede l'iniziale. Restituisce i cognomi (minuscoli).
function natTwins() {
  const names = natXi.map(n => n.trim().toLowerCase()).filter(Boolean);
  const bare = n => n.replace(/^\p{L}\.\s+/u,'');
  return [...new Set(names.filter((n,i) => names.some((m,j) => j !== i && bare(m) === bare(n)
    && (m === n || m === bare(m) || n === bare(n)))).map(bare))];
}

function natTwinsError() {
  const twin = natTwins()[0];
  if (!twin) return '';
  const name = cleanName(twin).toUpperCase();
  return `Ci sono due ${name}: scrivi anche l'iniziale del nome (es. S. ${cleanName(twin)}).`;
}

function natValidate(step) {
  if (step === 'natkind' && !natSel) { showError('Scegli la grafica.'); return false; }
  if (step === 'goaltype' && !goalType) { showError('Scegli il tipo di gol.'); return false; }
  if (step === 'natxi' && !natModule) { showError('Scegli il modulo.'); return false; }
  if (step === 'natxi' && natXi.some(n => !n.trim())) { showError('Scrivi tutti gli 11 titolari.'); return false; }
  if (step === 'natxi' && natTwinsError()) { showError(natTwinsError()); return false; }
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
  natModuleButton();
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
  natModule = ''; natModuleManual = false; natXi = Array(11).fill('');
  $('natXiText').value = ''; natReadXi(false);
  $('natOpp').value = ''; $('natPlayer').value = '';
}

// Dati della richiesta (buildPayload): Italia o gol senza giocatore della rosa.
function natPayload() {
  const data = {team:'italy', kind:realKind(), competition, kit, side, opponent:{name:natOppName()}};
  if (!data.opponent.name) throw new Error('Scrivi la squadra avversaria.');
  if (kind === 'natxi') {
    if (!natModule) throw new Error('Scegli il modulo.');
    if (natXi.some(n => !n.trim())) throw new Error('Scrivi tutti gli 11 titolari.');
    if (natTwinsError()) throw new Error(natTwinsError());
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

// Reparto di ogni posto (portiere, poi le linee del modulo dalla difesa all'attacco).
function natRoles(module) {
  if (!module) return [];
  const rows = module.split('-').map(Number);
  const middle = rows.length === 4 ? ['CEN','TRQ'] : Array(Math.max(0, rows.length - 2)).fill('CEN');
  const names = ['DIF',...middle,'ATT'];
  return ['POR',...rows.flatMap((n,i) => Array(n).fill(names[i]))];
}

// Testo incollato -> modulo e 11 cognomi (portiere, poi ogni linea da sinistra a destra).
function natReadXi(render = true) {
  const {module, groups} = parseFormation($('natXiText').value);
  const flat = groups.flat().slice(0,11);
  if (!natModuleManual) {
    const fromLines = groups.length > 2 ? groups.slice(1).map(g => g.length).join('-') : '';
    natModule = NAT_MODULES.includes(module) ? module : NAT_MODULES.includes(fromLines) ? fromLines : natModule;
  }
  // I giornali scrivono ogni reparto da destra a sinistra: come nella Probabile XI, si gira.
  const sizes = natModule ? [1, ...natModule.split('-').map(Number)] : [];
  let ordered = flat;
  if (sizes.length > 1) {
    ordered = [];
    let at = 0;
    sizes.forEach(n => { ordered.push(...flat.slice(at, at + n).reverse()); at += n; });
    ordered.push(...flat.slice(at));
  }
  // Due cognomi uguali: si tiene l'iniziale scritta (S. Esposito, P. Esposito); se manca si chiede.
  const seen = {};
  ordered.slice(0,11).forEach(p => { const k = cleanName(p.label).toLowerCase(); seen[k] = (seen[k] || 0) + 1; });
  natXi = Array.from({length:11},(_,i) => {
    const p = ordered[i];
    if (!p) return '';
    const name = cleanName(p.label);
    return seen[name.toLowerCase()] > 1 && p.initial ? `${p.initial}. ${name}` : name;
  });
  natModuleButton();
  const roles = natRoles(natModule);
  const box = $('natXiParsed');
  box.innerHTML = '';
  if (flat.length) natXi.forEach((name,i) => {
    const row = document.createElement('div');
    row.className = 'parsed-row' + (name ? '' : ' miss');
    row.innerHTML = '<span class="pr-num pr-role"></span><span class="pr-name"></span><span class="pr-role"></span>';
    row.children[0].textContent = roles[i] || '';
    row.children[1].textContent = name ? name.toUpperCase() : '—';
    row.children[2].textContent = !name ? 'manca' : natTwins().includes(name.toLowerCase().replace(/^\p{L}\.\s+/u,'')) ? 'iniziale?' : '';
    box.appendChild(row);
  });
  $('natXiSummary').textContent = `${flat.length} / 11 giocatori`;
  if (render) renderSteps();
}

// Pulsante e pannello del modulo: come la Probabile XI dei club, con i moduli della grafica Italia.
function natModuleButton() {
  const box = $('natModOpts');
  if (!box) return;
  box.innerHTML = `<button type="button" class="mod-btn">${natModule ? modPitch(natModule) : ''}<span><b>${natModule ? 'Modulo' : 'Scegli il modulo'}</b></span><em>${natModule}</em><i>›</i></button>`;
  box.firstChild.addEventListener('click',natOpenModSheet);
}

function natOpenModSheet() {
  haptic('select');
  const sh = $('modSh');
  sh.innerHTML = `<div class="mod-bar"></div><div class="mod-top"><b>Modulo</b></div>`
    + `<div class="mod-grid">${NAT_MODULES.map(m => `<button type="button" class="mod-tile${m === natModule ? ' on' : ''}" data-m="${m}">${modPitch(m)}<span>${m}</span></button>`).join('')}</div>`;
  sh.querySelectorAll('.mod-tile[data-m]').forEach(b => b.addEventListener('click',() => {
    natModule = b.dataset.m; natModuleManual = true; haptic('select'); closeModSheet(); natReadXi();
  }));
  $('modOv').classList.add('open');
}

function natInit() {
  $('natXiText').addEventListener('input',() => natReadXi());
  ['natOpp','natPlayer'].forEach(id => $(id).addEventListener('input',() => renderSteps()));
  ['natOpp','natPlayer'].forEach(id => $(id).addEventListener('keydown',e => { if (e.key === 'Enter') { e.preventDefault(); nextField(true); } }));
}
