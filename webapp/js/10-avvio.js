/* Mini App ImageGen JR. File caricati in ordine da index.html: l'ordine conta. */
/* ---------- Viewport ---------- */
function updateViewport() {
  const isDesktop = window.matchMedia('(min-width:900px)').matches;
  const vv = window.visualViewport;
  const h = isDesktop
    ? window.innerHeight
    : (vv ? Math.round(vv.height + vv.offsetTop) : window.innerHeight);
  document.documentElement.style.setProperty('--app-h',`${Math.max(320,h)}px`);
}

/* ---------- Events ---------- */
$('opponentSearch').addEventListener('input',async () => {
  selectedTeam = null;
  refreshSearchSummaries();
  renderSteps();
  if (!teamsLoaded) { await loadCatalogs(); refreshSearchSummaries(); }
});

$('playerSearch').addEventListener('input',async () => {
  selectedPlayer = null;
  refreshSearchSummaries();
  renderSteps();
  if (!playersLoaded) { await loadCatalogs(); refreshSearchSummaries(); }
});

$('etToggle').addEventListener('click',() => {
  haptic('select');
  etOn = !etOn;
  // Supplementari e Rigori si escludono: attivarne uno spegne l'altro.
  if (etOn) { pensOn = false; $('homePens').value = ''; $('awayPens').value = ''; }
  updatePhaseUI();
  renderSteps();
});
$('pensToggle').addEventListener('click',() => {
  haptic('select');
  pensOn = !pensOn;
  if (pensOn) etOn = false;
  if (!pensOn) { $('homePens').value = ''; $('awayPens').value = ''; }
  updatePhaseUI();
  renderSteps();
});
$('minute').addEventListener('input',renderSteps);
['homeScore','awayScore','homePens','awayPens','evHomeScore','evAwayScore'].forEach(id => $(id).addEventListener('input',renderSteps));
$('statRows').addEventListener('input',() => { collectStats(); renderSteps(); });
$('statClear').addEventListener('click',() => { clearStats(); clearError(); renderSteps(); });
$('squadText').addEventListener('input',() => { updateSquadSummary(); clearError(); renderSteps(); });
initPhotoEditor();
initPlayerPose();
initJrBlur();
initJrColor();
natInit();
initJrCollage();
initPhaseEditor();
$('squadLinkBtn').addEventListener('click',openLinkSheet);
$('lnkClose').addEventListener('click',closeLinkSheet);
$('lnkGo').addEventListener('click',submitLink);
$('lnkIn').addEventListener('keydown',e => { if (e.key === 'Enter') { e.preventDefault(); submitLink(); } });
$('lnkIn').addEventListener('input',() => { $('lnkErr').textContent = ''; $('lnkGo').disabled = lnkBusy || !$('lnkIn').value.trim(); });
// "Incolla": prende il link dagli appunti (se il telefono lo permette, altrimenti si tiene premuto il campo)
$('lnkPaste').addEventListener('click', async () => {
  try {
    const text = (await navigator.clipboard.readText()).trim();
    if (text) { $('lnkIn').value = text; $('lnkIn').dispatchEvent(new Event('input')); return; }
  } catch (_) {}
  $('lnkIn').focus();
});
$('lnkOv').addEventListener('click',e => { if (e.target.id === 'lnkOv') closeLinkSheet(); });
$('previewEdit').addEventListener('click',() => {
  if (kind === 'pxi') { openLayoutEditor(); return; }
  flowIndex = Math.max(0, flow.indexOf('calrows')); closePreview();
});
initLayoutEditor();
$('igText').addEventListener('input',() => { clearError(); igRefresh(); });
$('igPick').addEventListener('click',() => $('igFile').click());
$('igClear').addEventListener('click',igClearPhoto);
$('igFile').addEventListener('change',e => { uploadIgPhoto(e.target.files && e.target.files[0]); e.target.value = ''; });
initCalendarSheet();
initSettings();
initNav();
// "A mano": altra partita o dati inventati, si passa subito al passo successivo.
$('mdManualBtn').addEventListener('click', async () => { haptic('select'); await pickMdFixture('manual'); nextField(true); });

