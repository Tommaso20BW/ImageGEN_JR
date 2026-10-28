"""SQUAD LIST: convocati della prima squadra letti direttamente da juventus.com.

Ogni articolo "I convocati" del sito diventa una partita con i suoi giocatori:
    "Serie A | Genoa-Juventus | I convocati"  ->  Genoa (casa) - Juventus, Serie A, 23 nomi.

Come si legge la pagina (struttura controllata il 28/10/2026 su "Genoa-Juventus"):
- il blocco JSON-LD "NewsArticle" ha titolo (headline), data (datePublished) e
  parole chiave: ["First Team Men", "2026/27", "Serie A"]. "First Team Men" = prima
  squadra maschile: Next Gen, U20, femminile ecc. vengono scartate;
- i giocatori sono un paragrafo ciascuno nel corpo: "<p>3 Bremer</p>" (e anche
  nell'articleBody del JSON-LD, usato come riserva).

Gli articoli si trovano nelle pagine elenco del sito (link /it/news/articoli/...-convocati...);
se l'elenco non risponde si può passare il link di un articolo preciso.
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
TIMEOUT = 20
BASE = 'https://www.juventus.com'
LISTINGS = (
    f'{BASE}/it/news/articoli/',
    f'{BASE}/it/news/',
    f'{BASE}/it/search?q=convocati',
)
MAX_CANDIDATES = 24     # articoli letti per volta
MAX_ITEMS = 10          # partite mostrate
MIN_PLAYERS = 11
LIST_CACHE_SECONDS = 120
ARTICLE_CACHE_SECONDS = 3600
URL_OK = re.compile(r'^https://www\.juventus\.com/(?:it|en)/news/articoli/[\w\-./%]+$')

# Competizione del sito -> codice usato da ImageGEN (vedi graphics/squad_list.py).
COMPETITIONS = (
    ('conference', 'uefa.europa.conf'),
    ('europa league', 'uefa.europa'),
    ('champions', 'uefa.champions'),
    ('coppa italia', 'ita.coppa_italia'),
    ('supercoppa', 'ita.super_cup'),
    ('serie a', 'ita.1'),
)
# Parole che indicano una squadra diversa dalla prima maschile.
NOT_FIRST_TEAM = ('first team women', 'next gen', 'under 20', 'under 19', 'under 18', 'under 17',
                  'u20', 'u19', 'u18', 'u17', 'primavera', 'femminile', 'women', 'academy')


class ConvocatiError(ValueError):
    """Convocati non letti: il messaggio va mostrato nella Mini App."""


_list_cache = {}
_article_cache = {}
_lock = threading.Lock()


def _get(url):
    try:
        response = requests.get(url, headers={'User-Agent': UA, 'Accept-Language': 'it-IT,it;q=0.9'},
                                timeout=TIMEOUT)
        response.raise_for_status()
    except requests.RequestException as exc:
        raise ConvocatiError(f'juventus.com non raggiungibile ({type(exc).__name__}).') from exc
    response.encoding = response.encoding or 'utf-8'
    return response.text


def _clean(fragment):
    return ' '.join(html.unescape(re.sub(r'<[^>]+>', ' ', fragment)).split())


def _jsonld_article(page):
    """Blocco JSON-LD NewsArticle (type=\"application/ld&#x2B;json\": il + è scritto come entità)."""
    pattern = r'<script[^>]*type="application/ld(?:\+|&#x2B;|&#43;|&plus;)json"[^>]*>(.*?)</script>'
    for raw in re.findall(pattern, page, re.S | re.I):
        try:
            data = json.loads(html.unescape(raw) if '&quot;' in raw else raw)
        except ValueError:
            continue
        for block in data if isinstance(data, list) else [data]:
            if isinstance(block, dict) and block.get('@type') == 'NewsArticle':
                return block
    return None


def _competition(candidates):
    for text in candidates:
        low = str(text or '').lower()
        for needle, code in COMPETITIONS:
            if needle in low:
                return code, str(text).strip()
    return '', ''


def _teams(headline):
    """\"Serie A | Genoa-Juventus | I convocati\" o \"I convocati per Juventus-Lecce\" -> (casa, trasferta)."""
    for part in re.split(r'\s*\|\s*', headline):
        text = re.sub(r'(?i)\bi\s+convocati\b(\s+(?:per|di|della|del|contro))?', ' ', part)
        text = ' '.join(text.replace(',', ' ').split()).strip(' -–—')
        match = re.match(r'(?i)^juventus\s*[-–—]\s*(.+)$', text)
        if match:
            return 'Juventus', match.group(1).strip()
        match = re.match(r'(?i)^(.+?)\s*[-–—]\s*juventus$', text)
        if match:
            return match.group(1).strip(), 'Juventus'
    return None


def _players(page, article):
    """Righe \"3 Bremer\": prima dai paragrafi del corpo, poi dall'articleBody del JSON-LD."""
    rows = []
    for fragment in re.findall(r'<p[^>]*>(.*?)</p>', page, re.S | re.I):
        text = _clean(fragment)
        if re.fullmatch(r'\d{1,2}\s+\S.{0,40}', text):
            rows.append(text)
    if len(rows) < MIN_PLAYERS:
        rows = [line.strip() for line in str(article.get('articleBody', '')).splitlines()
                if re.fullmatch(r'\d{1,2}\s+\S.{0,40}', line.strip())]
    seen, out = set(), []
    for row in rows:
        key = row.lower()
        if key not in seen:
            seen.add(key)
            out.append(row)
    return out


def _rome_day(iso):
    """datePublished (UTC) -> giorno italiano AAAA-MM-GG."""
    iso = str(iso or '')
    try:
        from datetime import datetime, timezone
        from zoneinfo import ZoneInfo
        stamp = datetime.fromisoformat(iso.replace('Z', '+00:00'))
        if stamp.tzinfo is None:
            stamp = stamp.replace(tzinfo=timezone.utc)
        return stamp.astimezone(ZoneInfo('Europe/Rome')).strftime('%Y-%m-%d')
    except Exception:  # noqa: BLE001 - senza fuso orario vale il giorno scritto nella data
        return iso[:10]


def parse_article(page, url):
    """Una partita con i suoi convocati, oppure None se l'articolo non è dei convocati della prima squadra."""
    article = _jsonld_article(page)
    if not article:
        return None
    headline = html.unescape(str(article.get('headline', ''))).strip()
    if 'convocat' not in headline.lower():
        return None
    keywords = [str(k).strip() for k in (article.get('keywords') or []) if str(k).strip()]
    low_words = [k.lower() for k in keywords]
    if keywords and 'first team men' not in low_words:
        return None
    if any(bad in f'{headline.lower()} | ' + ' | '.join(low_words) for bad in NOT_FIRST_TEAM):
        return None
    teams = _teams(headline)
    if not teams:
        return None
    home, away = teams
    players = _players(page, article)
    if len(players) < MIN_PLAYERS:
        return None
    code, label = _competition([*keywords, re.split(r'\s*\|\s*', headline)[0]])
    published = str(article.get('datePublished') or '')
    side = 'home' if home == 'Juventus' else 'away'
    return {
        'id': re.sub(r'[^\w\-]+', '-', url.rstrip('/').rsplit('/', 1)[-1]),
        'url': url,
        'title': headline,
        'published': published,
        'date': _rome_day(published),
        'competition': code,
        'competition_label': label,
        'home': home,
        'away': away,
        'side': side,
        'opponent': away if side == 'home' else home,
        'players': players,
    }


def _article(url):
    now = time.time()
    with _lock:
        hit = _article_cache.get(url)
        if hit and now - hit[0] < ARTICLE_CACHE_SECONDS:
            return hit[1]
    item = parse_article(_get(url), url)
    with _lock:
        _article_cache[url] = (now, item)
    return item


def _links(page):
    """Link agli articoli \"convocati\" in una pagina elenco (anche dentro JSON con \\/ e &amp;)."""
    text = html.unescape(page).replace('\\/', '/')
    found = {}
    for path in re.findall(r'(?:https://www\.juventus\.com)?(/it/news/articoli/[^"\'#?\s<>\\)]+)', text):
        path = path.rstrip('/')
        slug = path.rsplit('/', 1)[-1]
        if slug and 'convocat' in slug.lower():
            found[f'{BASE}{path}'] = True
    return list(found)


def discover():
    urls = {}
    errors = []
    for listing in LISTINGS:
        try:
            for url in _links(_get(listing)):
                urls[url] = True
        except ConvocatiError as exc:
            errors.append(str(exc))
    if not urls and errors:
        raise ConvocatiError(errors[0])
    return list(urls)[:MAX_CANDIDATES]


def fetch(url=''):
    """Convocati della prima squadra, dal più recente. Con url: solo quell'articolo."""
    url = str(url or '').strip()
    if url:
        if not URL_OK.match(url):
            raise ConvocatiError('Il link deve essere un articolo di juventus.com.')
        item = _article(url)
        if not item:
            raise ConvocatiError('Articolo non valido: servono i convocati della prima squadra maschile.')
        return [item]
    now = time.time()
    with _lock:
        hit = _list_cache.get('all')
        if hit and now - hit[0] < LIST_CACHE_SECONDS:
            return hit[1]
    urls = discover()

    def safe(link):
        try:
            return _article(link)
        except ConvocatiError as exc:
            print(f'WARN IMAGEGEN: convocati {link}: {exc}', flush=True)
            return None

    with ThreadPoolExecutor(max_workers=6) as pool:
        items = [item for item in pool.map(safe, urls) if item]
    items.sort(key=lambda item: item['published'], reverse=True)
    items = items[:MAX_ITEMS]
    if not items:
        raise ConvocatiError('Nessun convocato della prima squadra trovato su juventus.com.')
    with _lock:
        _list_cache['all'] = (now, items)
    return items
