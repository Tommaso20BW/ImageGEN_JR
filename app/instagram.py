"""CITAZIONE IG: legge un post Instagram dalla sua pagina "embed" pubblica e ufficiale
(https://www.instagram.com/p/<codice>/embed/captioned/, quella che usano i siti per incorporare i post).

Ritorna testo del post, nome dell'account, foto profilo e le foto (tutte, se è un carosello).
Nessun mirror e nessun trucco: richiesta normale con un User-Agent che dice chi siamo. Se Instagram
non risponde o il post è privato, la Mini App lo dice e si può caricare la foto a mano.
"""
import html
import json
import re
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlsplit

import requests

import log

UA = 'ImageGEN-JR/1.0 (anteprima post)'
HOSTS = {'instagram.com', 'www.instagram.com', 'm.instagram.com', 'instagr.am'}
MAX_PHOTOS = 10
MAX_BYTES = 12 * 1024 * 1024
BS = chr(92)


def parse_url(url):
    """Codice del post da un link Instagram (post, reel, tv). ValueError se il link non va."""
    url = str(url or '').strip()
    if not re.match(r'^https?://', url, re.I):
        url = 'https://' + url
    parts = urlsplit(url)
    if parts.hostname not in HOSTS:
        raise ValueError('Incolla il link di un post Instagram (instagram.com/p/…).')
    m = re.match(r'^/(?:[\w.]+/)?(p|reel|reels|tv)/([A-Za-z0-9_-]{5,})', parts.path)
    if not m:
        raise ValueError('Link non valido: serve il link di un post (instagram.com/p/…).')
    return m.group(2)


def _json_str(raw):
    """Stringa JSON annidata (anche doppia) -> testo."""
    value = raw
    for _ in range(3):
        if BS not in value:
            break
        value = json.loads('"' + value + '"')
    return value


def parse_embed(page):
    """Dati dal codice della pagina embed."""
    user = re.search(r'class="UsernameText"[^>]*>([^<]+)', page)
    avatar = re.search(r'class="Avatar[^"]*"[^>]*>.{0,400}?src="([^"]+)"', page, re.S)
    text = ''
    start = page.find('class="Caption"')
    if start >= 0:
        # Dentro la didascalia ci sono solo <a> (nome, menzioni, hashtag) e <br>: finisce al primo
        # <div> o </div> (commenti "View all…" o, se mancano, il piè di pagina "Add a comment...").
        block = page[start:].split('>', 1)[-1]
        end = min([i for i in (block.find('<div'), block.find('</div')) if i >= 0] or [len(block)])
        block = re.sub(r'<br\s*/?>', '\n', block[:end])
        block = re.sub(r'<a [^>]*class="CaptionUsername"[^>]*>.*?</a>', '', block, flags=re.S)
        text = html.unescape(re.sub(r'<[^>]+>', '', block)).strip()
    photos = []
    for raw in re.findall('display_url' + BS * 3 + '":' + BS * 3 + '"(.*?)' + BS * 3 + '"', page):
        try:
            url = _json_str(raw)
        except ValueError:
            continue
        if url.startswith('https://') and url not in photos:
            photos.append(url)
    if not photos:      # post con una foto sola: niente JSON, c'è l'immagine nella pagina
        photos = [html.unescape(u) for u in re.findall(r'class="EmbeddedMediaImage"[^>]+src="([^"]+)"', page)]
    if not photos:
        # Video (reel): l'anteprima del video fa da foto. Copertina del <video>, miniatura nel JSON
        # o immagine dentro il riquadro del post, in quest'ordine.
        found = [html.unescape(u) for u in re.findall(r'<video[^>]+poster="([^"]+)"', page)]
        for key in ('thumbnail_src', 'thumbnail_url', 'cover_frame_url'):
            for raw in re.findall(key + BS * 3 + '":' + BS * 3 + '"(.*?)' + BS * 3 + '"', page):
                try:
                    found.append(_json_str(raw))
                except ValueError:
                    pass
        found += [html.unescape(u) for u in re.findall(
            r'class="EmbeddedMedia[^"]*"[^>]*>(?:\s*<[^>]+>){0,6}?\s*<img[^>]+src="([^"]+)"', page)]
        for url in found:
            if url.startswith('https://') and url not in photos:
                photos.append(url)
    # Il carosello ha prima il "padre" (uguale alla prima foto) e poi le foto: i doppioni sono già tolti.
    return {
        'user': html.unescape(user.group(1)).strip() if user else '',
        'avatar_url': html.unescape(avatar.group(1)) if avatar else '',
        'text': text,
        'photos': photos[:MAX_PHOTOS],
    }


def tidy_text(text):
    """Testo per la citazione: via le righe finali fatte solo di hashtag/menzioni e gli
    hashtag attaccati in fondo all'ultima riga."""
    lines = [line.rstrip() for line in str(text or '').replace('\r', '').split('\n')]
    tag = re.compile(r'^(?:[#@][\w.]+[\s,.]*)+$', re.U)
    while lines and (not lines[-1].strip() or tag.match(lines[-1].strip())):
        lines.pop()
    if lines:
        lines[-1] = re.sub(r'(?:\s+[#@][\w.]+)+\s*$', '', lines[-1])
    return '\n'.join(lines).strip()


def _download(session, url):
    try:
        r = session.get(url, headers={'User-Agent': UA}, timeout=25)
        if r.status_code == 200 and 0 < len(r.content) <= MAX_BYTES:
            return r.content
    except requests.RequestException:
        pass
    return None


def fetch(url, session=None):
    """{'code', 'user', 'text', 'avatar': bytes|None, 'photos': [bytes]} del post."""
    code = parse_url(url)
    session = session or requests.Session()
    try:
        r = session.get(f'https://www.instagram.com/p/{code}/embed/captioned/',
                        headers={'User-Agent': UA}, timeout=25)
    except requests.RequestException:
        raise ValueError('Instagram non risponde. Riprova o carica la foto a mano.') from None
    if r.status_code != 200:
        raise ValueError(f'Instagram non ha dato il post (HTTP {r.status_code}). Carica la foto a mano.')
    data = parse_embed(r.text)
    if not data['photos']:
        raise ValueError('Nel post non ci sono foto né anteprime video leggibili (post privato?).')
    with ThreadPoolExecutor(6) as pool:
        photos = [p for p in pool.map(lambda u: _download(session, u), data['photos']) if p]
        avatar = _download(session, data['avatar_url']) if data['avatar_url'] else None
    if not photos:
        raise ValueError('Foto del post non scaricabili. Carica la foto a mano.')
    log.info('INSTAGRAM', f"Post {code} di {data['user'] or '?'}: {len(photos)} foto, "
                          f"testo {len(data['text'])} caratteri, foto profilo {'sì' if avatar else 'no'}")
    return {'code': code, 'user': data['user'], 'text': tidy_text(data['text']), 'avatar': avatar,
            'photos': photos}
