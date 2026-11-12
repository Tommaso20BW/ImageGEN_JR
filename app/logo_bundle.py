"""Prepara, dentro il workflow, il catalogo squadre con i loghi già incorporati.

Ogni run costruisce un pacchetto fresco (manifest + loghi ridotti come data URI)
che la Mini App scarica una sola volta dal tunnel del workflow: nessuna cache
vecchia e nessun caricamento di immagini esterne mentre si usa l'app.
"""
import log
import base64
import io
import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import requests
from PIL import Image

from livescore.graphics import goal as g

# Numeri di maglia per la Starting XI (la Mini App li propone in automatico).
from shirt_numbers import load as _load_shirts

SHIRT_NUMBERS = _load_shirts()
from name_splits import load as _load_splits
NAME_SPLITS = _load_splits()                # convocati: parole del nome (data/name_splits.json)

LOGO_SIZE = 96
MANIFEST_RELATIVE = Path('data/fclogo_manifest.json')


def _core_root():
    # .../_graphics_core/livescore/graphics/goal.py -> .../_graphics_core
    return Path(g.__file__).resolve().parents[2]


def _find_manifest():
    path = _core_root() / MANIFEST_RELATIVE
    if not path.is_file():
        raise FileNotFoundError(f'Manifest loghi non trovato: {path}')
    return path


def _local_logo(assets, team):
    for name in [team.get('file'), *(team.get('files') or [])]:
        if not name:
            continue
        for base in ('team_logos', 'team_logos/fclogo_cache'):
            path = assets / base / name
            if path.is_file():
                return path.read_bytes()
    return None


def _remote_logo(team):
    url = team.get('source_url')
    if not url:
        return None
    try:
        response = requests.get(url, timeout=12)
        response.raise_for_status()
        return response.content
    except requests.RequestException:
        return None


def _to_data_uri(raw):
    image = Image.open(io.BytesIO(raw)).convert('RGBA')
    image.thumbnail((LOGO_SIZE, LOGO_SIZE), Image.LANCZOS)
    out = io.BytesIO()
    image.save(out, format='PNG', optimize=True)
    return 'data:image/png;base64,' + base64.b64encode(out.getvalue()).decode('ascii')


def _prepare(assets, team):
    row = dict(team)
    custom = row.pop('custom_logo', None)
    try:
        raw = None if row.get('manual') else (_local_logo(assets, team) or _remote_logo(team))
        if raw:
            row['logo'] = _to_data_uri(raw)
        if custom:
            # Logo caricato in Impostazioni: prende il posto di FCLogo, che resta per "Torna a fclogo".
            row['logo_fclogo'] = row.get('logo')
            row['logo'] = _to_data_uri(Path(custom).read_bytes())
            row['logo_custom'] = True
    except Exception as exc:  # un logo rotto non deve bloccare il workflow
        log.warn('AVVIO', f'Logo non preparato per {team.get("name")}: {exc}')
    return row


def _players(assets=g.DEFAULT_ASSET_DIR):
    """Rosa dal motore grafico, nello stesso formato letto dalla Mini App.

    'poses' dice, maglia per maglia, quali pose hanno il PNG: la Mini App mostra solo quelle.
    """
    rows = []
    for player in g.load_players():
        rows.append({
            'name': player.name,
            'aliases': list(getattr(player, 'aliases', None) or []),
            'role': getattr(player, 'role', None),
            'slug': player.slug,
            'number': SHIRT_NUMBERS.get(player.slug),
            'poses': {kit: list(g.available_poses(player, kit, assets) or ())
                      for kit in ('home', 'away', 'third')},
        })
    rows.sort(key=lambda row: row['name'].casefold())
    return rows


def build_team_bundle(assets=g.DEFAULT_ASSET_DIR):
    assets = Path(assets)
    manifest = json.loads(_find_manifest().read_text(encoding='utf-8'))
    teams = manifest.get('teams', [])
    try:   # correzioni di Impostazioni › Squadre e loghi
        from livescore.core import team_overrides
        teams = team_overrides.apply(teams, assets)
    except ImportError:
        pass
    with ThreadPoolExecutor(max_workers=8) as pool:
        rows = list(pool.map(lambda team: _prepare(assets, team), teams))
    ready = sum(1 for row in rows if row.get('logo'))
    log.info('AVVIO', f'Loghi incorporati: {ready}/{len(rows)}')
    try:
        players = _players(assets)
    except Exception as exc:  # la Mini App ripiega sul download da GitHub
        log.warn('AVVIO', f'Calciatori non preparati: {exc}')
        players = []
    log.info('AVVIO', f'Calciatori nel pacchetto: {len(players)}')
    return json.dumps(
        {**manifest, 'teams': rows, 'players': players, 'shirts': dict(SHIRT_NUMBERS),
         'name_splits': dict(NAME_SPLITS)}, ensure_ascii=False
    ).encode('utf-8')