$('minuteQuick').addEventListener('click',event => {
  const b = event.target.closest('button[data-v]');
  if (!b) return;
  const input = $('minute');
  input.value = b.dataset.v;
  input.focus({preventScroll:true});
  try { input.setSelectionRange(input.value.length,input.value.length); } catch (_) {}
  renderSteps();
});

document.querySelectorAll('.step-btn').forEach(btn => {
  btn.addEventListener('click',() => {
    const input = $(btn.dataset.target);
    const delta = Number(btn.dataset.delta);
    const raw = input.value.trim();
    if (raw === '' && delta < 0) return;
    haptic('light');
    const next = Math.max(0,Math.min(99,(parseInt(raw || '0',10) || 0) + delta));
    if (raw !== '' && String(next) === raw) return;
    input.value = String(next);
    // Effetto contatore: il numero nuovo arriva dal basso (+) o dall'alto (−).
    if (motionOK()) input.animate([
      {opacity:0, transform:`translate3d(0,${delta > 0 ? 6 : -6}px,0)`},
      {opacity:1, transform:'none'}
    ],{duration:180, easing:EASE_OUT});
    renderSteps();
  });
});

// Invio: su desktop avanza, su mobile chiude solo la tastiera.
document.addEventListener('keydown',event => {
  if (event.key === 'Enter' && event.target && event.target.closest && event.target.closest('#ask')) return;   // invio del popup
  if (event.key === 'Enter' && event.target && event.target.matches && event.target.matches('input')) {
    event.preventDefault();
    if (event.target.closest('.stat-row')) {
      const all = [...$('statRows').querySelectorAll('input')];
      const next = all[all.indexOf(event.target) + 1];
      if (next) next.focus(); else event.target.blur();
      return;
    }
    if (finePointer) nextField(true);
    else event.target.blur();
  }
});

$('nextButton').addEventListener('click',() => { haptic('light'); nextField(true); });
$('backButton').addEventListener('click',() => { haptic('light'); previousField(); });
$('closeWorkflowButton').addEventListener('click',askCloseWorkflow);
$('homeSide').addEventListener('click',askGoHome);
$('homeTop').addEventListener('click',askGoHome);

if (window.visualViewport) {
  window.visualViewport.addEventListener('resize',updateViewport);
  window.visualViewport.addEventListener('scroll',updateViewport);
}
window.addEventListener('resize',updateViewport);

document.addEventListener('visibilitychange',() => {
  if (!LIVE && !document.hidden && (!playersLoaded || !teamsLoaded)) loadCatalogs();
});

if (LIVE) {
  // Dati della partita dal LiveScore: niente cataloghi, niente menu.
  document.body.classList.add('live');
  kind = 'match'; phase = LIVE_PHASE;
  const lead = document.querySelector('[data-screen="preview"] .lead');
  if (lead) lead.textContent = 'Se è tutto ok, premi “Conferma foto”: il bot la userà al fischio. Puoi ancora tornare indietro e cambiarla.';
  const note = document.querySelector('[data-screen="preview"] .note');
  if (note) note.textContent = 'Anteprima con il risultato di adesso: al fischio la grafica userà quello finale.';
  loadLiveState();
} else {
  restoreCatalogCache();
  refreshSearchSummaries();
  loadCatalogs();
  prefetchFixtures();
}

buildStatRows();
buildFlow();
renderHome();
renderFlow();
updateViewport();

if (!session) showError('Generatore non attivo. Avvia il workflow ImageGen.');
updateSessionTimer();
if (sessionExpiresAt && !sessionExpired()) timerHandle = setInterval(updateSessionTimer,1000);
// Scadenza vera dal servizio (riaprendo la Mini App il link ha quella iniziale).
if (directBase && session) {
  netFetch(`${directBase}/session?session=${encodeURIComponent(session)}`,{}, 15000)
    .then(r => r.ok ? r.json() : null).then(body => { sessionChecked = true; if (body && body.ok) applySessionInfo(body); else updateSessionTimer(); })
    .catch(() => { sessionChecked = true; updateSessionTimer(); });
}
