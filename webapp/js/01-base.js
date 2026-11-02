/* Mini App ImageGen JR. File caricati in ordine da index.html: l'ordine conta. */
const tg = window.Telegram && window.Telegram.WebApp;
const media = window.matchMedia('(prefers-color-scheme: dark)');
const metaTheme = document.querySelector('meta[name="theme-color"]');

function applyTheme() {
  const theme = tg && ['dark','light'].includes(tg.colorScheme)
    ? tg.colorScheme
    : (media.matches ? 'dark' : 'light');
  document.documentElement.dataset.theme = theme;
  document.documentElement.style.colorScheme = theme;
  metaTheme.setAttribute('content', theme === 'dark' ? '#161618' : '#F4F3F0');
}
applyTheme();
if (media.addEventListener) media.addEventListener('change', applyTheme);

if (tg) {
  tg.ready();
  tg.expand();
  // Conferma anche quando si chiude con la X nativa di Telegram.
  try { if (typeof tg.enableClosingConfirmation === 'function') tg.enableClosingConfirmation(); } catch (_) {}
  if (tg.onEvent) tg.onEvent('themeChanged', applyTheme);
  if (['ios','android'].includes(tg.platform)) {
    document.documentElement.classList.add('tg-mobile');
    try { if (typeof tg.requestFullscreen === 'function') tg.requestFullscreen(); } catch (_) {}
  }
}

document.addEventListener('gesturestart', e => e.preventDefault(), {passive:false});
document.addEventListener('gesturechange', e => e.preventDefault(), {passive:false});
document.addEventListener('gestureend', e => e.preventDefault(), {passive:false});
let lastTouchEnd = 0;
document.addEventListener('touchend', event => {
  const now = Date.now();
  // Blocca solo il doppio tocco-zoom fuori dai pulsanti: due tocchi rapidi su
  // pulsanti diversi (es. Supplementari poi Rigori) devono funzionare entrambi.
  const onButton = event.target && event.target.closest && event.target.closest('button');
  if (!onButton && now - lastTouchEnd <= 280) event.preventDefault();
  lastTouchEnd = now;
}, {passive:false});

const PLAYERS_URLS = [
  'https://raw.githubusercontent.com/Tommaso20BW/LiveScore_JR/main/data/goal_players.json',
  'https://cdn.jsdelivr.net/gh/Tommaso20BW/LiveScore_JR@main/data/goal_players.json',
  'https://api.github.com/repos/Tommaso20BW/LiveScore_JR/contents/data/goal_players.json?ref=main'
];
const TEAMS_URLS = [
  'https://raw.githubusercontent.com/Tommaso20BW/LiveScore_JR/main/data/fclogo_manifest.json',
  'https://cdn.jsdelivr.net/gh/Tommaso20BW/LiveScore_JR@main/data/fclogo_manifest.json',
  'https://api.github.com/repos/Tommaso20BW/LiveScore_JR/contents/data/fclogo_manifest.json?ref=main'
];

const TEAM_NAMES_URLS = [
  'https://raw.githubusercontent.com/Tommaso20BW/LiveScore_JR/main/data/teams.json',
  'https://cdn.jsdelivr.net/gh/Tommaso20BW/LiveScore_JR@main/data/teams.json',
  'https://api.github.com/repos/Tommaso20BW/LiveScore_JR/contents/data/teams.json?ref=main'
];

