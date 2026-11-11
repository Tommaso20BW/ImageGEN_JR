"""Emoji personalizzate delle squadre, per le didascalie e Impostazioni › Emoji squadre.

Tutto nella cartella degli asset (repo LiveScore_Assets_JR):
  team_emoji/auto.json       scelta automatica (la aggiorna a ogni stagione tools/emoji_squadre.py)
  team_emoji/packs.json      emoji di ogni pack, in ordine; packs/<pack>.webp le miniature
  team_overrides/emoji.json  scelte fatte a mano in Impostazioni (vincono sulla automatica)
Chiave della squadra: slug FCLogo, oppure la chiave new:... delle squadre aggiunte da te.
"""
import base64
import io
import json
import os
import threading
from pathlib import Path

AUTO = 'team_emoji/auto.json'
PACKS = 'team_emoji/packs.json'
MANUAL = 'team_overrides/emoji.json'
_lock = threading.Lock()


def _assets():
    from graphics.common import asset_dir
    return Path(asset_dir())


def _read(path, default):
    try:
        return json.loads(Path(path).read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return default


def _norm(name):
    return ' '.join(str(name or '').casefold().split())


def auto_rows(assets=None):
    return _read((assets or _assets()) / AUTO, {}).get('teams') or {}


def manual_rows(assets=None):
    return _read((assets or _assets()) / MANUAL, {}).get('teams') or {}


def key_of(team):
    return str(team.get('slug') or team.get('override_key') or team.get('key') or '')


def current(team, assets=None, auto=None, manual=None):
    """Riga in uso per la squadra: {'id', 'emoji', 'pack', 'index', 'manual'} oppure None."""
    if not isinstance(team, dict):
        return None
    assets = assets or _assets()
    auto = auto_rows(assets) if auto is None else auto
    manual = manual_rows(assets) if manual is None else manual
    key = key_of(team)
    if not key or (key not in auto and key not in manual):
        names = {_norm(n) for n in [team.get('name'), team.get('display_name'), *(team.get('aliases') or [])] if n}
        key = next((k for k, r in auto.items() if names & {_norm(n) for n in [r.get('name'), *(r.get('aliases') or [])]}), '')
    if key in manual:
        row = manual[key]
        return None if row.get('none') or not row.get('id') else {**row, 'manual': True}
    row = auto.get(key)
    return {**row, 'manual': False} if row and row.get('id') else None


def find(team, assets=None):
    """(id, simbolo di riserva) dell'emoji della squadra, oppure None (nel testo resta 🆚)."""
    try:
        row = current(team, assets)
    except Exception:
        return None
    return (str(row['id']), row.get('emoji') or '🆚') if row else None


# ---------- Impostazioni › Emoji squadre ----------

def packs_info(assets=None):
    return _read((assets or _assets()) / PACKS, {})


def _thumb(assets, info, pack, index):
    """Miniatura 64 px (data URI PNG) di una emoji, ritagliata dalla griglia del pack."""
    from PIL import Image
    meta = info.get(pack) or {}
    pos = next((n for n, e in enumerate(meta.get('items', [])) if e.get('index') == index), None)
    if pos is None:
        return ''
    cell, cols = int(meta.get('cell', 64)), int(meta.get('cols', 12))
    try:
        sheet = Image.open(Path(assets) / 'team_emoji' / meta['file'])
    except (OSError, KeyError):
        return ''
    x, y = (pos % cols) * cell, (pos // cols) * cell
    out = io.BytesIO()
    sheet.crop((x, y, x + cell, y + cell)).save(out, 'PNG', optimize=True)
    return 'data:image/png;base64,' + base64.b64encode(out.getvalue()).decode('ascii')


def settings_list(teams, assets=None):
    """Pack (in ordine) e squadre del catalogo con l'emoji in uso e la sua miniatura."""
    assets = assets or _assets()
    info = packs_info(assets)
    packs = [{'pack': p, 'name': m.get('name') or p, 'count': len(m.get('items', []))} for p, m in info.items()]
    autos, manual = auto_rows(assets), manual_rows(assets)
    out = []
    for team in teams:
        key = key_of(team)
        if not key:
            continue
        row = current(team, assets, autos, manual)
        auto = autos.get(key) or {}
        out.append({'key': key, 'name': team.get('name'), 'display_name': team.get('display_name'),
                    'pack': row and row.get('pack'), 'index': row and row.get('index'),
                    'manual': key in manual,
                    'thumb': _thumb(assets, info, row['pack'], row.get('index')) if row else '',
                    'auto': {'pack': auto.get('pack'), 'index': auto.get('index')} if auto.get('id') else None})
    return {'packs': packs, 'teams': out}


def pack_sheet(pack, assets=None):
    """Griglia del pack per il selettore: immagine (data URI) e emoji in ordine."""
    assets = assets or _assets()
    meta = packs_info(assets).get(pack)
    if not meta:
        raise ValueError('Pack non trovato.')
    raw = (Path(assets) / 'team_emoji' / meta['file']).read_bytes()
    return {'pack': pack, 'name': meta.get('name') or pack, 'cell': meta.get('cell', 64), 'cols': meta.get('cols', 12),
            'items': [{'index': e.get('index')} for e in meta.get('items', [])],
            'sprite': 'data:image/webp;base64,' + base64.b64encode(raw).decode('ascii')}


def save(request, assets=None, env=None):
    """{key, name, pack, index} = emoji scelta; {key, none: true} = 🆚; {key, reset: true} = automatica.
    Salva in team_overrides/emoji.json (copia locale subito, poi un commit nel repo degli asset)."""
    import team_settings
    env = os.environ if env is None else env
    assets = assets or _assets()
    key = str(request.get('key') or '').strip()
    if not key:
        raise ValueError('Squadra mancante.')
    with _lock:
        rows = dict(manual_rows(assets))
        if request.get('reset'):
            rows.pop(key, None)
        elif request.get('none'):
            rows[key] = {'name': str(request.get('name') or ''), 'none': True}
        else:
            pack, index = str(request.get('pack') or ''), request.get('index')
            item = next((e for e in (packs_info(assets).get(pack) or {}).get('items', []) if e.get('index') == index), None)
            if not item:
                raise ValueError('Emoji non trovata nel pack.')
            rows[key] = {'name': str(request.get('name') or ''), 'id': item['id'], 'emoji': item.get('emoji') or '',
                         'pack': pack, 'index': index}
        text = json.dumps({'version': 1, 'teams': dict(sorted(rows.items()))}, ensure_ascii=False, indent=1) + '\n'
        path = Path(assets) / MANUAL
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding='utf-8')
        label = request.get('name') or key
        ok, why = team_settings._commit({MANUAL: text.encode('utf-8')}, f'Emoji squadre: {label} (mini app ImageGen)', env)
    return {'remote': ok, 'warning': '' if ok else why}
