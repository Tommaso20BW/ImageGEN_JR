"""Impostazioni › Squadre e loghi: salva le correzioni delle squadre.

Le correzioni stanno nel repo degli asset in team_overrides/ (formato e regole in
livescore/core/team_overrides.py), lette sia da ImageGen sia da LiveScore.
Ogni salvataggio:
  1. aggiorna subito la copia locale (l'app e le grafiche la usano da questo momento);
  2. pubblica overrides.json e i loghi nel repo degli asset con UN solo commit
     (API Git di GitHub, token IMAGEGEN_ASSETS_PAT): mai mezzi salvataggi.
"""
import base64
import hashlib
import io
import json
import os
import re
import threading
import unicodedata
from pathlib import Path

import requests
from PIL import Image

from livescore.core import team_overrides
from livescore.core.team_matching import normalize_team_name

ASSETS_REPO_DEFAULT = 'Tommaso20BW/LiveScore_Assets_JR'
LOGO_MAX = 512
MAX_ALIASES = 12
MAX_NAME = 40
_lock = threading.Lock()


# ---------- logo ----------
def make_mono(raw):
    """PNG caricato -> sagoma nera su trasparente (come i loghi FCLogo mono).

    - già mono (un solo colore con trasparenza): si tiene la trasparenza com'è;
    - a colori o su fondo bianco: diventano pieni i tratti scuri/colorati, il bianco
      sparisce (dentro lo stemma resta il disegno, come nelle versioni mono).
    """
    try:
        image = Image.open(io.BytesIO(raw))
        image.load()
    except Exception:
        raise ValueError('Logo non valido: usa un PNG (meglio con sfondo trasparente).') from None
    image = image.convert('RGBA')
    image.thumbnail((LOGO_MAX * 2, LOGO_MAX * 2), Image.LANCZOS)
    alpha = image.getchannel('A')
    small = image.copy()
    small.thumbnail((96, 96))
    pixels = list(small.getdata())
    visible = [p for p in pixels if p[3] > 40]
    if not visible:
        raise ValueError('Logo vuoto: l’immagine è tutta trasparente.')
    transparent = 1 - len(visible) / len(pixels)
    lum = sorted(0.299 * r + 0.587 * g + 0.114 * b for r, g, b, _a in visible)
    spread = lum[int(len(lum) * .95)] - lum[int(len(lum) * .05)]
    if transparent < 0.05 or spread > 60:
        # A colori o senza trasparenza: opaco dove è scuro/colorato, trasparente sul bianco.
        ink = image.convert('L').point(lambda v: 255 if v <= 170 else 0 if v >= 235 else int((235 - v) * 255 / 65))
        alpha = Image.composite(ink, Image.new('L', image.size, 0), alpha)
    bbox = alpha.getbbox()
    if not bbox:
        raise ValueError('Logo vuoto dopo la conversione: usa un PNG con sfondo trasparente.')
    alpha = alpha.crop(bbox)
    alpha.thumbnail((LOGO_MAX, LOGO_MAX), Image.LANCZOS)
    out = Image.new('RGBA', alpha.size, (0, 0, 0, 255))
    out.putalpha(alpha)
    buf = io.BytesIO()
    out.save(buf, format='PNG', optimize=True)
    return buf.getvalue()


def preview_uri(png, size=160):
    image = Image.open(io.BytesIO(png)).convert('RGBA')
    image.thumbnail((size, size), Image.LANCZOS)
    buf = io.BytesIO()
    image.save(buf, format='PNG', optimize=True)
    return 'data:image/png;base64,' + base64.b64encode(buf.getvalue()).decode('ascii')


# ---------- dati ----------
def _slug(text):
    raw = unicodedata.normalize('NFKD', str(text)).encode('ascii', 'ignore').decode()
    return re.sub(r'[^a-z0-9]+', '-', raw.lower()).strip('-')[:40] or 'squadra'


