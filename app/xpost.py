"""CITAZIONE X: legge un post di X (Twitter) da FxTwitter, con VxTwitter di riserva: lo stesso
servizio pubblico per le anteprime dei post che usa già Notizie_JR, raggiungibile da GitHub.

Ritorna nome, @account, foto profilo, testo e foto del post (per i video l'anteprima).
Molti post di X non hanno foto: lo sfondo di riserva (canva/x_quote_bg.jpg) lo aggiunge il servizio.
"""
import html
import re
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlsplit

import requests

import log

UA = 'ImageGEN-JR/1.0 (anteprima post)'
HOSTS = {'x.com', 'www.x.com', 'mobile.x.com', 'twitter.com', 'www.twitter.com', 'mobile.twitter.com',
         'fxtwitter.com', 'vxtwitter.com', 'fixupx.com'}
APIS = ('https://api.fxtwitter.com/status/{}', 'https://api.vxtwitter.com/status/{}')
MAX_PHOTOS = 4
MAX_BYTES = 12 * 1024 * 1024


def is_x_url(url):
    url = str(url or '').strip()
    if not re.match(r'^https?://', url, re.I):
        url = 'https://' + url
    return urlsplit(url).hostname in HOSTS


def parse_url(url):
    """Numero del post da un link di X. ValueError se il link non va."""
    url = str(url or '').strip()
    if not re.match(r'^https?://', url, re.I):
        url = 'https://' + url
    parts = urlsplit(url)
    m = re.search(r'/status(?:es)?/(\d{5,25})', parts.path)
    if parts.hostname not in HOSTS or not m:
        raise ValueError('Incolla il link di un post di X (x.com/…/status/…).')
    return m.group(1)


def clean_text(text):
    """Testo del post senza i link t.co finali (foto, video) e con le entità HTML sciolte."""
    text = html.unescape(str(text or ''))
    text = re.sub(r'(?:\s*https?://t\.co/\S+)+\s*$', '', text)
    return text.strip()


def _get(session, url):
    try:
        r = session.get(url, headers={'User-Agent': UA}, timeout=25)
        return r if r.status_code == 200 else None
    except requests.RequestException:
        return None


def _download(session, url):
    r = _get(session, url)
    return r.content if r is not None and 0 < len(r.content) <= MAX_BYTES else None


def fetch(url, session=None):
    """{'code', 'user', 'handle', 'text', 'avatar': bytes|None, 'photos': [bytes]} del post."""
    code = parse_url(url)
    session = session or requests.Session()
    data = None
    for api in APIS:
        r = _get(session, api.format(code))
        if r is None:
            continue
        try:
            body = r.json()
        except ValueError:
            continue
        tweet = body.get('tweet') if isinstance(body.get('tweet'), dict) else body
        if isinstance(tweet, dict) and (tweet.get('text') is not None or tweet.get('media')):
            data = tweet
            break
    if not data:
        raise ValueError('Post di X non trovato (privato, cancellato o servizio non raggiungibile).')

    author = data.get('author') or {}
    media = data.get('media') or {}
    urls = [p.get('url') for p in (media.get('photos') or []) if p.get('url')]
    if not urls:     # formato VxTwitter
        urls = [m.get('url') for m in data.get('media_extended') or [] if m.get('type') == 'image']
    if not urls:     # solo video/gif: vale l'anteprima del video
        urls = [v.get('thumbnail_url') for v in (media.get('videos') or []) if v.get('thumbnail_url')]
        urls += [m.get('thumbnail_url') for m in data.get('media_extended') or [] if m.get('thumbnail_url')]
    full = []
    for u in urls[:MAX_PHOTOS]:
        if 'pbs.twimg.com/media/' in u and 'name=' not in u:
            u += ('&' if '?' in u else '?') + 'name=orig'
        full.append(u)
    avatar_url = str(author.get('avatar_url') or data.get('user_profile_image_url') or '')
    avatar_url = re.sub(r'_(normal|bigger|mini|\d+x\d+)(\.\w+)$', r'_400x400\2', avatar_url)
    with ThreadPoolExecutor(5) as pool:
        photos = [p for p in pool.map(lambda u: _download(session, u), full) if p]
        avatar = _download(session, avatar_url) if avatar_url.startswith('https://') else None
    user = str(author.get('name') or data.get('user_name') or '').strip()
    handle = str(author.get('screen_name') or data.get('user_screen_name') or '').strip()
    text = clean_text(data.get('text'))
    log.info('X', f"Post {code} di @{handle or '?'}: {len(photos)} foto, testo {len(text)} caratteri, "
                  f"foto profilo {'sì' if avatar else 'no'}")
    return {'code': code, 'user': user, 'handle': handle, 'text': text, 'avatar': avatar, 'photos': photos}
