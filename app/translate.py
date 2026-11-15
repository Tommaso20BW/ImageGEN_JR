"""Citazioni IG / X / Threads: traduzione veloce del testo in italiano (Google Traduttore, senza chiave)."""
from __future__ import annotations

import requests

URL = 'https://translate.googleapis.com/translate_a/single'
URL_CHROME = 'https://clients5.google.com/translate_a/t'
MAX_CHARS = 4000


def to_italian(text: str, session=None) -> dict:
    """{'text': testo tradotto, 'source': lingua di partenza}. Gli a-capo restano."""
    text = str(text or '').strip()
    if not text:
        raise ValueError('Nessun testo da tradurre.')
    if len(text) > MAX_CHARS:
        raise ValueError('Testo troppo lungo da tradurre.')
    session = session or requests.Session()
    # Due indirizzi di Google Traduttore: se il primo risponde "troppe richieste" si prova l'altro.
    for attempt in (_gtx, _chrome):
        try:
            out, source = attempt(session, text)
        except (requests.RequestException, ValueError, LookupError, TypeError):
            continue
        if out.strip():
            return {'text': out.strip(), 'source': source}
    raise ValueError('Traduttore non disponibile. Riprova tra poco.')


def _gtx(session, text):
    r = session.get(URL, params={'client': 'gtx', 'sl': 'auto', 'tl': 'it', 'dt': 't', 'q': text}, timeout=15)
    r.raise_for_status()
    data = r.json()
    out = ''.join(part[0] for part in (data[0] or []) if part and part[0])
    return out, data[2] if len(data) > 2 and isinstance(data[2], str) else ''


def _chrome(session, text):
    r = session.get(URL_CHROME, params={'client': 'dict-chrome-ex', 'sl': 'auto', 'tl': 'it', 'q': text}, timeout=15)
    r.raise_for_status()
    data = r.json()
    first = data[0]
    return (first[0], first[1]) if isinstance(first, list) else (first, '')
