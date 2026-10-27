"""PROBABILE XI: probabile formazione della Juventus letta da Gazzetta o Sky Sport.

Ogni sito diventa lo stesso testo che si incolla a mano nella Mini App:
    "Juventus (3-5-2): Vicario; Gatti, Bremer, Lucumi; Kalulu, …; Woltemade, Kolo Muani"
cioè portiere e poi ogni reparto da destra a sinistra (prima il terzino destro),
che la Mini App sa già leggere e mettere da sinistra a destra nella grafica.

Ordine dei giocatori nei siti (controllato il 27/10/2026, 20 squadre):
- Gazzetta: portiere, poi reparti da destra a sinistra (come il testo);
- Sky: dati JSON nella pagina, formationPlace 1..11 nello stesso ordine;
Entrambe le pagine rispondono anche dai server di GitHub.
"""
import html
import json
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor

import requests

UA = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
      '(KHTML, like Gecko) Chrome/130.0 Safari/537.36')
TIMEOUT = 40
TEAM = 'juventus'
SOURCES = {
    'gazzetta': ('Gazzetta', 'https://www.gazzetta.it/Calcio/prob_form/'),
    'sky': ('Sky Sport', 'https://sport.sky.it/calcio/serie-a/probabili-formazioni'),
}


MONTHS = {m: i for i, m in enumerate(
    ('gennaio', 'febbraio', 'marzo', 'aprile', 'maggio', 'giugno', 'luglio', 'agosto',
     'settembre', 'ottobre', 'novembre', 'dicembre'), 1)}
CACHE_SECONDS = 120       # pagina riletta al massimo ogni 2 minuti (data/ora e pulsante)
_cache = {}
_cache_lock = threading.Lock()


class LineupError(ValueError):
    """Formazione non trovata: il messaggio va mostrato nella Mini App."""


def _text(fragment):
    return ' '.join(html.unescape(re.sub(r'<[^>]+>', ' ', fragment)).split())


def _module(sizes):
    return '-'.join(str(n) for n in sizes)


def _lines(players, sizes):
    """[11 nomi] + [4, 3, 3] -> [[portiere], [4], [3], [3]]."""
    out, at = [[players[0]]], 1
    for n in sizes:
        out.append(players[at:at + n])
        at += n
    return out


def _name(value):
    """Cognome senza iniziale del nome: "Sarr P." / "Lucumí J." -> "Sarr" / "Lucumí"."""
    return re.sub(r'\s+\w\.$', '', ' '.join(str(value).split())).strip()


def _as_text(lines):
    """Righe (portiere, poi reparti da destra a sinistra) -> testo come quello incollato."""
    module = _module(len(line) for line in lines[1:])
    return f'Juventus ({module}): ' + '; '.join(', '.join(_name(p) for p in line) for line in lines)


def _check(players, sizes, site):
    if len(players) != 11 or sum(sizes) != 10:
        raise LineupError(f'{site}: formazione della Juventus incompleta.')


# ---------- Gazzetta ----------
def parse_gazzetta(page):
    for block in re.split(r'<div id="match-\d+" class="bck-box-match-details"', page)[1:]:
        teams = re.findall(r'class="details-team__name"[^>]*>\s*([^<]+?)\s*</a', block)
        if len(teams) < 2 or not any(TEAM in t.lower() for t in teams[:2]):
            continue
        side = 'home' if TEAM in teams[0].lower() else 'away'
        modules = re.findall(r'<strong>Modulo:</strong>\s*([\d\-]+)', block)
        lists = re.findall(r'<div class="lineup-team is--(home|away)">(.*?)</ul>', block, re.S)
        names = next((re.findall(r'class="lineup-team__name">([^<]+)<', body)
                      for s, body in lists if s == side), [])
        players = [html.unescape(n).strip() for n in names]
        module = modules[0 if side == 'home' else 1] if len(modules) >= 2 else ''
        sizes = [int(x) for x in module.split('-') if x.isdigit()]
        _check(players, sizes, 'Gazzetta')
        # "Ultimo aggiornamento: 26 ottobre 2026, ore 19:40" della scheda della partita.
        upd = re.search(r'aggiornamento:\s*(\d{1,2})\s+([a-zà]+)\s+\d{4},\s*ore\s*(\d{1,2})[:.](\d{2})', _text(block), re.I)
        updated = (f'{int(upd[1]):02d}/{MONTHS.get(upd[2].lower(), 0):02d} {int(upd[3]):02d}:{upd[4]}'
                   if upd and upd[2].lower() in MONTHS else '')
        return {'module': module, 'lines': _lines(players, sizes),
                'match': f'{teams[0]} - {teams[1]}', 'updated': updated}
    raise LineupError('Gazzetta: partita della Juventus non trovata.')


