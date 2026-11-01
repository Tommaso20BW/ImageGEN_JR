"""HEAD TO HEAD: dati da Transfermarkt (bilancio, ultimi precedenti, forma).

- squadra: ricerca per nome sul sito (con varianti del nome, senza giovanili);
- bilancio e precedenti: pagina "Tutti gli incontri" Juventus-avversario;
- forma: ultime 5 partite giocate dal calendario della stagione di ogni squadra.
"""
import html
import re
import urllib.parse
import urllib.request
from datetime import date

BASE = 'https://www.transfermarkt.it'
JUVE_TM = '506'
HEADERS = {
    'User-Agent': ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                   '(KHTML, like Gecko) Chrome/130.0 Safari/537.36'),
    'Accept-Language': 'it-IT,it;q=0.9',
}
YOUTH = re.compile(r'\b(U\d\d|Primavera|Giovan|Under|Femminile|Women|Frauen|Youth|Reserves?|II|B)\b|\(U\d', re.I)
PREFIXES = re.compile(r'^(?:FC|AC|AS|ACF|SSC|SS|US|UC|AFC|CF|SC|SK|FK|NK|HNK|GNK|PFC|RCD|RC|CD|SD|UD|SL|SV|VfB|VfL|TSG|BSC|OGC|AJ|RB|KRC|KAA|KV|RSC|PSV)\s+', re.I)
SUFFIXES = re.compile(r'\s+(?:FC|CF|AC|SC|1\d{3}|Calcio|Milan)$', re.I)
COMPETITION_NAMES = {
    'UEFA Champions League': 'Champions League',
    'UEFA Europa League': 'Europa League',
    'UEFA Europa Conference League': 'Conference League',
    'UEFA Conference League': 'Conference League',
    'UEFA-Cup': 'Coppa UEFA',
    'UEFA Cup': 'Coppa UEFA',
    'UEFA Super Cup': 'Supercoppa UEFA',
    'UEFA Supercup': 'Supercoppa UEFA',
    'Europapokal der Landesmeister': 'Coppa dei Campioni',
    'Europapokal der Pokalsieger': 'Coppa delle Coppe',
    'Messestädte-Pokal': 'Coppa delle Fiere',
    'Messepokal': 'Coppa delle Fiere',
    'UI-Cup': 'Coppa Intertoto',
    'Intertoto Cup': 'Coppa Intertoto',
}


def _get(path, timeout=20):
    req = urllib.request.Request(BASE + path, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode('utf-8', 'replace')


def _variants(names):
    out = []
    for name in names:
        name = ' '.join(str(name or '').split())
        if not name:
            continue
        short = SUFFIXES.sub('', PREFIXES.sub('', name)).strip()
        for v in (name, short, PREFIXES.sub('', name).strip()):
            if v and v not in out:
                out.append(v)
    return out


def find_club(names):
    """Id Transfermarkt della prima squadra trovata con uno dei nomi."""
    for query in _variants(names):
        page = _get('/schnellsuche/ergebnis/schnellsuche?' + urllib.parse.urlencode({'query': query}))
        for title, club_id in re.findall(
                r'<td class="hauptlink"><a title="([^"]+)" href="/[^/]+/startseite/verein/(\d+)"', page):
            if club_id != JUVE_TM and not YOUTH.search(html.unescape(title)):
                return club_id
    raise LookupError('Squadra non trovata su Transfermarkt.')


def _competition(name):
    name = html.unescape(name)
    return COMPETITION_NAMES.get(name, name)


def head_to_head(opp_id):
    """Bilancio dal punto di vista della Juventus + elenco partite (dalla più recente)."""
    page = _get(f'/vergleich/vereineBegegnungen/statistik/{JUVE_TM}_{opp_id}')
    # Riepilogo del sito (comprende anche le partite senza tabellino):
    # partite, vittorie Juve, pareggi, sconfitte, gol fatti:subiti.
    i = page.find('Bilancio complessivo')
    if i < 0:
        raise LookupError('Nessun precedente su Transfermarkt.')
    cells = re.findall(r'<td class="zentriert">\s*([^<]*?)\s*</td>', page[i:i + 3000])[:5]
    num = lambda s: int(s.replace('.', '') or 0)
    wins, draws, losses = (num(c) for c in cells[1:4])
    played = num(cells[0]) or wins + draws + losses     # mai giocato: cella vuota
    gf, ga = (num(x) for x in (cells[4].split(':') + ['0'])[:2])
    matches = []
    j = page.find('Tutti gli scontri')
    body = page[j:page.find('</table>', j)] if j >= 0 else ''
    for row in re.findall(r'<tr>(.*?)</tr>', body, re.S):
        comp = re.search(r'title="([^"]+)" alt="[^"]*" class="wettbewerblogo"', row)
        day = re.search(r'hide-for-small">\w+, (\d\d)/(\d\d)/(\d{4})</td>', row)
        clubs = re.findall(r'/spielplan/verein/(\d+)/', row)
        score = re.search(r'ergebnis-link[^>]*><span[^>]*>\s*(\d+):(\d+)', row)
        if not (comp and day and clubs and score):
            continue
        matches.append({
            'competition': _competition(comp[1]),
            'date': f'{day[3]}-{day[2]}-{day[1]}',
            'juve_home': clubs[0] == JUVE_TM,
            'home_goals': int(score[1]), 'away_goals': int(score[2]),
        })
    return {'played': played, 'W': wins, 'D': draws, 'L': losses, 'gf': gf, 'ga': ga, 'matches': matches}


def form(club_id, today=None, n=5):
    """Ultime n partite giocate in stagione: 'V', 'P', 'S' dalla più vecchia alla più recente."""
    today = today or date.today()
    season = today.year if today.month >= 7 else today.year - 1
    rows = []
    for s in (season, season - 1):
        page = _get(f'/x/spielplan/verein/{club_id}/saison_id/{s}')
        for row in re.findall(r'<tr>(.*?)</tr>', page, re.S):
            d = re.search(r'(\d\d)/(\d\d)/(\d{4})', row)
            r = re.search(r'ergebnis-link[^>]*><span class="(greentext|redtext|)"?[^>]*>\s*\d+:\d+', row)
            if d and r:
                rows.append((f'{d[3]}{d[2]}{d[1]}', {'greentext': 'V', 'redtext': 'S'}.get(r[1], 'P')))
        if len(rows) >= n:
            break
    rows = sorted(set(rows))
    return [res for _d, res in rows[-n:]]


def fetch(opponent_names):
    opp = find_club(opponent_names)
    data = head_to_head(opp)
    data['form'] = {'juve': form(JUVE_TM), 'opp': form(opp)}
    return data
