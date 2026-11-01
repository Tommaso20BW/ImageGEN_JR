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
    'Accept-Language': 'it-IT,it;q=0.9,en;q=0.8',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Referer': 'https://www.transfermarkt.it/',
}
LAST = {}   # ultima pagina scaricata (per capire cosa risponde il sito se qualcosa va storto)
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
        page = resp.read().decode('utf-8', 'replace')
        title = re.search(r'<title>(.*?)</title>', page, re.S)
        LAST.update(url=resp.geturl(), status=resp.status, size=len(page),
                    title=' '.join(html.unescape(title[1]).split())[:80] if title else '')
        print(f"TRANSFERMARKT {LAST['status']} {LAST['url']} {LAST['size']}B «{LAST['title']}»", flush=True)
        return page


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
    raise LookupError(f'Squadra non trovata su Transfermarkt ({", ".join(_variants(names)[:3])}). '
                      f'Risposta: {LAST.get("status")} «{LAST.get("title")}» {LAST.get("size")}B')


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


# ---------- ESPN (risponde anche dai server GitHub) ----------
ESPN = 'https://site.api.espn.com/apis/site/v2/sports/soccer/all/teams/{id}/schedule'
JUVE_ESPN = '111'
ESPN_COMPETITIONS = {
    'Italian Serie A': 'Serie A', 'Coppa Italia': 'Coppa Italia', 'Italian Supercoppa': 'Supercoppa Italiana',
    'UEFA Champions League': 'Champions League', 'UEFA Europa League': 'Europa League',
    'UEFA Conference League': 'Conference League', 'UEFA Europa Conference League': 'Conference League',
    'FIFA Club World Cup': 'Mondiale per Club',
}


def _espn_results(team_id, season=None):
    """Partite ufficiali giocate (niente amichevoli), dalla più recente."""
    import json
    url = ESPN.format(id=team_id) + (f'?season={season}' if season else '')
    req = urllib.request.Request(url, headers={'User-Agent': HEADERS['User-Agent']})
    with urllib.request.urlopen(req, timeout=20) as resp:
        events = json.loads(resp.read().decode('utf-8')).get('events') or []
    out = []
    for e in events:
        league = (e.get('league') or {}).get('name') or ''
        comp = (e.get('competitions') or [{}])[0]
        if 'Friendly' in league or not ((comp.get('status') or {}).get('type') or {}).get('completed'):
            continue
        teams = {c.get('homeAway'): c for c in comp.get('competitors') or []}
        if set(teams) != {'home', 'away'}:
            continue
        goals = lambda side: int(float(((teams[side].get('score') or {}).get('value')) or 0))
        out.append({
            'date': e['date'][:10], 'competition': ESPN_COMPETITIONS.get(league, league),
            'home_id': str(teams['home']['id']), 'away_id': str(teams['away']['id']),
            'home_name': teams['home']['team'].get('displayName', ''), 'away_name': teams['away']['team'].get('displayName', ''),
            'home_goals': goals('home'), 'away_goals': goals('away'),
            'winner': next((s for s in ('home', 'away') if teams[s].get('winner')), ''),
        })
    return sorted(out, key=lambda m: m['date'], reverse=True)


def _espn_fixtures():
    """Prossime partite della Juventus (stessa forma di _espn_results, senza risultato)."""
    import json
    try:
        req = urllib.request.Request(ESPN.format(id=JUVE_ESPN) + '?fixture=true', headers={'User-Agent': HEADERS['User-Agent']})
        with urllib.request.urlopen(req, timeout=20) as resp:
            events = json.loads(resp.read().decode('utf-8')).get('events') or []
    except OSError:
        return []
    out = []
    for e in events:
        teams = {c.get('homeAway'): c for c in ((e.get('competitions') or [{}])[0].get('competitors') or [])}
        if set(teams) == {'home', 'away'}:
            out.append({'home_id': str(teams['home']['id']), 'away_id': str(teams['away']['id']),
                        'home_name': teams['home']['team'].get('displayName', ''),
                        'away_name': teams['away']['team'].get('displayName', '')})
    return out


def espn_form(team_id, n=5):
    """Ultime n partite ufficiali: 'V', 'P', 'S' dalla più vecchia alla più recente."""
    ms = _espn_results(team_id)
    if len(ms) < n:
        ms += _espn_results(team_id, season=date.today().year - (1 if date.today().month >= 7 else 2))
    res = []
    for m in ms[:n]:
        side = 'home' if m['home_id'] == str(team_id) else 'away'
        res.append('P' if m['home_goals'] == m['away_goals'] and not m['winner'] else 'V' if m['winner'] == side else 'S')
    return res[::-1]


def _snapshot(names):
    import json
    from pathlib import Path
    from graphics.common import normalize
    path = Path(__file__).with_name('data') / 'h2h.json'
    if not path.is_file():
        return None
    teams = json.loads(path.read_text(encoding='utf-8')).get('teams') or {}
    for name in names:
        hit = teams.get(normalize(name or ''))
        if hit:
            return dict(hit, matches=list(hit['matches']))
    return None


def fetch(opponent_names, opponent_espn=''):
    """Bilancio + precedenti: archivio Transfermarkt (data/h2h.json) più le partite
    giocate dopo, prese da ESPN. Senza archivio prova Transfermarkt dal vivo.
    Forma: ESPN (Transfermarkt se manca l'id ESPN)."""
    from graphics.common import normalize
    data = _snapshot(opponent_names)
    if data is None:
        data = head_to_head(find_club(opponent_names))
        data['updated'] = date.today().isoformat()
    names = {normalize(n or '') for n in opponent_names}
    try:
        recent = _espn_results(JUVE_ESPN)
        if data['updated'][:4] < str(date.today().year):
            recent += _espn_results(JUVE_ESPN, season=int(data['updated'][:4]))
    except OSError:
        recent = []
    known = {m['date'] for m in data['matches']}
    for m in sorted(recent, key=lambda m: m['date']):
        opp_home = m['home_id'] != JUVE_ESPN
        opp_id, opp_name = (m['home_id'], m['home_name']) if opp_home else (m['away_id'], m['away_name'])
        same = (opponent_espn and opp_id == str(opponent_espn)) or normalize(opp_name) in names
        if not same or m['date'] <= data['updated'] or m['date'] in known:
            continue
        jg, og = (m['away_goals'], m['home_goals']) if opp_home else (m['home_goals'], m['away_goals'])
        juve_side = 'away' if opp_home else 'home'
        res = 'D' if jg == og and not m['winner'] else 'W' if m['winner'] == juve_side or jg > og else 'L'
        data[res] += 1
        data['played'] += 1
        data['gf'] += jg
        data['ga'] += og
        data['matches'].insert(0, {'competition': m['competition'], 'date': m['date'], 'juve_home': not opp_home,
                                   'home_goals': m['home_goals'], 'away_goals': m['away_goals']})
    if not opponent_espn:      # id ESPN dell'avversario dal calendario Juventus (partite giocate o in arrivo)
        opponent_espn = next((i for m in recent + _espn_fixtures() for i, nm in ((m['home_id'], m['home_name']), (m['away_id'], m['away_name']))
                              if i != JUVE_ESPN and normalize(nm) in names), '')

    def safe(fn, *args):
        try:
            return fn(*args)
        except (OSError, KeyError, LookupError, ValueError):
            return []
    data['form'] = {'juve': safe(espn_form, JUVE_ESPN),
                    'opp': safe(espn_form, opponent_espn) if opponent_espn else safe(form, data.get('tm_id', ''))}
    return data
