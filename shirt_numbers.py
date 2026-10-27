"""Numeri di maglia ricordati nel repository (data/shirt_numbers.json).

Quando si invia una Starting XI, i numeri nuovi o cambiati vengono salvati con
un commit nel repository ImageGEN_JR (API GitHub, token del workflow
passato come IMAGEGEN_GH_PAT; serve contents: write in imagegen.yml).
"""
import base64
import json
import os
import threading
from pathlib import Path

import requests

PATH = 'data/shirt_numbers.json'
LOCAL = Path(__file__).parent / PATH
_lock = threading.Lock()


def load():
    data = json.loads(LOCAL.read_text(encoding='utf-8'))
    return {k: v for k, v in data.items() if not k.startswith('_')}


def slug_of(name):
    """Chiave per chi non è nella rosa: come slugOf nella Mini App ("Kenan Yıldız" -> "kenan_yildiz")."""
    import re
    import unicodedata
    text = str(name).lower()
    for a, b in (('ı', 'i'), ('ł', 'l'), ('đ', 'd'), ('ð', 'd'), ('þ', 'th'), ('ø', 'o'),
                 ('æ', 'ae'), ('œ', 'oe'), ('ß', 'ss')):
        text = text.replace(a, b)
    text = ''.join(c for c in unicodedata.normalize('NFKD', text) if not unicodedata.combining(c))
    return '_'.join(re.sub(r'[^a-z0-9]+', ' ', text).split())


def changes(lineup, players, known):
    """{slug: numero} dei giocatori della formazione con numero nuovo o diverso
    (anche quelli fuori rosa, con la chiave del nome scritto)."""
    by_name = {p.name: p.slug for p in players}
    out = {}
    for number, name in lineup:
        slug = by_name.get(name) or slug_of(name)
        if slug and str(number).isdigit() and known.get(slug) != int(number):
            out[slug] = int(number)
    return out


def save(updates, env=None, session=None):
    """Aggiorna il file nel repository (e la copia locale). Ritorna True se salvato."""
    if not updates:
        return False
    env = os.environ if env is None else env
    token, repo = env.get('IMAGEGEN_GH_PAT', '').strip(), env.get('GITHUB_REPOSITORY', '').strip()
    with _lock:
        data = json.loads(LOCAL.read_text(encoding='utf-8'))
        data.update(updates)
        text = json.dumps(data, ensure_ascii=False, indent=1) + '\n'
        LOCAL.write_text(text, encoding='utf-8')
        if not token or not repo:
            print('WARN IMAGEGEN: numeri di maglia salvati solo per questa sessione (token mancante)', flush=True)
            return False
        http = session or requests
        headers = {'Authorization': f'Bearer {token}', 'Accept': 'application/vnd.github+json',
                   'X-GitHub-Api-Version': '2022-11-28'}
        url = f'https://api.github.com/repos/{repo}/contents/{PATH}'
        for _attempt in range(2):
            current = http.get(url, headers=headers, params={'ref': 'main'}, timeout=20)
            if current.status_code != 200:
                print(f'WARN IMAGEGEN: numeri di maglia non salvati (lettura HTTP {current.status_code})', flush=True)
                return False
            remote = json.loads(base64.b64decode(current.json()['content']).decode('utf-8'))
            remote.update(updates)
            body = {
                'message': 'Numeri di maglia: ' + ', '.join(f'{k} {v}' for k, v in sorted(updates.items())),
                'content': base64.b64encode((json.dumps(remote, ensure_ascii=False, indent=1) + '\n').encode()).decode(),
                'sha': current.json()['sha'],
                'branch': 'main',
            }
            put = http.put(url, headers=headers, json=body, timeout=20)
            if put.status_code in (200, 201):
                print(f'INFO IMAGEGEN: numeri di maglia salvati nel repository | {updates}', flush=True)
                return True
            if put.status_code != 409:              # 409 = file cambiato nel frattempo: riprova
                break
        print(f'WARN IMAGEGEN: numeri di maglia non salvati (scrittura HTTP {put.status_code}); '
              'serve contents: write nel workflow imagegen.yml', flush=True)
        return False
