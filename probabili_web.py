"""PROBABILE XI: probabile formazione della Juventus letta da Gazzetta, Sky Sport o Fantacalcio.it.

Ogni sito diventa lo stesso testo che si incolla a mano nella Mini App:
    "Juventus (3-5-2): Vicario; Gatti, Bremer, Lucumi; Kalulu, …; Woltemade, Kolo Muani"
cioè portiere e poi ogni reparto da destra a sinistra (prima il terzino destro),
che la Mini App sa già leggere e mettere da sinistra a destra nella grafica.

Ordine dei giocatori nei siti (controllato il 27/10/2026, 20 squadre):
- Gazzetta: portiere, poi reparti da destra a sinistra (come il testo);
- Sky: dati JSON nella pagina, formationPlace 1..11 nello stesso ordine;
- Fantacalcio: dall'attacco al portiere, ogni reparto da sinistra a destra (si capovolge).
Tutte e tre le pagine rispondono anche dai server di GitHub.
"""
import html
import json
import re

import requests

UA = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
      '(KHTML, like Gecko) Chrome/130.0 Safari/537.36')
TIMEOUT = 40
TEAM = 'juventus'
SOURCES = {
    'gazzetta': ('Gazzetta', 'https://www.gazzetta.it/Calcio/prob_form/'),
    'sky': ('Sky Sport', 'https://sport.sky.it/calcio/serie-a/probabili-formazioni'),
    'fantacalcio': ('Fantacalcio.it', 'https://www.fantacalcio.it/probabili-formazioni-serie-a'),
}


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
        return {'module': module, 'lines': _lines(players, sizes),
                'match': f'{teams[0]} - {teams[1]}'}
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
        return {'module': _module(sizes), 'lines': _lines(players, sizes),
                'match': f"{teams['home']} - {teams['away']}" if len(teams) == 2 else ''}
    raise LineupError('Sky Sport: partita della Juventus non trovata.')


# ---------- Fantacalcio.it ----------
def parse_fantacalcio(page):
    for m in re.finditer(r'<div class="team team-(home|away)"[^>]*>\s*<ul class="team-lineup"[^>]*>(.*?)</ul>',
                         page, re.S):
        body = m.group(2)
        if f'/squadre/{TEAM}/' not in body:
            continue
        # Righe separate da <li class="separator">: dall'attacco al portiere, ognuna da sinistra a destra.
        rows = []
        for chunk in re.split(r'<li class="separator"></li>', body):
            names = [_text(n) for n in re.findall(r'<span>(.*?)</span>', chunk, re.S)]
            if names:
                rows.append(names)
        lines = [list(reversed(r)) for r in reversed(rows)]
        players = [p for line in lines for p in line]
        sizes = [len(line) for line in lines[1:]]
        _check(players, sizes, 'Fantacalcio.it')
        if len(lines[0]) != 1:
            raise LineupError('Fantacalcio.it: portiere della Juventus non trovato.')
        return {'module': _module(sizes), 'lines': lines, 'match': ''}
    raise LineupError('Fantacalcio.it: partita della Juventus non trovata.')


PARSERS = {'gazzetta': parse_gazzetta, 'sky': parse_sky, 'fantacalcio': parse_fantacalcio}


def fetch(source):
    """{'source', 'label', 'module', 'text', 'match'} dalla pagina del sito."""
    if source not in SOURCES:
        raise LineupError('Sito non valido.')
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
            'text': _as_text(found['lines']), 'match': found['match']}
