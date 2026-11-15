"""Storia IG: ultimi post del canale Telegram (pagina pubblica t.me/s/<canale>) come testo della storia.

Il testo arriva già pulito come nelle altre grafiche: senza emoji, senza la firma
"👉 @Juventus_Reborn" e senza la riga della fonte ("📲 Nicolò Schira").
"""
from __future__ import annotations

import re
from html.parser import HTMLParser

import requests

CHANNEL = 'juventus_reborn'
PAGE = 'https://t.me/s/{channel}'
LIMIT = 20
_SOURCE = re.compile(r'^\s*📲')          # riga della fonte, prima di togliere gli emoji
_HASHTAGS = re.compile(r'^(?:#\w+\s*)+$')


class _Page(HTMLParser):
    """Post della pagina: id, data e testo (a-capo dai <br>)."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.posts, self._post, self._depth, self._text = [], None, 0, None

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        cls = a.get('class') or ''
        if tag == 'div' and a.get('data-post'):
            self._post = {'id': a['data-post'].rsplit('/', 1)[-1], 'date': '', 'text': ''}
            self.posts.append(self._post)
        elif tag == 'time' and self._post is not None and a.get('datetime') and not self._post['date']:
            self._post['date'] = a['datetime']
        if self._text is not None:
            if tag == 'div':
                self._depth += 1
            elif tag == 'br':
                self._text.append('\n')
        elif tag == 'div' and 'tgme_widget_message_text' in cls and self._post is not None:
            self._text, self._depth = [], 1

    def handle_startendtag(self, tag, attrs):
        if self._text is not None and tag == 'br':
            self._text.append('\n')
        else:
            self.handle_starttag(tag, attrs)

    def handle_endtag(self, tag):
        if self._text is not None and tag == 'div':
            self._depth -= 1
            if not self._depth:
                if not self._post['text']:
                    self._post['text'] = ''.join(self._text)
                self._text = None

    def handle_data(self, data):
        if self._text is not None:
            self._text.append(data)


def parse(page_html: str) -> list[dict]:
    p = _Page()
    p.feed(page_html)
    return [x for x in p.posts if x['text'].strip()]


def story_text(raw: str) -> str:
    """Testo per la storia: niente fonte, firma, hashtag finali ed emoji."""
    from graphics.ig_quote import tidy
    lines = [l for l in str(raw or '').replace('\r', '').split('\n') if not _SOURCE.match(l)]
    text = tidy('\n'.join(lines))
    lines = [l for l in text.split('\n') if not _HASHTAGS.match(l.strip())]
    return re.sub(r'\n{3,}', '\n\n', '\n'.join(lines)).strip()


def fetch(channel: str = CHANNEL, limit: int = LIMIT, session=None) -> list[dict]:
    """Ultimi `limit` post con testo, dal più recente."""
    session = session or requests.Session()
    url, posts, seen = PAGE.format(channel=channel), [], set()
    params = {}
    for _ in range(4):                         # una pagina ha ~20 post, non tutti con testo
        r = session.get(url, params=params, timeout=15, headers={'User-Agent': 'Mozilla/5.0'})
        r.raise_for_status()
        page = [p for p in parse(r.text) if p['id'] not in seen]
        if not page:
            break
        seen.update(p['id'] for p in page)
        posts = page + posts
        if len(posts) >= limit:
            break
        params = {'before': min(int(p['id']) for p in page)}
    posts.sort(key=lambda p: int(p['id']), reverse=True)
    out = []
    for p in posts:
        text = story_text(p['text'])
        if text:
            out.append({'id': p['id'], 'date': p['date'], 'text': text})
        if len(out) >= limit:
            break
    return out
