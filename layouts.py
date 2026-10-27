"""PROBABILE XI: posizioni e grandezza delle card scelte con "Modifica", per modulo.

Salvate per sempre nel repository (data/probabili_layouts.json) con un commit via
API GitHub, come i numeri di maglia (token IMAGEGEN_GH_PAT, Contents read/write).
Un modulo mai modificato usa le posizioni Canva di graphics/probabili.py.
"""
import base64
import json
import math
import os
import threading
from pathlib import Path

import requests

PATH = 'data/probabili_layouts.json'
LOCAL = Path(__file__).parent / PATH
SCALE_MIN, SCALE_MAX = 0.7, 1.3
_lock = threading.Lock()


def _read():
    try:
        data = json.loads(LOCAL.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return {}
    return {k: v for k, v in data.items() if not k.startswith('_') and isinstance(v, dict)}


def clean(module, value):
    """{'cards': [[x, alto], ...11], 'scale': s} validato, o ValueError."""
    from graphics.probabili import MODULES
    from graphics.common import DESIGN_H, DESIGN_W

    if module not in MODULES:
        raise ValueError('Modulo non valido.')
    if not isinstance(value, dict):
        raise ValueError('Posizioni non valide.')
    cards = value.get('cards')
    if not isinstance(cards, list) or len(cards) != 11:
        raise ValueError('Servono 11 posizioni.')
    out = []
    for card in cards:
        try:
            x, top = float(card[0]), float(card[1])
        except (TypeError, ValueError, IndexError, KeyError):
            raise ValueError('Posizione non valida.') from None
        if not (math.isfinite(x) and math.isfinite(top) and 0 <= x <= DESIGN_W and 0 <= top <= DESIGN_H):
            raise ValueError('Posizione fuori dalla grafica.')
        out.append([round(x, 2), round(top, 2)])
    try:
        scale = float(value.get('scale', 1))
    except (TypeError, ValueError):
        raise ValueError('Grandezza non valida.') from None
    if not math.isfinite(scale):
        raise ValueError('Grandezza non valida.')
    return {'cards': out, 'scale': round(max(SCALE_MIN, min(SCALE_MAX, scale)), 2)}


def default(module):
    from graphics.probabili import MODULE_SCALE, MODULES
    return {'cards': [list(c) for c in MODULES[module]], 'scale': MODULE_SCALE.get(module, 1.0)}


def get(module):
    """Disposizione in uso: quella salvata o quella Canva."""
    saved = _read().get(module)
    if saved:
        try:
            return clean(module, saved)
        except ValueError:
            pass
    return default(module)


def all_layouts():
    from graphics.probabili import MODULES
    return {module: get(module) for module in MODULES}


def save(module, layout, env=None, session=None):
    """Salva la disposizione (copia locale subito, repository via API). True se nel repository."""
    layout = clean(module, layout)
    env = os.environ if env is None else env
    token, repo = env.get('IMAGEGEN_GH_PAT', '').strip(), env.get('GITHUB_REPOSITORY', '').strip()
    with _lock:
        data = _read()
        if data.get(module) == layout:
            return True
        data[module] = layout
        LOCAL.parent.mkdir(parents=True, exist_ok=True)
        LOCAL.write_text(_dump(data), encoding='utf-8')
        if not token or not repo:
            print('WARN IMAGEGEN: posizioni salvate solo per questa sessione (token mancante)', flush=True)
            return False
        http = session or requests
        headers = {'Authorization': f'Bearer {token}', 'Accept': 'application/vnd.github+json',
                   'X-GitHub-Api-Version': '2022-11-28'}
        url = f'https://api.github.com/repos/{repo}/contents/{PATH}'
        status = None
        for _attempt in range(2):
            current = http.get(url, headers=headers, params={'ref': 'main'}, timeout=20)
            if current.status_code == 200:
                remote = json.loads(base64.b64decode(current.json()['content']).decode('utf-8'))
                sha = current.json()['sha']
            elif current.status_code == 404:          # primo salvataggio: il file non c'è ancora
                remote, sha = {}, None
            else:
                print(f'WARN IMAGEGEN: posizioni non salvate (lettura HTTP {current.status_code})', flush=True)
                return False
            remote[module] = layout
            body = {
                'message': f'Probabile XI: posizioni {module} ({round(layout["scale"] * 100)}%)',
                'content': base64.b64encode(_dump(remote).encode()).decode(),
                'branch': 'main',
            }
            if sha:
                body['sha'] = sha
            put = http.put(url, headers=headers, json=body, timeout=20)
            status = put.status_code
            if status in (200, 201):
                print(f'INFO IMAGEGEN: posizioni {module} salvate nel repository', flush=True)
                return True
            if status not in (409, 422):              # file cambiato nel frattempo: riprova
                break
        print(f'WARN IMAGEGEN: posizioni non salvate (scrittura HTTP {status}); '
              'serve il permesso Contents read/write su IMAGEGEN_GH_PAT', flush=True)
        return False


def _dump(data):
    lines = ['{']
    items = sorted(data.items())
    for i, (module, layout) in enumerate(items):
        comma = ',' if i < len(items) - 1 else ''
        lines.append(f' {json.dumps(module)}: {json.dumps(layout, separators=(", ", ": "))}{comma}')
    lines.append('}')
    return '\n'.join(lines) + '\n'
