"""TABELLONE: legge da Diretta.it la fase a eliminazione diretta (Coppa Italia e coppe europee).

Stesso metodo della classifica (classifica_data.py): Chromium apre la pagina "tabellone"
e si leggono turni, squadre, gol e chi passa il turno (Diretta.it scrive in grassetto il
nome della squadra qualificata). I loghi del tabellone sono minuscoli (15 px): cliccando una
sfida compaiono le partite, i cui link portano alle pagine delle squadre, dove c'è lo stemma
da 100 px (lo stesso della classifica).

Si mostrano gli ultimi turni, dagli ottavi (o dal primo turno con al massimo 8 sfide) alla finale.
"""
import difflib
import os
import re
import time
import unicodedata

import log

from classifica_data import (
    _logo_grande_diretta, _logo_personalizzato, stagione_corrente_da_data, stagione_da_testo,
)

UA = ('Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 '
      '(KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36')

# theme: stile della classifica da riusare. league: classifica da cui prendere la pagina
# squadra di chi non ha ancora giocato (es. teste di serie della Coppa Italia).
COMPETIZIONI = {
    'CI': {'nome': 'Coppa Italia', 'theme': 'CI',
           'base': 'https://www.diretta.it/calcio/italia/coppa-italia{season}/', 'direct': True,
           'league': ('https://www.diretta.it/serie-a/classifiche/',
                      'https://www.diretta.it/calcio/italia/serie-b/classifiche/')},
    'UCL': {'nome': 'Champions League', 'theme': 'UCL',
            'base': 'https://www.diretta.it/calcio/europa/champions-league{season}/'},
    'UEL': {'nome': 'Europa League', 'theme': 'UEL',
            'base': 'https://www.diretta.it/calcio/europa/europa-league{season}/'},
    'UECL': {'nome': 'Conference League', 'theme': 'UECL',
             'base': 'https://www.diretta.it/calcio/europa/conference-league{season}/'},
}
_PAGES = {}            # competizione -> pagina del tabellone già trovata
_TEAM_URLS = {}        # nome -> pagina squadra (resta per la sessione)
MAX_FIRST = 8          # primo turno mostrato: al massimo 8 sfide (ottavi)

SHORT = {'1/8 finale': 'Ottavi', 'quarti di finale': 'Quarti', 'semi finali': 'Semifinali',
         'semifinali': 'Semifinali', 'finale': 'Finale', '1/16 finale': 'Sedicesimi'}

READ_ROUNDS = r"""() => [...document.querySelectorAll('.draw__round')].map(r => ({
  label: (r.querySelector('.draw__label')?.textContent || '').trim(),
  cells: [...r.querySelectorAll('[data-testid="wcl-drawCell"]')].map(c => ({
    teams: [...c.querySelectorAll('[data-testid="wcl-drawCellParticipant"]')].map(t => {
      const name = t.querySelector('[data-testid="wcl-simple-text-01"]');
      return {
        name: (name?.textContent || '').trim(),
        slot: /participant2/.test(t.className) ? 1 : 0,
        bold: /bold/i.test(name?.className || ''),
        scores: [...t.querySelectorAll('[data-testid="wcl-tableScore"]')].map(s => s.textContent.trim()),
      };
    })
  }))
}))"""


class TabelloneError(ValueError):
    """Tabellone non disponibile: il messaggio si mostra nella Mini App."""


def _norm(text):
    text = unicodedata.normalize('NFKD', str(text or '')).encode('ascii', 'ignore').decode()
    return re.sub(r'[^a-z0-9]', '', text.lower())


def _goals(scores):
    """['2', '1(4)'] -> (3, 4): somma dei gol e rigori (None se non ci sono)."""
    total, pens, seen = 0, None, False
    for s in scores:
        m = re.match(r'^(\d+)\s*(?:\((\d+)\))?$', s)
        if not m:
            continue
        seen = True
        total += int(m.group(1))
        if m.group(2) is not None:
            pens = int(m.group(2))
    return (total if seen else None), pens