// Richieste della home: ognuna apre il suo percorso. Gli eventi della partita (Kick off,
// Half time, ...) sono voci a sé: la fase è già scelta, quindi il passo "Quale evento?" non c'è più.
const ICONS = {
  'goal':'<circle cx="12" cy="12" r="9"/><path d="M12 8.2l3.4 2.5-1.3 4h-4.2l-1.3-4zM12 8.2V3.1M15.4 10.7l5-1.9M14.1 14.7l3.4 4.4M9.9 14.7l-3.4 4.4M8.6 10.7l-5-1.9"/>',
  'saved':'<path d="M7 14V8a1.5 1.5 0 013 0v3.5M10 11V5.5a1.5 1.5 0 013 0V11M13 11V6.5a1.5 1.5 0 013 0V12M16 12V9.5a1.5 1.5 0 013 0V15c0 4-3 6.5-7 6.5-2.6 0-4.3-1-5.6-2.6l-3-3.6a1.5 1.5 0 012.3-1.9L7 15"/>',
  'stats':'<path d="M5 20v-9M12 20V5M19 20v-6"/>',
  'kick':'<path d="M6 21V4M6 4h12l-3 4.5L18 13H6"/>',
  'half':'<path d="M9 5v14M15 5v14"/>',
  'second':'<path d="M8 5l11 7-11 7z"/>',
  'end90':'<circle cx="12" cy="13" r="8"/><path d="M12 9v4l2.5 2M9 2h6"/>',
  'full':'<path d="M5 21V4M5 4h14v10H5M12 4v10M5 9h14"/>',
  'md':'<path d="M3 7h18v3.5a1.5 1.5 0 000 3V17H3v-3.5a1.5 1.5 0 000-3zM14.5 7v2M14.5 11v2M14.5 15v2"/>',
  'pxi':'<rect x="3" y="4" width="18" height="16" rx="2"/><path d="M12 4v16"/><circle cx="12" cy="12" r="3"/>',
  'squad':'<path d="M8 6h13M8 12h13M8 18h13M3 6h.01M3 12h.01M3 18h.01"/>',
  'xi':'<path d="M8.5 3L3 6l2 4.5 2.5-1.2V21h9V9.3l2.5 1.2L21 6l-5.5-3c-.6 1.6-1.9 2.5-3.5 2.5S9.1 4.6 8.5 3z"/>',
  'cal':'<rect x="3" y="5" width="18" height="16" rx="3"/><path d="M3 10h18M8 3v4M16 3v4"/>',
  'ita':'<path fill="currentColor" stroke="none" d="M7.9 13.1 7.6 13.1 6.6 13.9 6.4 13.9 6.4 13.4 6.2 13.4 5.9 14.0 5.9 14.4 6.2 14.6 6.3 14.8 6.3 15.8 6.4 16.1 6.4 16.3 6.4 17.2 6.3 17.3 6.3 17.4 6.6 17.6 6.8 17.8 7.3 17.7 7.4 17.3 8.1 17.3 8.4 15.7 8.4 15.4 8.2 15.2 8.3 15.0 8.4 14.8 8.3 14.3 8.4 13.8 8.3 13.8 8.1 13.7ZM4.3 4.3 4.0 4.4 4.0 4.7 4.6 5.3 4.1 5.7 3.8 5.7 3.8 6.1 4.3 6.4 4.3 6.7 4.1 6.9 4.2 7.6 4.7 7.9 5.2 7.9 4.9 8.2 5.1 8.6 5.9 8.4 6.3 8.0 6.4 7.6 6.9 7.3 7.6 7.4 8.2 7.9 8.7 7.9 8.9 8.3 8.9 8.7 9.3 9.6 9.3 10.1 9.6 10.1 9.7 10.3 9.9 10.4 10.3 10.8 10.1 11.1 10.7 11.1 11.6 11.9 12.0 12.6 12.9 13.3 14.0 13.4 14.3 13.9 14.3 14.1 14.4 14.2 14.7 14.1 14.8 14.2 14.7 14.4 14.8 14.7 15.0 14.7 15.3 14.4 15.6 14.4 15.6 14.6 15.6 15.3 15.8 15.4 16.3 15.7 16.6 15.7 16.7 15.6 16.8 15.7 16.8 16.2 17.2 17.1 17.2 17.6 17.4 17.8 17.4 17.9 17.0 17.9 16.9 18.1 17.0 18.6 16.9 18.7 16.0 19.1 15.6 19.0 15.1 19.3 14.0 19.3 13.4 19.0 13.1 19.0 13.0 19.3 12.8 19.3 12.7 19.1 12.4 19.0 12.1 19.3 12.0 19.6 12.0 19.8 12.3 20.3 12.7 20.2 13.8 21.1 14.7 21.3 15.0 21.8 15.6 21.9 16.1 21.9 16.0 21.7 16.3 21.4 16.4 21.1 16.2 21.0 16.2 20.7 16.0 20.6 16.0 20.4 16.1 20.3 16.2 19.8 16.6 19.2 16.7 19.2 16.7 19.4 16.8 19.6 17.4 19.6 17.7 19.0 18.1 18.6 18.1 18.0 18.6 17.7 19.0 17.7 19.0 17.4 18.8 17.2 18.8 16.6 18.4 16.3 18.1 16.2 18.0 16.1 18.2 15.8 18.2 15.6 18.4 15.2 18.4 15.0 18.8 14.7 19.0 15.0 19.3 15.1 19.6 15.1 19.9 15.4 20.0 15.8 20.4 16.1 20.7 16.1 20.8 15.1 20.0 14.2 19.4 13.9 18.4 13.3 17.4 12.9 17.2 12.7 17.2 12.6 17.6 12.3 17.4 11.9 16.8 11.8 16.1 11.9 15.1 11.2 14.6 10.7 13.9 8.7 13.2 8.3 12.0 7.4 12.0 6.6 12.3 6.4 12.4 6.0 12.2 6.0 12.1 5.9 12.0 5.4 12.4 5.2 13.7 4.9 13.9 5.1 14.3 5.0 14.2 4.6 13.9 4.4 13.9 3.7 13.7 3.7 13.6 3.6 14.0 3.4 14.0 3.0 12.4 2.9 11.9 2.4 11.9 2.0 11.6 2.0 11.3 2.2 10.3 2.2 10.0 2.6 9.9 2.6 9.7 2.4 9.3 2.4 8.9 2.9 8.7 3.0 8.6 3.4 8.0 3.4 7.9 3.0 7.7 3.0 7.3 3.8 7.2 4.4 6.6 3.4 6.4 3.3 6.0 3.4 5.8 4.0 5.6 4.2 5.1 4.1 4.8 4.3Z"/>',
  'table':'<path d="M3 20h18M4.5 20v-6h5v6M9.5 20V8h5v12M14.5 20v-4h5v4"/>',
  'jr':'<rect x="3" y="3" width="18" height="18" rx="4"/><circle cx="9" cy="9" r="1.8"/><path d="M21 16l-5-5-9 10"/>',
  'igbn':'<path d="M13 2L4 14h7l-1 8 9-12h-7z"/>',
  'g-pre':'<rect x="6" y="4" width="12" height="17" rx="2"/><path d="M9 4h6v3H9zM9 12h6M9 16h4"/>',
  'g-events':'<circle cx="12" cy="13" r="8"/><path d="M12 9v4l2.5 2M9 2h6"/>',
  'g-play':'<circle cx="12" cy="12" r="9"/><path d="M12 8.2l3.4 2.5-1.3 4h-4.2l-1.3-4zM12 8.2V3.1M15.4 10.7l5-1.9M14.1 14.7l3.4 4.4M9.9 14.7l-3.4 4.4M8.6 10.7l-5-1.9"/>',
  'g-other':'<rect x="4" y="4" width="7" height="7" rx="1.5"/><rect x="13" y="4" width="7" height="7" rx="1.5"/><rect x="4" y="13" width="7" height="7" rx="1.5"/><rect x="13" y="13" width="7" height="7" rx="1.5"/>',
  'home':'<path d="M3 11l9-8 9 8M5 10v10h14V10"/>'
};
const svgIcon = (id, cls) => `<svg class="${cls}" viewBox="0 0 24 24" aria-hidden="true">${ICONS[id] || ''}</svg>`;
const REQUESTS = [
  {id:'goal',   kind:'goal',  icon:'goal', title:'Gol',          desc:'Giocatore, minuto e risultato'},
  {id:'saved',  kind:'saved', icon:'saved', title:'Parata',       desc:'Il portiere protagonista'},
  {id:'stats',  kind:'stats', icon:'stats', title:'Statistiche',  desc:'Possesso, tiri, xG e altri numeri'},
  {id:'kick',   kind:'match', phase:'kick',       icon:'kick', title:'Kick off',    desc:'Si parte: la partita sta per iniziare'},
  {id:'half',   kind:'match', phase:'half',       icon:'half', title:'Half time',   desc:'Risultato dell’intervallo, con foto'},
  {id:'second', kind:'match', phase:'second',     icon:'second', title:'2nd half',    desc:'Inizia il secondo tempo'},
  {id:'end90',  kind:'match', phase:'end_of_90',  icon:'end90', title:'End of 90’',  desc:'Risultato dopo i 90 minuti, con foto'},
  {id:'full',   kind:'match', phase:'full',       icon:'full', title:'Full time',   desc:'Finale, supplementari e rigori, con foto'},
  {id:'md',     kind:'md',    icon:'md', title:'Matchday',     desc:'Presentazione della partita'},
  {id:'pxi',    kind:'pxi',   icon:'pxi', title:'Probabile XI', desc:'Formazione probabile sul campo'},
  {id:'squad',  kind:'squad', icon:'squad', title:'Squad List',   desc:'Lista dei convocati'},
  {id:'xi',     kind:'xi',    icon:'xi', title:'Starting XI',  desc:'Formazione ufficiale con foto'},
  {id:'cal',    kind:'cal',   icon:'cal', title:'Calendario',   desc:'Le partite del mese'},
  {id:'table',  kind:'table', icon:'table', title:'Classifica',  desc:'Serie A e coppe europee, aggiornata da Diretta.it'},
  {id:'jr',     kind:'jr',    icon:'jr', title:'Post',         desc:'Foto con il logo JR: classica, sfocata o collage'},
  {id:'igbn',   kind:'igbn',  icon:'igbn', title:'Storia IG',    desc:'Breaking News in formato storia'},
  {id:'ita',    kind:'ita',   icon:'ita', title:'Italia',       desc:'Grafiche della Nazionale'}
];
const HOME_GROUPS = [
  {icon:'g-pre', title:'Pre-gara',              ids:['md','pxi','squad','xi']},
  {icon:'g-events', title:'Eventi della partita', ids:['kick','half','second','end90','full']},
  {icon:'g-play', title:'In partita',            ids:['goal','saved','stats']},
  {icon:'g-other', title:'Altro',                 ids:['jr','igbn','cal','table','ita']}
];
const currentRequest = () => REQUESTS.find(r => r.kind === kind && (kind !== 'match' || r.phase === phase));
const COMPETITIONS_UEFA = [
  ['uefa.champions','Champions League'],['uefa.europa','Europa League'],
  ['uefa.europa.conf','Conference League']
];
function competitionOptions() {
  if (nat) return NAT_COMPETITIONS;
  const friendly = [['club.friendly','Amichevole']];
  // Squad list: tutte le competizioni; quelle senza grafica propria usano quella delle amichevoli.
  if (kind === 'squad') return [['ita.1','Serie A'],['ita.coppa_italia','Coppa Italia'],['ita.super_cup','Supercoppa Italiana'],
    ...COMPETITIONS_UEFA,['uefa.super_cup','Supercoppa UEFA'],['fifa.cwc','Mondiale per Club'], ...friendly];
  const italy = [['ita.1','Serie A'],['ita.coppa_italia','Coppa Italia'],['ita.super_cup','Supercoppa Italiana']];
  return [...italy, ...COMPETITIONS_UEFA, ['uefa.super_cup','Supercoppa UEFA'], ['fifa.cwc','Mondiale per Club'], ...friendly];
}
// Fasi con foto caricata (sfondo + persona), prima prese dalla pagina 1 Canva.
const PHOTO_PHASES = new Set(['half','end_of_90','full']);
const PHASES = [['kick','KICK OFF'],['half','HALF TIME'],['second','2ND HALF'],['end_of_90',"END OF 90'"],['full','FULL TIME']];
const PHASE_TEXT = {
  second:{title:'Risultato all’intervallo',lead:'Inserisci i gol di entrambe le squadre a fine primo tempo.'},
  half:{title:'Risultato all’intervallo',lead:'Inserisci i gol di entrambe le squadre a fine primo tempo.'},
  end_of_90:{title:'Risultato dopo i 90’',lead:'Inserisci i gol di entrambe le squadre al 90’.'},
  full:{title:'Risultato finale',lead:'Inserisci i gol di entrambe le squadre. Spunta “Supplementari” se si sono giocati, “Rigori” se è finita ai rigori.'}
};
const SIDES = [['home','In casa'],['away','In trasferta']];
const KITS = [['home','Home'],['away','Away'],['third','Third']];
// Colori della competizione (UCL / UEL / Conference) per Matchday, Starting XI e
// Probabile XI: con una partita di quella coppa si mettono da soli, la maglia non si chiede.
// Amichevoli: tema grigio e argento, come quello di una coppa.
const UEFA_THEMES = {ucl:'Champions League', uel:'Europa League', conference:'Conference League',
  coppa:'Coppa Italia', supercoppa:'Supercoppa Italiana', usc:'Supercoppa UEFA', cwc:'Mondiale per Club', friendly:'Amichevole'};
