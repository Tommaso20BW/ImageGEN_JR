"""Partite della Juventus da ESPN (stessa fonte di LiveScore): stadio, data e ora.

Per la MATCHDAY: scelto l'avversario, trova la partita più vicina contro di lui
(prima le prossime, poi le ultime giocate) e restituisce stadio, data e ora.
In casa lo stadio è sempre ALLIANZ STADIUM.
"""
import re
import time
import unicodedata
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import requests

JUVENTUS_ID = '111'
URL = 'https://site.api.espn.com/apis/site/v2/sports/soccer/all/teams/111/schedule'
HOME_STADIUM = 'ALLIANZ STADIUM'
ROME = ZoneInfo('Europe/Rome')
CACHE_SECONDS = 600
_cache = {'at': 0.0, 'events': []}

# Parole che indicano già uno stadio: se mancano si aggiunge "STADIO".
VENUE_WORDS = ('STADIO', 'STADIUM', 'STADION', 'ARENA', 'PARK', 'DOMUS', 'GROUND', 'PARC', 'CAMP ',
               'COLISEUM', 'FIELD')
FOREIGN = (('ESTADIO ', 'STADIO '), ('STADION ', 'STADIO '), ('STADE ', 'STADIO '), ('ESTADI ', 'STADIO '))


def plain(text):
    raw = unicodedata.normalize('NFKD', str(text or ''))
    return ''.join(c for c in raw if not unicodedata.combining(c))


def norm(text):
    return ' '.join(re.sub(r'[^a-z0-9 ]', ' ', plain(text).casefold()).split())


def stadium_label(name):
    """Nome stadio come nella grafica: maiuscolo, senza accenti, in italiano."""
    label = ' '.join(plain(name).upper().split())
    for foreign, italian in FOREIGN:
        if label.startswith(foreign):
            label = italian + label[len(foreign):]
    if not any(word in label for word in VENUE_WORDS):
        label = 'STADIO ' + label
    return label[:28].rstrip()


def _fetch(session=None):
    if time.time() - _cache['at'] < CACHE_SECONDS and _cache['events']:
        return _cache['events']
    http = session or requests
    events = []
    for params in ({'fixture': 'true'}, {}):            # prossime partite e risultati
        response = http.get(URL, params=params, timeout=15)
        response.raise_for_status()
        events += response.json().get('events', [])
    seen, out = set(), []
    for e in events:
        if e.get('id') not in seen:
            seen.add(e.get('id'))
            out.append(e)
    _cache.update(at=time.time(), events=out)
    return out


SUMMARY_URL = 'https://site.api.espn.com/apis/site/v2/sports/soccer/{league}/summary'
KITS = ('home', 'away', 'third')
_kits = {}


def kit(event_id, league, session=None):
    """Maglia indossata dalla Juventus in quella partita ('home'/'away'/'third'), o ''.
    ESPN la dà nel riepilogo (boxscore -> uniform.type) per le partite giocate o in corso."""
    key = (str(event_id), str(league))
    if key in _kits:
        return _kits[key]
    if not re.fullmatch(r'\d{1,12}', key[0]) or not re.fullmatch(r'[a-z0-9._]{2,40}', key[1]):
        return ''
    http = session or requests
    response = http.get(SUMMARY_URL.format(league=key[1]), params={'event': key[0]}, timeout=15)
    response.raise_for_status()
    found = ''
    for team in response.json().get('boxscore', {}).get('teams', []):
        if str(team.get('team', {}).get('id')) == JUVENTUS_ID:
            found = (team['team'].get('uniform') or {}).get('type', '')
    found = found if found in KITS else ''
    if found:                                   # una maglia trovata non cambia più
        _kits[key] = found
    return found


def _names(team):
    return {norm(team.get(k)) for k in ('displayName', 'shortDisplayName', 'name', 'location', 'abbreviation')
            if team.get(k)}


def _same_team(espn_team, candidates):
    names = _names(espn_team)
    for cand in candidates:
        c = norm(cand)
        if not c:
            continue
        for n in names:
            if c == n or (len(min(c, n, key=len)) >= 4 and (c in n or n in c)):
                return True
    return False


def find(opponent_names, home=None, session=None, now=None):
    """{'stadium', 'date' (AAAA-MM-GG), 'time' (HH:MM, ora italiana), 'home'} o None.

    home=True/False: solo le partite con la Juventus in casa / in trasferta."""
    now = now or datetime.now(timezone.utc)
    matches = []
    for event in _fetch(session):
        comp = (event.get('competitions') or [{}])[0]
        teams = comp.get('competitors') or []
        juve = next((t for t in teams if str(t.get('team', {}).get('id')) == JUVENTUS_ID), None)
        other = next((t for t in teams if t is not juve), None)
        if not juve or not other or not _same_team(other.get('team', {}), opponent_names):
            continue
        when = datetime.fromisoformat(event['date'].replace('Z', '+00:00'))
        is_home = juve.get('homeAway') == 'home'
        if home is not None and is_home != home:
            continue
        matches.append((when, comp, is_home))
    if not matches:
        return None
    upcoming = sorted((m for m in matches if m[0] >= now - timedelta(hours=6)), key=lambda m: m[0])
    when, comp, is_home = upcoming[0] if upcoming else max(matches, key=lambda m: m[0])
    venue = (comp.get('venue') or {}).get('fullName') or ''
    local = when.astimezone(ROME)
    return {
        'stadium': HOME_STADIUM if is_home else (stadium_label(venue) if venue else ''),
        'date': local.strftime('%Y-%m-%d'),
        'time': local.strftime('%H:%M'),
        'home': is_home,
    }


def _catalog_name(espn_team, rows):
    """Nome della squadra nel catalogo loghi (quello che usa la Mini App), o None."""
    for row in rows:
        if _same_team(espn_team, [row.get('name'), *(row.get('aliases') or [])]):
            return row.get('name')
    return None


def matches(rows, start=None, end=None, session=None):
    """Partite Juventus fra start ed end (datetime con fuso), ordinate per data.

    rows = squadre del catalogo loghi (nome + alias) per riconoscere gli avversari.
    """
    out = []
    for event in _fetch(session):
        comp = (event.get('competitions') or [{}])[0]
        teams = comp.get('competitors') or []
        juve = next((t for t in teams if str(t.get('team', {}).get('id')) == JUVENTUS_ID), None)
        other = next((t for t in teams if t is not juve), None)
        if not juve or not other:
            continue
        when = datetime.fromisoformat(event['date'].replace('Z', '+00:00'))
        if (start and when < start) or (end and when >= end):
            continue
        home = juve.get('homeAway') == 'home'
        venue = (comp.get('venue') or {}).get('fullName') or ''
        local = when.astimezone(ROME)
        espn_team = other.get('team', {})
        out.append({
            'id': str(event.get('id')),
            'date': local.strftime('%Y-%m-%d'),
            'time': local.strftime('%H:%M'),
            'competition': (event.get('league') or {}).get('slug', ''),
            'side': 'home' if home else 'away',
            'opponent': _catalog_name(espn_team, rows),
            'opponent_espn': espn_team.get('displayName', ''),
            'stadium': HOME_STADIUM if home else (stadium_label(venue) if venue else ''),
        })
    return sorted(out, key=lambda m: (m['date'], m['time']))
