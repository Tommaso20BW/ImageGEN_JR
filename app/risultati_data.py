"""RISULTATI DELLA GIORNATA: partite dell'ultima giornata da Diretta.it (Serie A e coppe europee).

Come la classifica: pagina letta con Chromium headless. Dalla pagina "risultati" si prende
l'ultima giornata con almeno una partita finita; dalla pagina "calendario" le partite della
stessa giornata non ancora giocate (con data e ora). Stemmi grandi come nella classifica.
"""
import difflib
import os
import re
import unicodedata
from concurrent.futures import ThreadPoolExecutor
from datetime import date

import log
from classifica_data import (COMPETIZIONI, COPPA_ITALIA_RISULTATI_URL, _logo_grande_diretta, _logo_personalizzato,
                             stagione_corrente_da_data, stagione_da_testo)

MESI = ('', 'Gennaio', 'Febbraio', 'Marzo', 'Aprile', 'Maggio', 'Giugno', 'Luglio',
        'Agosto', 'Settembre', 'Ottobre', 'Novembre', 'Dicembre')
GIORNI = ('Lun', 'Mar', 'Mer', 'Gio', 'Ven', 'Sab', 'Dom')

UA = ('Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 '
      '(KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36')

# Righe della pagina: giornata, squadre, punteggio, stato, link della partita.
ROWS_JS = '''() => [...document.querySelectorAll('.event__round, .event__match')].map(e =>
  e.classList.contains('event__round') ? {round: e.textContent.trim()} : {
    time: (e.querySelector('.event__stageTime, .event__time')?.textContent || '').trim(),
    stage: (e.querySelector('.event__stage')?.textContent || '').trim(),
    home: (e.querySelector('.event__homeParticipant')?.textContent || '').trim(),
    away: (e.querySelector('.event__awayParticipant')?.textContent || '').trim(),
    home_logo: e.querySelector('.event__homeParticipant img')?.src || '',
    away_logo: e.querySelector('.event__awayParticipant img')?.src || '',
    hs: (e.querySelector('.event__score--home')?.textContent || '').trim(),
    as: (e.querySelector('.event__score--away')?.textContent || '').trim(),
    live: e.classList.contains('event__match--live'),
    scheduled: e.classList.contains('event__match--scheduled'),
    link: e.querySelector('a.eventRowLink')?.href || '',
  })'''


# Turni a eliminazione diretta come li scrive Diretta.it -> come si dicono.
TURNI = {'1/32 finale': 'Trentaduesimi di finale', '1/16 finale': 'Sedicesimi di finale',
         '1/8 finale': 'Ottavi di finale', '1/4 finale': 'Quarti di finale', '1/2 finale': 'Semifinali',
         'semifinali': 'Semifinali', 'finale': 'Finale'}
NOMI = {**{k: v['nome'] for k, v in COMPETIZIONI.items()}, 'CI': 'Coppa Italia'}


class RisultatiError(ValueError):
    """Risultati non disponibili: il messaggio si mostra nella Mini App."""


def _url(comp_key, pagina):
    """Pagina 'risultati' o 'calendario' della competizione; '' = riepilogo, l'unica con le partite in corso."""
    parte = f'/{pagina}/' if pagina else '/'
    if comp_key == 'CI':
        return COPPA_ITALIA_RISULTATI_URL.replace('/risultati/', parte)
    return COMPETIZIONI[comp_key]['url'].replace('/classifiche/', parte)


def _scrape(urls):
    """{pagina: righe} per ogni url, più il titolo (h1) della prima pagina."""
    from playwright.sync_api import sync_playwright
    out, titolo = {}, ''
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True, executable_path=os.environ.get('IMAGEGEN_CHROME') or None,
                                             args=['--disable-dev-shm-usage'])
        try:
            context = browser.new_context(locale='it-IT', timezone_id='Europe/Rome', user_agent=UA)
            context.route('**/*', lambda route: route.abort()
                          if route.request.resource_type in ('image', 'media', 'font') else route.continue_())
            page = context.new_page()
            for name, url in urls.items():
                page.goto(url, wait_until='domcontentloaded', timeout=45_000)
                try:
                    page.locator('.event__match').first.wait_for(state='attached', timeout=25_000)
                except Exception:  # noqa: BLE001 - pagina senza partite (es. calendario finito)
                    out[name] = []
                    continue
                out[name] = page.evaluate(ROWS_JS)
                if not titolo:
                    titolo = page.locator('h1').first.inner_text(timeout=10_000)
        finally:
            browser.close()
    return out, titolo