def _season_part():
    """IMAGEGEN_TABELLONE_STAGIONE=2025-2026 legge una stagione archiviata (solo per le prove)."""
    season = os.environ.get('IMAGEGEN_TABELLONE_STAGIONE', '').strip()
    return f'-{season}' if season else ''


def _draw_ok(page):
    try:
        page.locator('.draw__round').first.wait_for(state='visible', timeout=8_000)
        page.wait_for_timeout(1500)
        return page.evaluate(READ_ROUNDS)
    except Exception:  # noqa: BLE001 - pagina senza tabellone
        return None


def _is_final_bracket(rounds):
    return bool(rounds) and rounds[-1]['label'].lower() == 'finale' and len(rounds[-1]['cells']) == 1


def _open_bracket(page, base, direct):
    """Apre il tabellone della fase finale; ritorna i turni letti oppure None."""
    known = _PAGES.get(base)
    for url in ([known] if known else []) + ([base + 'tabellone/'] if direct else []):
        page.goto(url, wait_until='domcontentloaded', timeout=45_000)
        rounds = _draw_ok(page)
        if _is_final_bracket(rounds):
            _PAGES[base] = url
            return rounds
    # Coppe europee: il tabellone è una delle "fasi" nella pagina classifiche.
    page.goto(base + 'classifiche/', wait_until='domcontentloaded', timeout=45_000)
    page.wait_for_timeout(2500)
    links = page.evaluate(r"""base => [...new Set([...document.querySelectorAll('a')].map(a => a.href)
        .filter(h => h.startsWith(base + 'classifiche/') && /classifiche\/[A-Za-z0-9]{8}\/$/.test(h)))]""", base)
    for link in reversed(links):        # la fase a eliminazione è di solito l'ultima
        page.goto(link, wait_until='domcontentloaded', timeout=45_000)
        rounds = _draw_ok(page)
        if _is_final_bracket(rounds):
            _PAGES[base] = link
            return rounds
    return None


def _played(cell):
    return any(t['scores'] for t in cell['teams'])


def _team_links(page, round_index, cell_index):
    """Link alle pagine squadra dalle partite di una sfida (clic sulla cella)."""
    cell = page.locator('.draw__round').nth(round_index).locator('[data-testid="wcl-drawCell"]').nth(cell_index)
    links = r"""() => [...document.querySelectorAll('a[href*="/partita/calcio/"]')].map(a => a.href)"""
    try:
        if cell.get_attribute('aria-expanded') == 'true':
            cell.click(timeout=5000)
            page.wait_for_timeout(300)
        before = set(page.evaluate(links))
        cell.click(timeout=5000)
        hrefs = []
        for _ in range(12):                 # l'elenco delle partite arriva dopo un attimo
            page.wait_for_timeout(250)
            hrefs = [h for h in page.evaluate(links) if h not in before]
            if hrefs:
                break
        cell.click(timeout=5000)            # richiude l'elenco
        page.wait_for_timeout(300)
    except Exception as exc:  # noqa: BLE001 - si usa il ripiego (classifica del campionato)
        log.warn('TABELLONE', f'Sfida {round_index}/{cell_index} non apribile: {exc}')
        return {}
    teams = {}
    for href in hrefs:
        m = re.search(r'/partita/calcio/([a-z0-9-]+)-([A-Za-z0-9]{8})/([a-z0-9-]+)-([A-Za-z0-9]{8})/', href)
        if m:
            teams[m.group(2)] = m.group(1)
            teams[m.group(4)] = m.group(3)
    return teams