def _read(assets):
    path = team_overrides.overrides_path(assets)
    try:
        return json.loads(path.read_text(encoding='utf-8')).get('teams') or {}
    except (OSError, ValueError, AttributeError):
        return {}


def _dump(teams):
    return json.dumps({'version': 1, 'teams': dict(sorted(teams.items()))}, ensure_ascii=False, indent=2) + '\n'


def _catalog(manifest_rows):
    """{nome normalizzato: nome squadra} per tutte le squadre FCLogo (nome + alias)."""
    out = {}
    for row in manifest_rows:
        for n in [row.get('name'), *(row.get('aliases') or [])]:
            if n:
                out.setdefault(normalize_team_name(n), row['name'])
    return out


def build_change(request, manifest_rows, current, photos):
    """Valida la richiesta della mini app. Ritorna (chiave, voce o None, png nuovo o None).

    request: {key?, base?, name?, aliases: [...], logo: 'keep' | 'upload:<id>' | null, reset?: true}
    """
    catalog = _catalog(manifest_rows)
    base = str(request.get('base') or '').strip() or None
    if base:
        base = catalog.get(normalize_team_name(base))
        if not base:
            raise ValueError('Squadra non trovata nel catalogo loghi.')
    key = str(request.get('key') or '').strip()
    if base:
        key = normalize_team_name(base)
    elif not key.startswith('new:'):
        name = ' '.join(str(request.get('name') or '').split())
        if not name:
            raise ValueError('Scrivi il nome della squadra.')
        key = 'new:' + _slug(name)
        if key in current:
            raise ValueError(f'C’è già una squadra aggiunta con il nome «{name}».')
    if request.get('reset'):
        return key, None, None

    name = ' '.join(str(request.get('name') or '').split())[:MAX_NAME] or None
    aliases = [' '.join(str(a).split())[:MAX_NAME] for a in (request.get('aliases') or []) if str(a).strip()]
    if len(aliases) > MAX_ALIASES:
        raise ValueError(f'Al massimo {MAX_ALIASES} nomi ESPN per squadra.')
    own = normalize_team_name(base) if base else None
    for alias in aliases:
        owner = catalog.get(normalize_team_name(alias))
        if owner and normalize_team_name(owner) != own:
            raise ValueError(f'«{alias}» è già il nome di {owner} nel catalogo.')
        for other_key, other in current.items():
            if other_key != key and normalize_team_name(alias) in {
                    normalize_team_name(n) for n in [other.get('name'), *(other.get('aliases') or [])] if n}:
                raise ValueError(f'«{alias}» è già collegato a {other.get("name") or other.get("base")}.')

    logo, png = request.get('logo', 'keep'), None
    old = current.get(key) or {}
    if logo == 'keep':
        logo = old.get('logo')
    elif isinstance(logo, str) and logo.startswith('upload:'):
        raw = photos.get(logo[7:])
        if raw is None:
            raise ValueError('Logo caricato scaduto: caricalo di nuovo.')
        png = make_mono(raw)
        logo = f'logos/{_slug(base or name or key)}-{hashlib.sha256(png).hexdigest()[:8]}.png'
    else:
        logo = None
    if not base and not (name and logo):
        raise ValueError('Per una squadra nuova servono nome e logo.')
    entry = team_overrides.clean_entry({'base': base, 'name': name, 'aliases': aliases, 'logo': logo})
    return key, entry, png