def _giornate(rows):
    """[(etichetta, [partite])] nell'ordine della pagina."""
    out = []
    for row in rows:
        if 'round' in row:
            out.append((row['round'], []))
        elif out:
            out[-1][1].append(row)
        else:
            out.append(('', [row]))
    return out


def _norm(text):
    text = unicodedata.normalize('NFKD', text or '').encode('ascii', 'ignore').decode().lower()
    return re.sub(r'[^a-z0-9]+', '', text)


def _team_urls(match):
    """Pagine delle due squadre ricavate dal link della partita. Nel link le squadre sono in
    ordine alfabetico, non casa/trasferta: si abbinano col nome più simile."""
    m = re.search(r'/partita/calcio/([a-z0-9-]+)-([A-Za-z0-9]{8})/([a-z0-9-]+)-([A-Za-z0-9]{8})/', match.get('link', ''))
    if not m:
        return '', ''
    a = (m.group(1), f'/squadra/{m.group(1)}/{m.group(2)}/')
    b = (m.group(3), f'/squadra/{m.group(3)}/{m.group(4)}/')

    def sim(name, slug):
        return difflib.SequenceMatcher(None, _norm(name), _norm(slug)).ratio()
    h, w = match['home'], match['away']
    if sim(h, a[0]) + sim(w, b[0]) >= sim(h, b[0]) + sim(w, a[0]):
        return a[1], b[1]
    return b[1], a[1]


def _quando(testo):
    """'22.11. 20:45' -> (date, '20:45'); se manca qualcosa -> (None, testo)."""
    m = re.search(r'(\d{1,2})\.(\d{1,2})\.(?:\s*(\d{4}))?\s*(\d{1,2}:\d{2})?', testo or '')
    if not m:
        return None, (testo or '').strip()
    oggi = date.today()
    giorno, mese = int(m.group(1)), int(m.group(2))
    anno = int(m.group(3)) if m.group(3) else oggi.year
    if not m.group(3) and mese - oggi.month > 6:      # dicembre visto da gennaio
        anno -= 1
    elif not m.group(3) and oggi.month - mese > 6:    # gennaio visto da dicembre
        anno += 1
    try:
        return date(anno, mese, giorno), m.group(4) or ''
    except ValueError:
        return None, testo.strip()


def _date_label(giorni):
    """Date della giornata: '21–23 Novembre', '30 Novembre – 1 Dicembre', '4 Novembre'."""
    giorni = sorted(set(d for d in giorni if d))
    if not giorni:
        return ''
    a, b = giorni[0], giorni[-1]
    if a == b:
        return f'{a.day} {MESI[a.month]}'
    if a.month == b.month:
        return f'{a.day}–{b.day} {MESI[a.month]}'
    return f'{a.day} {MESI[a.month]} – {b.day} {MESI[b.month]}'


def _nome(text):
    """Nome della squadra senza le aggiunte di Diretta.it ("FiorentinaQualificato: Fiorentina")."""
    return re.sub(r'Qualificat[oa]\s*:.*$', '', text or '').strip()


def _gol(text):
    """'1(4)' -> (1, 4): gol e rigori (None se non ci sono). '-' -> (None, None)."""
    m = re.fullmatch(r'\s*(\d+)\s*(?:\((\d+)\))?\s*', text or '')
    return (int(m.group(1)), int(m.group(2)) if m.group(2) else None) if m else (None, None)