def _match_slugs(names, slugs, known):
    """Nomi della sfida -> url squadra, accoppiando nome e "slug" del link più simili.
    Le squadre già note tengono il loro link; se resta un nome solo e un link solo, vanno insieme
    (es. "Stella Rossa" e "crvena-zvezda")."""
    out = {}
    used = {tid for tid in slugs if any(f'/{tid}/' in u for u in known.values())}
    todo = [n for n in names if n not in known]
    pairs = sorted(((difflib.SequenceMatcher(None, _norm(n), _norm(s)).ratio(), n, tid, s)
                    for n in todo for tid, s in slugs.items()), reverse=True)
    for score, name, tid, slug in pairs:
        if name in out or tid in used or score < .5:
            continue
        out[name] = f'/squadra/{slug}/{tid}/'
        used.add(tid)
    left = [n for n in todo if n not in out]
    free = [tid for tid in slugs if tid not in used]
    if len(left) == 1 and len(free) == 1:
        out[left[0]] = f'/squadra/{slugs[free[0]]}/{free[0]}/'
    return out


def _league_links(page, url):
    """{nome: url squadra} dalla classifica del campionato (ripiego per chi non ha giocato)."""
    try:
        page.goto(url, wait_until='domcontentloaded', timeout=45_000)
        page.locator('.ui-table__body .ui-table__row').first.wait_for(state='visible', timeout=30_000)
        return page.evaluate(r"""() => Object.fromEntries([...document.querySelectorAll('.ui-table__body .ui-table__row')]
            .map(r => r.querySelector('.tableCellParticipant__name')).filter(Boolean)
            .map(a => [a.textContent.trim(), a.getAttribute('href') || '']))""")
    except Exception as exc:  # noqa: BLE001
        log.warn('TABELLONE', f'Classifica di ripiego non letta: {exc}')
        return {}


def _scrape(comp):
    from playwright.sync_api import sync_playwright

    base = comp['base'].format(season=_season_part())
    started = time.time()
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            headless=True, executable_path=os.environ.get('IMAGEGEN_CHROME') or None,
            args=['--disable-dev-shm-usage'])
        try:
            context = browser.new_context(locale='it-IT', timezone_id='Europe/Rome', user_agent=UA)
            # Servono solo testi e link: niente immagini, font e video (pagine molto più rapide).
            context.route('**/*', lambda route: route.abort()
                          if route.request.resource_type in ('image', 'media', 'font') else route.continue_())
            page = context.new_page()
            rounds = _open_bracket(page, base, comp.get('direct'))
            if not rounds:
                return None
            title = page.title()
            log.info('TABELLONE', f'Tabellone trovato in {time.time() - started:.0f} s')
            log.info('TABELLONE', f'Pagina risolta: {page.url}')
            first = next(i for i, r in enumerate(rounds) if len(r['cells']) <= MAX_FIRST)
            team_urls = dict(_TEAM_URLS)       # squadre già trovate in questa sessione
            for ri in range(first, len(rounds)):
                for ci, cell in enumerate(rounds[ri]['cells']):
                    names = [t['name'] for t in cell['teams'] if t['name']]
                    if all(n in team_urls for n in names) or not _played(cell):   # senza partite niente link
                        continue
                    team_urls.update(_match_slugs(names, _team_links(page, ri, ci), team_urls))
            shown = rounds[first:]

            def missing():
                names = {t['name'] for r in shown for c in r['cells'] for t in c['teams'] if t['name']}
                return {n for n in names if n not in team_urls and not _logo_personalizzato(n)}
            # Chi non ha ancora giocato in questi turni: le sfide dei turni prima.
            for ri in range(first - 1, -1, -1):
                todo = missing()
                if not todo:
                    break
                for ci, cell in enumerate(rounds[ri]['cells']):
                    names = [t['name'] for t in cell['teams'] if t['name']]
                    if any(n in todo for n in names) and _played(cell):
                        team_urls.update(_match_slugs(names, _team_links(page, ri, ci), team_urls))
            # Ultimo ripiego: le classifiche dei campionati (teste di serie senza partite).
            for url in comp.get('league', ()):
                todo = missing()
                if not todo:
                    break
                league = _league_links(page, url)
                for name in todo:
                    hit = league.get(name) or next((u for n, u in league.items() if _norm(n) == _norm(name)), '')
                    if hit:
                        team_urls[name] = hit
        finally:
            browser.close()
    _TEAM_URLS.update(team_urls)
    log.info('TABELLONE', f'Squadre lette in {time.time() - started:.0f} s')
    return rounds, first, team_urls, title


