"""PROBABILE XI: tutti i moduli (posizioni delle card, grandezza, etichette dei ruoli).

L'unica sorgente è data/probabili_layouts.json: contiene TUTTI i moduli, con le posizioni di
partenza già dentro. Quando modifichi un modulo (posizioni, grandezza, etichette) si aggiorna
il suo pezzo di file; puoi aggiungere moduli nuovi (+) o cancellare quelli che non usi.
Il salvataggio va nel repository con un commit via API GitHub (token del workflow,
contents: write in imagegen.yml), come i numeri di maglia.
"""
import base64
import json
import math
import os
import re
import threading
from pathlib import Path

import requests

PATH = 'data/probabili_layouts.json'
LOCAL = Path(__file__).parent / PATH
SCALE_MIN, SCALE_MAX = 0.7, 1.3
ROLE_MAX = 5                       # lunghezza massima di un'etichetta (POR, DC, TRQ...)
_lock = threading.Lock()


def _read():
    try:
        data = json.loads(LOCAL.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return {}
    return {k: v for k, v in data.items() if not k.startswith('_') and isinstance(v, dict)}


def sizes(module):
    """[4, 3, 3] da '4-3-3', o None se il nome non è un modulo (10 giocatori di movimento)."""
    if not isinstance(module, str) or not re.fullmatch(r'[1-9](-[1-9]){1,5}', module):
        return None
    parts = [int(n) for n in module.split('-')]
    return parts if sum(parts) == 10 else None


def normalize_name(text):
    """'451', '4 5 1', '4-5-1' -> '4-5-1' (se è un modulo valido), altrimenti None."""
    digits = re.findall(r'\d', str(text or ''))
    name = '-'.join(digits)
    return name if sizes(name) else None


# ---------- disposizione automatica (moduli nuovi) ----------
_X = {1: [540.0], 2: [306.01, 773.99], 3: [225.0, 540.0, 855.0], 4: [123.53, 384.53, 695.47, 956.47],
      5: [123.53, 340.0, 540.0, 740.0, 956.47], 6: [90.0, 270.0, 450.0, 630.0, 810.0, 990.0]}
_DEF = {3: ([225.0, 540.0, 851.77], [982.4] * 3),
        4: ([124.26, 401.5, 678.75, 955.74], [956.16, 991.04, 991.04, 956.16]),
        5: ([110.0, 325.0, 540.0, 755.0, 970.0], [930.0, 982.4, 982.4, 982.4, 930.0])}
_STAGGER = {4: [-13, 0, 0, -13], 5: [-70, 0, 70, 0, -70]}


def auto_roles(module):
    parts = sizes(module)
    roles = ['POR']
    for i, k in enumerate(parts):
        last, before_last = i == len(parts) - 1, i == len(parts) - 2   # (before_last: la fila prima dell'attacco)
        if i == 0:
            roles += {3: ['DC'] * 3, 4: ['TS', 'DC', 'DC', 'TD'], 5: ['TS', 'DC', 'DC', 'DC', 'TD']}.get(k, ['DC'] * k)
        elif last:
            roles += ['AS', 'ATT', 'AD'] if k == 3 else ['ATT'] * k
        elif k == 1:
            roles += ['TRQ' if before_last else 'CDC']
        elif k == 4:
            roles += ['ES', 'CC', 'CC', 'ED']
        elif k == 5:
            roles += ['ES', 'CC', 'CDC', 'CC', 'ED']
        else:
            roles += ['CC'] * k
    return roles[:11]


def auto_layout(module):
    """Una fila per reparto, spaziate in modo uguale dalla difesa all'attacco."""
    parts = sizes(module)
    if parts is None:
        raise ValueError('Modulo non valido.')
    cards = [[540.0, 1228.16]]
    n = len(parts)
    for i, k in enumerate(parts):
        y = 982.4 + (295.4 - 982.4) * i / (n - 1)
        if i == 0 and k in _DEF:
            xs, ys = _DEF[k]
        else:
            xs = _X.get(k, _X[6][:k])
            ys = [y + d for d in _STAGGER.get(k, [0] * k)] if i else [y] * k
        cards += [[x, round(yy, 2)] for x, yy in zip(xs, ys)]
    return {'cards': cards, 'scale': 0.9 if max(parts) >= 5 else 1.0, 'roles': auto_roles(module)}


# ---------- validazione ----------
def clean(module, value):
    """{'cards': [[x, alto], ...11], 'scale': s, 'roles': [11 etichette]} validato, o ValueError."""
    from graphics.common import DESIGN_H, DESIGN_W

    if sizes(module) is None:
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
    roles = value.get('roles')
    if isinstance(roles, list) and len(roles) == 11:
        roles = [str(r).strip().upper()[:ROLE_MAX] for r in roles]
    else:
        roles = auto_roles(module)
    return {'cards': out, 'scale': round(max(SCALE_MIN, min(SCALE_MAX, scale)), 2), 'roles': roles}


def modules():
    return list(_read())


def exists(module):
    return module in _read()


def get(module):
    """Disposizione in uso: quella nel file data (o, per un modulo mai salvato, quella automatica)."""
    saved = _read().get(module)
    if saved:
        try:
            return clean(module, saved)
        except ValueError:
            pass
    return auto_layout(module)


default = get


def all_layouts():
    return {module: get(module) for module in _read()}


# ---------- salvataggio ----------
def _persist(change, message, env=None, session=None):
    """Applica change(dict)->dict al file locale subito e al repository via API. True se nel repository."""
    env = os.environ if env is None else env
    token, repo = env.get('IMAGEGEN_GH_PAT', '').strip(), env.get('GITHUB_REPOSITORY', '').strip()
    with _lock:
        data = _read()
        new = change(dict(data))
        if new == data:
            return True
        LOCAL.parent.mkdir(parents=True, exist_ok=True)
        LOCAL.write_text(_dump(new), encoding='utf-8')
        if not token or not repo:
            print('WARN IMAGEGEN: moduli salvati solo per questa sessione (token mancante)', flush=True)
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
                print(f'WARN IMAGEGEN: moduli non salvati (lettura HTTP {current.status_code})', flush=True)
                return False
            body = {'message': message, 'content': base64.b64encode(_dump(change(remote)).encode()).decode(),
                    'branch': 'main'}
            if sha:
                body['sha'] = sha
            put = http.put(url, headers=headers, json=body, timeout=20)
            status = put.status_code
            if status in (200, 201):
                print(f'INFO IMAGEGEN: {message} (repository)', flush=True)
                return True
            if status not in (409, 422):              # file cambiato nel frattempo: riprova
                break
        print(f'WARN IMAGEGEN: moduli non salvati (scrittura HTTP {status}); '
              'serve contents: write nel workflow imagegen.yml', flush=True)
        return False


def save(module, layout, env=None, session=None):
    layout = clean(module, layout)
    return _persist(lambda d: {**d, module: layout},
                    f'Probabile XI: posizioni {module} ({round(layout["scale"] * 100)}%)', env, session)


def create(module, env=None, session=None):
    """Nuovo modulo con disposizione automatica. Ritorna la disposizione."""
    module = normalize_name(module)
    if not module:
        raise ValueError('Modulo non valido: servono 10 giocatori di movimento (es. 4-5-1).')
    if exists(module):
        raise ValueError(f'Il modulo {module} c\'è già.')
    layout = clean(module, auto_layout(module))
    _persist(lambda d: {**d, module: layout}, f'Probabile XI: nuovo modulo {module}', env, session)
    return module, layout


def delete(module, env=None, session=None):
    if not exists(module):
        raise ValueError('Modulo non trovato.')
    if len(_read()) <= 1:
        raise ValueError('Deve restare almeno un modulo.')
    _persist(lambda d: {k: v for k, v in d.items() if k != module}, f'Probabile XI: modulo {module} eliminato',
             env, session)


def _dump(data):
    lines = ['{']
    items = list(data.items())
    for i, (module, layout) in enumerate(items):
        comma = ',' if i < len(items) - 1 else ''
        lines.append(f' {json.dumps(module)}: {json.dumps(layout, separators=(", ", ": "))}{comma}')
    lines.append('}')
    return '\n'.join(lines) + '\n'
