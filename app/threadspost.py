"""CITAZIONE THREADS: legge un post pubblico di Threads, come la Citazione X / IG.

- link: threads.com o threads.net, sia /@account/post/CODICE sia i link di condivisione /share/…
  (si segue il rimando fino al post);
- testo, foto del post, foto profilo piccola e spunta blu: dalla pagina embed ufficiale del post
  (…/post/CODICE/embed, quella che Threads dà per incorporare i post nei siti);
- nome completo: dal titolo della pagina del post ("Nome (@account) on Threads");
- foto profilo grande: dalla pagina pubblica del profilo (og:image), se c'è.
Nessun login: solo pagine pubbliche, con il nostro nome client.
"""
import html
import re
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlsplit

import requests

import log

UA = 'ImageGEN-JR/1.0 (anteprima post)'
HOSTS = {'threads.com', 'www.threads.com', 'threads.net', 'www.threads.net'}
BASE = 'https://www.threads.com'
POST_RE = re.compile(r'^/@([\w.]+)/post/([\w-]+)')
MAX_PHOTOS = 4
MAX_BYTES = 12 * 1024 * 1024


def _norm(url):
    url = str(url or '').strip()
    return url if re.match(r'^https?://', url, re.I) else 'https://' + url


def is_threads_url(url):
    return urlsplit(_norm(url)).hostname in HOSTS


def _get(session, url):
    try:
        r = session.get(url, headers={'User-Agent': UA}, timeout=25, allow_redirects=True)
        return r if r.status_code == 200 else None
    except requests.RequestException:
        return None


def _download(session, url):
    r = _get(session, url)
    return r.content if r is not None and 0 < len(r.content) <= MAX_BYTES else None


def _meta(page, prop):
    m = re.search(r'<meta[^>]+property="%s"[^>]+content="([^"]*)"' % re.escape(prop), page)
    return html.unescape(m.group(1)) if m else ''


def _text(fragment):
    """HTML del testo del post -> testo semplice con gli a-capo."""
    t = re.sub(r'<br\s*/?>', '\n', fragment, flags=re.I)
    t = re.sub(r'<[^>]+>', '', t)
    return html.unescape(t).strip()


def resolve(url, session):
    """(account, codice, pagina del post): segue i link di condivisione fino al post."""
    url = _norm(url)
    if urlsplit(url).hostname not in HOSTS:
        raise ValueError('Incolla il link di un post di Threads (threads.com/@…/post/…).')
    m = POST_RE.match(urlsplit(url).path)
    page = None
    if not m:                                   # /share/… o altro: si segue il rimando
        r = _get(session, url)
        if r is None:
            raise ValueError('Post di Threads non raggiungibile.')
        m = POST_RE.match(urlsplit(r.url).path)
        page = r.text
    if not m:
        raise ValueError('Incolla il link di un post di Threads (threads.com/@…/post/…).')
    return m.group(1), m.group(2), page


def fetch(url, session=None):
    """{'code', 'user', 'handle', 'verified', 'text', 'avatar': bytes|None, 'photos': [bytes]}."""
    session = session or requests.Session()
    handle, code, page = resolve(url, session)
    post_url = f'{BASE}/@{handle}/post/{code}'
    with ThreadPoolExecutor(3) as pool:
        embed_f = pool.submit(_get, session, post_url + '/embed')
        page_f = pool.submit(_get, session, post_url) if page is None else None
        profile_f = pool.submit(_get, session, f'{BASE}/@{handle}')
        embed = embed_f.result()
        page = page if page is not None else (page_f.result().text if page_f.result() is not None else '')
        profile = profile_f.result()
    if embed is None:
        raise ValueError('Post di Threads non trovato (privato, cancellato o non raggiungibile).')
    e = embed.text
    # testo: <span class="BodyTextContainer"><span>…</span></span>
    m = re.search(r'class="BodyTextContainer"><span>(.*?)</span></span>', e, re.S)
    text = _text(m.group(1)) if m else ''
    # foto del post (l'immagine piccola dell'intestazione è la foto profilo)
    media = re.findall(r'class="MediaScrollImageContainer"><img[^>]+src="([^"]+)"', e)
    if not media:
        single = re.search(r'class="(?:SingleInnerMediaContainer|MediaContainer)[^"]*">\s*(?:<[^>]+>\s*)*<img[^>]+src="([^"]+)"', e)
        media = [single.group(1)] if single else []
    media = [html.unescape(u) for u in media][:MAX_PHOTOS]
    small_avatar = re.search(r'class="AvatarContainer".*?<img[^>]+src="([^"]+)"', e, re.S)
    verified = 'class="VerifiedBadge"' in e
    # nome completo: "Alessandro Del Piero (@alessandrodelpiero) on Threads"
    title = _meta(page, 'og:title')
    nm = re.match(r'^(.*?)\s*\(@[\w.]+\)', title)
    user = nm.group(1).strip() if nm else handle
    avatar_url = _meta(profile.text, 'og:image') if profile is not None else ''
    if not avatar_url and small_avatar:
        avatar_url = html.unescape(small_avatar.group(1))
    with ThreadPoolExecutor(5) as pool:
        photos = [p for p in pool.map(lambda u: _download(session, u), media) if p]
        avatar = _download(session, avatar_url) if avatar_url.startswith('https://') else None
    log.info('THREADS', f"Post {code} di @{handle}: {len(photos)} foto, testo {len(text)} caratteri, "
                        f"foto profilo {'sì' if avatar else 'no'}")
    if not text and not photos:
        raise ValueError('Post di Threads vuoto o non leggibile.')
    return {'code': code, 'user': user, 'handle': handle, 'verified': verified, 'text': text,
            'avatar': avatar, 'photos': photos}