def _order_like_previous(rounds):
    """Nel turno dopo, la squadra che viene dalla sfida di sopra va sopra (linee dritte)."""
    for prev, cur in zip(rounds, rounds[1:]):
        for k, cell in enumerate(cur['cells']):
            if len(cell['teams']) != 2 or 2 * k + 1 >= len(prev['cells']):
                continue
            below = {t['name'] for t in prev['cells'][2 * k + 1]['teams'] if t}
            above = {t['name'] for t in prev['cells'][2 * k]['teams'] if t}
            a, b = cell['teams']
            if (a and a['name'] in below) or (b and b['name'] in above):
                cell['teams'] = [b, a]


def fetch(comp_key):
    """Tabellone della fase finale, pronto per la grafica."""
    comp_key = (comp_key or '').upper()
    comp = COMPETIZIONI.get(comp_key)
    if not comp:
        raise TabelloneError('Competizione non valida per il tabellone.')
    log.info('TABELLONE', f"{comp['nome']}: leggo il tabellone da Diretta.it")
    try:
        result = _scrape(comp)
    except Exception as exc:  # noqa: BLE001 - messaggio leggibile nella Mini App
        log.warn('TABELLONE', f'Errore durante la lettura: {exc}')
        raise TabelloneError('Non riesco a leggere il tabellone da Diretta.it. Riprova tra poco.') from exc
    if result is None:
        raise TabelloneError(f"Il tabellone della {comp['nome']} non c'è ancora su Diretta.it "
                             '(la fase a eliminazione diretta non è iniziata).')
    raw, first, team_urls, title = result

    rounds = []
    for r in raw:
        cells = []
        for c in r['cells']:
            teams = [None, None]          # posto 0 = sopra, 1 = sotto (anche se c'è una squadra sola)
            for i, t in enumerate(c['teams'][:2]):
                if not t['name']:
                    continue
                goals, pens = _goals(t['scores'])
                slot = t['slot'] if len(c['teams']) == 1 else i
                teams[slot] = {'name': t['name'], 'goals': goals, 'pens': pens, 'winner': t['bold'],
                               'team_url': team_urls.get(t['name'], '')}
            cells.append({'teams': teams})
        rounds.append({'label': SHORT.get(r['label'].lower(), r['label']), 'cells': cells})
    _order_like_previous(rounds)

    rounds = rounds[first:]

    # Loghi da 100 px dalle pagine squadra (Juventus e Roma: i loghi personalizzati).
    from concurrent.futures import ThreadPoolExecutor
    teams = [t for r in rounds for c in r['cells'] for t in c['teams'] if t]
    unique = {t['name']: t for t in teams}
    def big(t):
        return _logo_personalizzato(t['name']) or (_logo_grande_diretta(t['team_url'], '') if t['team_url'] else '')
    with ThreadPoolExecutor(6) as pool:
        logos = dict(zip(unique, pool.map(big, unique.values())))
    missing = [n for n, url in logos.items() if not url]
    if missing:
        log.warn('TABELLONE', 'Loghi non trovati: ' + ', '.join(missing))
        raise TabelloneError(f"Non trovo il logo di {', '.join(missing[:3])}. Riprova tra poco.")
    for t in teams:
        t['logo'] = logos[t['name']]
        t.pop('team_url', None)

    return {'competition': comp_key, 'theme': comp['theme'], 'competition_name': comp['nome'],
            'stagione': (stagione_da_testo(title) or stagione_da_testo(_season_part())
                         or stagione_corrente_da_data()), 'rounds': rounds}