def _partita(row):
    row = {**row, 'home': _nome(row.get('home')), 'away': _nome(row.get('away'))}
    giorno, ora = _quando(row.get('time', ''))
    (hs, hr), (as_, ar) = _gol(row.get('hs')), _gol(row.get('as'))
    finita = not row.get('scheduled') and not row.get('live') and hs is not None and as_ is not None
    live = bool(row.get('live')) and hs is not None
    stato = 'finita' if finita else 'live' if live else 'rinviata' if re.search(r'rinv|annul|sosp', row.get('stage', ''), re.I) else 'da_giocare'
    home_url, away_url = _team_urls(row)
    out = {
        'home': row['home'], 'away': row['away'],
        'home_logo': row.get('home_logo', ''), 'away_logo': row.get('away_logo', ''),
        '_home_url': home_url, '_away_url': away_url,
        'stato': stato, '_giorno': giorno,
        'quando': f'{GIORNI[giorno.weekday()]} {giorno.day}/{giorno.month}' + (f' · {ora}' if ora else '') if giorno else ora,
    }
    if stato in ('finita', 'live'):
        out['gol_casa'], out['gol_trasferta'] = hs, as_
        extra = (row.get('time', '') + ' ' + row.get('stage', '')).lower()
        if hr is not None and ar is not None:
            out['rigori'] = [hr, ar]
        elif 'suppl' in extra:
            out['dts'] = True
    return out


def _in_corso(righe, riepilogo):
    """Partite in corso della stessa giornata, dal riepilogo del torneo: Diretta.it non le mette né nei
    risultati né nel calendario. Nel riepilogo non hanno la giornata, quindi entrano solo se nessuna delle
    due squadre gioca già in questa giornata (oppure se sono il ritorno di una partita già presente)."""
    coppie = {(_nome(r['home']), _nome(r['away'])) for r in righe}
    squadre = {s for c in coppie for s in c}
    oggi = date.today().strftime('%d.%m.')
    out = []
    for r in riepilogo:
        if 'round' in r or not r.get('live') or not r.get('home') or not r.get('away'):
            continue
        h, a = _nome(r['home']), _nome(r['away'])
        if (h, a) in coppie or not ((a, h) in coppie or (h not in squadre and a not in squadre)):
            continue
        out.append({**r, 'time': oggi})           # nel riepilogo l'ora è il minuto di gioco
        coppie.add((h, a))
        squadre |= {h, a}
    return out


def _tie(a, r):
    """Andata (a) e ritorno (r) della stessa coppia in una partita sola, con il totale.
    Squadre e stemmi come all'andata; nel ritorno casa e trasferta sono invertite."""
    t = {k: v for k, v in a.items() if k not in ('gol_casa', 'gol_trasferta', 'rigori', 'dts')}
    t['_giorno2'] = r['_giorno']
    giocata = lambda p: p['stato'] in ('finita', 'live')  # noqa: E731
    if not giocata(a):
        if giocata(r):
            return r                       # andata non giocata (rinviata): resta solo il ritorno
        t['ritorno_quando'] = r['quando']
        return t
    t['gol_casa'], t['gol_trasferta'] = a['gol_casa'], a['gol_trasferta']
    if not giocata(r):
        t['ritorno_quando'] = r['quando']  # solo l'andata: il totale è l'andata
        return t
    rc, rt = r['gol_trasferta'], r['gol_casa']   # gol del ritorno visti dalla parte dell'andata
    t['andata_res'] = [a['gol_casa'], a['gol_trasferta']]
    t['ritorno_res'] = [rc, rt]
    t['gol_casa'], t['gol_trasferta'] = a['gol_casa'] + rc, a['gol_trasferta'] + rt
    t['stato'] = 'live' if 'live' in (a['stato'], r['stato']) else 'finita'
    if 'rigori' in r:
        t['rigori'] = [r['rigori'][1], r['rigori'][0]]
    elif r.get('dts'):
        t['dts'] = True
    return t


def _accoppia(partite):
    """Andata e ritorno (stesse due squadre a campi invertiti nella stessa fase) -> una riga sola."""
    out, usati = [], set()
    for i, p in enumerate(partite):
        if i in usati:
            continue
        j = next((k for k in range(i + 1, len(partite)) if k not in usati
                  and partite[k]['home'] == p['away'] and partite[k]['away'] == p['home']), None)
        if j is None:
            out.append(p)
            continue
        usati.add(j)
        a, r = sorted((p, partite[j]), key=lambda x: (x['_giorno'] or date.max, x['quando']))
        out.append(_tie(a, r))
    return out