const isFriendly = () => String(competition || '').includes('friendly');
const uefaTheme = c => {
  c = String(c || '').toLowerCase();
  if (c.includes('friendly')) return 'friendly';
  if (c === 'uefa.super_cup') return 'usc';
  if (c === 'fifa.cwc') return 'cwc';
  if (c === 'ita.super_cup') return 'supercoppa';
  if (c === 'ita.coppa_italia') return 'coppa';
  if (c.includes('conf')) return 'conference';
  if (c.includes('champions')) return 'ucl';
  return c.startsWith('uefa.europa') ? 'uel' : '';   // anche i preliminari
};
const uefaAuto = () => ['md','xi','pxi'].includes(kind) ? uefaTheme(competition) : '';
// Probabile XI a tema UEFA: il passo "Maglia" resta, ma solo per le foto dei giocatori.
let shirt = '';
// Amichevole: niente foto dei giocatori, quindi nessuna maglia da scegliere.
const needsShirt = () => kind === 'pxi' && !!UEFA_THEMES[kit] && kit !== 'friendly';
const JR_COLORS = [['black','Nero'],['white','Bianco'],['gold','Oro']];
const TABLE_COMPS = [['SA','Serie A'],['UCL','Champions League'],['UEL','Europa League'],['UECL','Conference League']];
const JR_STYLES = [['classic','Classica'],['blur','Sfocata'],['collage','Collage']];
// Formati della Classica: larghezza fissa 1080, cambia l'altezza (come graphics/photo_jr.py RATIOS).
// Il logo JR resta in alto a destra, alla stessa distanza dai bordi e della stessa misura del 3:4.
const JR_RATIOS = [['3:4','3:4'],['4:5','4:5'],['1:1','1:1'],['9:16','9:16'],['16:9','16:9'],['4:3','4:3'],['3:2','3:2']];
const ratioDims = r => { const [w,h] = String(r).split(':').map(Number); return [1080, 1080 * h / w]; };
const CAL_MONTHS = ['Gennaio','Febbraio','Marzo','Aprile','Maggio','Giugno','Luglio','Agosto','Settembre','Ottobre','Novembre','Dicembre'];
const CAL_MAX = 14;
let PXI_MODULES = [["4-2-3-1", "4-2-3-1"], ["4-3-3", "4-3-3"], ["4-4-2", "4-4-2"], ["4-3-1-2", "4-3-1-2"], ["4-2-2-2", "4-2-2-2"], ["4-3-2-1", "4-3-2-1"], ["4-1-2-1-2", "4-1-2-1-2"], ["3-4-2-1", "3-4-2-1"], ["3-4-1-2", "3-4-1-2"], ["3-5-2", "3-5-2"], ["3-5-1-1", "3-5-1-1"], ["3-4-3", "3-4-3"], ["5-4-1", "5-4-1"]];
let PXI_ROLES = {"4-2-3-1": ["POR", "TS", "DC", "DC", "TD", "CDC", "CDC", "AS", "COC", "AD", "ATT"], "4-3-3": ["POR", "TS", "DC", "DC", "TD", "CC", "CC", "CC", "AS", "ATT", "AD"], "4-4-2": ["POR", "TS", "DC", "DC", "TD", "ES", "CC", "CC", "ED", "ATT", "ATT"], "4-3-1-2": ["POR", "TS", "DC", "DC", "TD", "CC", "CC", "CC", "TRQ", "ATT", "ATT"], "4-2-2-2": ["POR", "TS", "DC", "DC", "TD", "CDC", "CDC", "AS", "AD", "ATT", "ATT"], "4-3-2-1": ["POR", "TS", "DC", "DC", "TD", "CC", "CC", "CC", "TRQ", "TRQ", "ATT"], "4-1-2-1-2": ["POR", "TS", "DC", "DC", "TD", "CDC", "CC", "CC", "COC", "ATT", "ATT"], "3-4-2-1": ["POR", "DC", "DC", "DC", "ES", "CC", "CC", "ED", "TRQ", "TRQ", "ATT"], "3-4-1-2": ["POR", "DC", "DC", "DC", "ES", "CC", "CC", "ED", "TRQ", "ATT", "ATT"], "3-5-2": ["POR", "DC", "DC", "DC", "ES", "CC", "CDC", "CC", "ED", "ATT", "ATT"], "3-5-1-1": ["POR", "DC", "DC", "DC", "ES", "CC", "CDC", "CC", "ED", "TRQ", "ATT"], "3-4-3": ["POR", "DC", "DC", "DC", "ES", "CC", "CC", "ED", "AS", "ATT", "AD"], "5-4-1": ["POR", "TS", "DC", "DC", "DC", "TD", "ES", "CC", "CC", "ED", "ATT"]};
const POSES = [['arms_crossed','Braccia incrociate'],['pointing','Indica']];
const MOMENTS = [['HT','HALF TIME'],['2H_END',"END OF 90'"],['FT','FULL TIME']];
const STATS = [
  'POSSESSO','xG','TIRI','TIRI IN PORTA','CORNER','FALLI',
  'FUORIGIOCO','AMMONITI','ESPULSI','PARATE','PRECISIONE PASSAGGI','PASSAGGI'
];
// Tipo di dato di ogni voce -> placeholder semi-trasparenti [casa, trasferta]
const STAT_PLACEHOLDERS = {pct:['58%','42%'], dec:['1.42','0.87'], int:['7','4']};
const STAT_TYPES = {'POSSESSO':'pct','PRECISIONE PASSAGGI':'pct','xG':'dec'};

const STEP_NAMES = {
  home:'Home',
  competition:'Competizione', side:'Campo', opponent:'Avversario', kit:'Maglia',
  player:'Giocatore', minute:'Risultato e minuto', pose:'Posa', score:'Risultato',
  natkind:'Grafica', natopp:'Avversaria', natplayer:'Giocatore', goaltype:'Tipo di gol',
  phase:'Fase', moment:'Momento', stats:'Statistiche', squad:'Convocati', mdpick:'Partita', lineup:'Formazione', photo:'Foto', match:'Partita', jrcolor:'Colore JR', module:'Modulo', xi11:'Giocatori', calmonth:'Mese', calrows:'Partite', tablecomp:'Classifica', phasephoto:'Foto', jrstyle:'Stile', jrratio:'Formato', jrphotos:'Foto', jrbg:'Sfondo', jrblur:'Posizione', jrlayout:'Layout', igcontent:'Contenuto'
};

const $ = id => document.getElementById(id);