# ---------- salvataggio ----------
def _commit(changes, message, env):
    """Un commit nel repo degli asset con i file dati: {percorso: bytes | None (= cancella)}."""
    token = env.get('IMAGEGEN_ASSETS_PAT', '').strip()
    repo = env.get('IMAGEGEN_ASSETS_REPO', ASSETS_REPO_DEFAULT).strip()
    if not token:
        return False, 'token IMAGEGEN_ASSETS_PAT mancante'
    api = f'https://api.github.com/repos/{repo}'
    h = {'Authorization': f'Bearer {token}', 'Accept': 'application/vnd.github+json', 'X-GitHub-Api-Version': '2022-11-28'}
    for _attempt in range(3):
        ref = requests.get(f'{api}/git/ref/heads/main', headers=h, timeout=20)
        if ref.status_code != 200:
            return False, f'lettura repo HTTP {ref.status_code}'
        head = ref.json()['object']['sha']
        tree = requests.get(f'{api}/git/commits/{head}', headers=h, timeout=20).json()['tree']['sha']
        entries = []
        for path, data in changes.items():
            if data is None:
                entries.append({'path': path, 'mode': '100644', 'type': 'blob', 'sha': None})
                continue
            blob = requests.post(f'{api}/git/blobs', headers=h, timeout=30,
                                 json={'content': base64.b64encode(data).decode(), 'encoding': 'base64'})
            if blob.status_code != 201:
                return False, f'scrittura HTTP {blob.status_code}'
            entries.append({'path': path, 'mode': '100644', 'type': 'blob', 'sha': blob.json()['sha']})
        new_tree = requests.post(f'{api}/git/trees', headers=h, timeout=30, json={'base_tree': tree, 'tree': entries})
        if new_tree.status_code != 201:
            return False, f'scrittura HTTP {new_tree.status_code}'
        commit = requests.post(f'{api}/git/commits', headers=h, timeout=30,
                               json={'message': message, 'tree': new_tree.json()['sha'], 'parents': [head]})
        if commit.status_code != 201:
            return False, f'scrittura HTTP {commit.status_code}'
        move = requests.patch(f'{api}/git/refs/heads/main', headers=h, timeout=20, json={'sha': commit.json()['sha']})
        if move.status_code == 200:
            return True, ''
        if move.status_code != 422:      # 422 = qualcuno ha scritto nel frattempo: si riprova
            return False, f'scrittura HTTP {move.status_code}'
    return False, 'il repo cambiava di continuo, riprova'


def save(request, assets, manifest_rows, photos, env=None):
    """Applica la richiesta. Ritorna {key, entry, remote: bool, warning}."""
    env = os.environ if env is None else env
    assets = Path(assets)
    folder = assets / team_overrides.DIRNAME
    with _lock:
        current = _read(assets)
        key, entry, png = build_change(request, manifest_rows, current, photos)
        new = dict(current)
        if entry:
            new[key] = entry
        else:
            new.pop(key, None)
        used = {e.get('logo') for e in new.values() if e.get('logo')}
        stale = {e.get('logo') for e in current.values() if e.get('logo')} - used
        changes = {}
        folder.mkdir(parents=True, exist_ok=True)
        if png:
            (folder / entry['logo']).parent.mkdir(parents=True, exist_ok=True)
            (folder / entry['logo']).write_bytes(png)
            changes[f'{team_overrides.DIRNAME}/{entry["logo"]}'] = png
        for logo in stale:
            (folder / logo).unlink(missing_ok=True)
            changes[f'{team_overrides.DIRNAME}/{logo}'] = None
        text = _dump(new)
        team_overrides.overrides_path(assets).write_text(text, encoding='utf-8')
        changes[f'{team_overrides.DIRNAME}/{team_overrides.FILENAME}'] = text.encode('utf-8')
        label = (entry or {}).get('name') or (entry or {}).get('base') or (current.get(key) or {}).get('name') or key
        what = 'cancellate le personalizzazioni di' if entry is None else 'aggiornata'
        ok, why = _commit(changes, f'Squadre e loghi: {what} {label} (mini app ImageGen)', env)
    if not ok:
        print(f'WARN IMAGEGEN: correzione squadra salvata solo per questa sessione ({why})', flush=True)
    else:
        print(f'INFO IMAGEGEN: correzione squadra pubblicata | {key}', flush=True)
    return {'key': key, 'entry': entry, 'remote': ok, 'warning': '' if ok else why}