def _loghi(partite):
    """Stemmi grandi di Diretta.it (pagina della squadra), salvo Juventus e Roma personalizzati."""
    jobs = []
    for p in partite:
        for side in ('home', 'away'):
            jobs.append((p, side))

    def big(job):
        p, side = job
        return _logo_personalizzato(p[side]) or _logo_grande_diretta(p[f'_{side}_url'], p[f'{side}_logo'])
    with ThreadPoolExecutor(max_workers=min(6, len(jobs) or 1)) as pool:
        loghi = list(pool.map(big, jobs))
    for (p, side), logo in zip(jobs, loghi):
        p[f'{side}_logo'] = logo


def fetch(comp_key: str) -> dict:
    """Come _fetch, ma richieste uguali nello stesso momento leggono Diretta.it una volta sola."""
    import diretta_cache
    from classifica_data import SHARED_SECONDS
    key = (comp_key or '').upper()
    return diretta_cache.shared(('risultati', key), SHARED_SECONDS, lambda: _fetch(key))


def _fetch(comp_key: str) -> dict:
    """Ultima giornata/fase di SA, CI, UCL, UEL o UECL: tutte le partite di quella fase,
    finite e ancora da giocare (Coppa Italia e coppe europee comprese, senza limiti di settimana)."""
    comp_key = (comp_key or '').upper()
    if comp_key not in NOMI:
        raise RisultatiError('Competizione non valida: scegli Serie A, Coppa Italia, Champions, Europa o Conference.')
    comp = {'nome': NOMI[comp_key]}
    log.info('RISULTATI', f"{comp['nome']}: leggo risultati e calendario da Diretta.it")
    try:
        pagine, titolo = _scrape({'risultati': _url(comp_key, 'risultati'), 'calendario': _url(comp_key, 'calendario'),
                                  'riepilogo': _url(comp_key, '')})
    except Exception as exc:  # noqa: BLE001 - errore della pagina -> messaggio leggibile
        log.warn('RISULTATI', f'Errore durante la lettura da Diretta.it: {exc}')
        raise RisultatiError('Non riesco a leggere i risultati da Diretta.it. Riprova tra poco.') from exc

    giocate = [g for g in _giornate(pagine.get('risultati', [])) if g[1]]
    if not giocate:
        raise RisultatiError(f"Diretta.it non mostra ancora risultati di {comp['nome']} in questa stagione.")
    etichetta, finite = giocate[0]
    # Partite della stessa giornata ancora da giocare (o in corso), dal calendario.
    altre = next((rows for label, rows in _giornate(pagine.get('calendario', [])) if label == etichetta), [])
    visti = {(r['home'], r['away']) for r in finite}
    righe = finite + [r for r in altre if (r['home'], r['away']) not in visti]
    live = _in_corso(righe, pagine.get('riepilogo', []))
    righe += live
    log.info('RISULTATI', f"{comp['nome']} {etichetta}: {len(finite)} finite, {len(righe) - len(finite) - len(live)} "
                          f"da giocare, {len(live)} in corso")
    # Giornate di Serie A e coppe europee: squadre/2 partite (10 o 18). Se ne mancano, meglio niente
    # grafica che una grafica incompleta.
    attese = (COMPETIZIONI.get(comp_key) or {}).get('squadre', 0) // 2
    if attese and etichetta.lower().startswith('giornata') and len(righe) < attese:
        log.warn('RISULTATI', f"{comp['nome']}: {len(righe)} partite su {attese} nella {etichetta}")
        raise RisultatiError(f"{comp['nome']}, {etichetta}: Diretta.it mostra {len(righe)} partite su {attese}. "
                             f"Riprova tra qualche minuto.")

    partite = _accoppia([_partita(r) for r in righe if r.get('home') and r.get('away')])
    # In ordine di calendario: prima le partite più vecchie, come si leggono nella giornata.
    partite.sort(key=lambda p: (p['_giorno'] or date.max, p['quando']))
    _loghi(partite)
    giorni = [p.pop('_giorno') for p in partite] + [p.pop('_giorno2', None) for p in partite]
    for p in partite:
        p.pop('_home_url'), p.pop('_away_url')

    m = re.search(r'(\d+)', etichetta)
    return {
        'competition': comp_key,
        'competition_name': comp['nome'],
        'giornata': int(m.group(1)) if m and etichetta.lower().startswith('giornata') else None,
        'turno': TURNI.get(etichetta.strip().lower(), etichetta),
        'date': _date_label(giorni),
        'stagione': stagione_da_testo(titolo) or stagione_corrente_da_data(),
        'partite': partite,
    }