# ---------- Sky Sport ----------
def parse_sky(page):
    dec = json.JSONDecoder()
    for m in re.finditer(r'"formation":"(\d{3,5})","id":"\d+"[^{]*?"name":"([^"]+)"', page):
        formation, name = m.groups()
        if TEAM not in name.lower():
            continue
        i = page.find('"startingLineup":', m.end())
        if i < 0:
            break
        arr, _ = dec.raw_decode(page[page.index('[', i):])
        arr = sorted(arr, key=lambda p: int(p.get('formationPlace') or 99))
        # fullName ha i nomi da calcio ("Bremer", "Douglas Luiz", "Lucumí J."): via l'iniziale.
        players = [re.sub(r'\s+\w\.$', '', str(p.get('fullName') or p.get('surname') or '')).strip()
                   for p in arr]
        sizes = [int(c) for c in formation]
        _check(players, sizes, 'Sky Sport')
        # Partita: casa - trasferta (nei dati di Sky la squadra in trasferta viene prima).
        start = page.rfind('"matchId"', 0, m.start())
        end = page.find('"matchId"', m.end())
        seg = page[start:end if end > 0 else len(page)]
        teams = {k: v for k, v in re.findall(r'"(home|away)":\{"ctaUrl":"[^"]*","formation":"\d*","id":"\d+",'
                                             r'"logoUrl":"[^"]*","name":"([^"]+)"', seg)}
        # "Aggiornato: 27/10, 13:16": uno solo per tutta la giornata.
        upd = re.search(r'Aggiornato:\s*(\d{1,2})/(\d{1,2}),?\s*(\d{1,2})[:.](\d{2})', page)
        return {'module': _module(sizes), 'lines': _lines(players, sizes),
                'match': f"{teams['home']} - {teams['away']}" if len(teams) == 2 else '',
                'updated': f'{int(upd[1]):02d}/{int(upd[2]):02d} {int(upd[3]):02d}:{upd[4]}' if upd else ''}
    raise LineupError('Sky Sport: partita della Juventus non trovata.')


PARSERS = {'gazzetta': parse_gazzetta, 'sky': parse_sky}


def fetch(source):
    """{'source', 'label', 'module', 'text', 'match', 'updated'} dalla pagina del sito.

    Il risultato (o l'errore) resta valido 2 minuti: la data mostrata sotto il pulsante
    e la formazione caricata toccandolo vengono dalla stessa lettura.
    """
    if source not in SOURCES:
        raise LineupError('Sito non valido.')
    with _cache_lock:
        hit = _cache.get(source)
    if hit and time.monotonic() - hit[0] < CACHE_SECONDS:
        if isinstance(hit[1], Exception):
            raise hit[1]
        return hit[1]
    try:
        result = _fetch(source)
    except LineupError as exc:
        with _cache_lock:
            _cache[source] = (time.monotonic(), exc)
        raise
    with _cache_lock:
        _cache[source] = (time.monotonic(), result)
    return result


def updates():
    """{sito: 'gg/mm hh:mm' o ''} per tutti i siti, letti in parallelo."""
    def one(source):
        try:
            return source, fetch(source).get('updated', '')
        except LineupError:
            return source, ''
    with ThreadPoolExecutor(max_workers=len(SOURCES)) as pool:
        return dict(pool.map(one, SOURCES))


def _fetch(source):
    label, url = SOURCES[source]
    try:
        r = requests.get(url, headers={'User-Agent': UA, 'Accept-Language': 'it-IT,it'}, timeout=TIMEOUT)
    except requests.RequestException:
        raise LineupError(f'{label} non raggiungibile. Riprova o incolla la formazione.') from None
    if r.status_code != 200:
        raise LineupError(f'{label} non raggiungibile (HTTP {r.status_code}).')
    r.encoding = 'utf-8'
    try:
        found = PARSERS[source](r.text)
    except LineupError:
        raise
    except Exception:
        raise LineupError(f'{label}: pagina cambiata, formazione non leggibile. Incollala a mano.') from None
    return {'source': source, 'label': label, 'module': found['module'],
            'text': _as_text(found['lines']), 'match': found['match'], 'updated': found.get('updated', '')}
