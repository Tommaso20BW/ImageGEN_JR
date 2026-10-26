"""Strumenti comuni: asset, loghi, font e render HTML -> PNG.

Le misure nei modelli sono in pixel del design Canva (1080x1440):
il render le porta a 1920x2560 come le altre grafiche HD.
"""
import base64
import html
import json
import mimetypes
import os
import unicodedata
from functools import lru_cache
from pathlib import Path

DESIGN_W, DESIGN_H = 1080, 1440
OUT_W, OUT_H = 1920, 2560


def asset_dir():
    """Cartella asset privati: IMAGEGEN_ASSETS in locale, motore grafico su GitHub."""
    override = os.environ.get('IMAGEGEN_ASSETS')
    if override:
        return Path(override)
    from livescore.graphics import goal
    return Path(goal.DEFAULT_ASSET_DIR)


def data_uri(path):
    path = Path(path)
    mime = mimetypes.guess_type(path.name)[0] or 'application/octet-stream'
    if path.suffix.lower() == '.otf':
        mime = 'font/otf'
    elif path.suffix.lower() == '.ttf':
        mime = 'font/ttf'
    return f'data:{mime};base64,' + base64.b64encode(path.read_bytes()).decode('ascii')


def font_face(family, filename):
    return (
        f"@font-face{{font-family:'{family}';"
        f"src:url({data_uri(asset_dir() / 'fonts' / filename)});}}"
    )


def esc(value):
    return html.escape(str(value), quote=True)


def normalize(value):
    raw = unicodedata.normalize('NFKD', str(value or '').casefold())
    return ' '.join(''.join(c for c in raw if not unicodedata.combining(c)).split())


@lru_cache(maxsize=2)
def _logo_rows(assets_text):
    assets = Path(assets_text)
    path = assets / 'team_logos' / 'manifest.json'
    if not path.is_file():
        path = assets / 'team_logos' / 'fclogo_cache' / 'manifest.json'
    return json.loads(path.read_text(encoding='utf-8')).get('teams', [])


def team_logo(name, team_id=''):
    """Percorso del logo mono della squadra (stesso file usato su Canva)."""
    assets = asset_dir()
    rows = _logo_rows(str(assets))
    key = normalize(name)
    for row in rows:
        names = [row.get('name'), *(row.get('aliases') or [])]
        if (team_id and str(row.get('espn_id') or '') == str(team_id)) or key in map(normalize, names):
            for file in [row.get('file'), *(row.get('files') or [])]:
                for base in ('team_logos', 'team_logos/fclogo_cache'):
                    path = assets / base / (file or '')
                    if file and path.is_file():
                        return path
    raise FileNotFoundError(f'Logo non trovato per {name!r}')


def render_html(markup, ghost=False):
    """Render della pagina 1080x1440 in PNG 1920x2560.

    ghost=True: versione leggera (540x720) con sfondo trasparente, per l'editor foto.
    """
    from playwright.sync_api import sync_playwright

    with sync_playwright() as playwright:
        chrome = os.environ.get('IMAGEGEN_CHROME') or None
        browser = playwright.chromium.launch(executable_path=chrome)
        try:
            page = browser.new_page(
                viewport={'width': DESIGN_W, 'height': DESIGN_H},
                device_scale_factor=0.5 if ghost else OUT_W / DESIGN_W,
            )
            page.set_content(markup, wait_until='load')
            page.evaluate('() => document.fonts.ready')
            return page.screenshot(type='png', omit_background=ghost)
        finally:
            browser.close()


def photo_layer(photo, frame):
    """(<img> della foto, colore di fondo pagina). Senza foto: niente <img> e fondo
    trasparente, per la versione "fantasma" mostrata sopra la foto nell'editor."""
    if photo is None:
        return '', 'transparent'
    from graphics.starting_xi import check_photo, photo_box
    left, top, width, height = photo_box(check_photo(photo), frame)
    mime = 'image/png' if photo.startswith(b'\x89PNG') else 'image/jpeg'
    uri = f'data:{mime};base64,' + base64.b64encode(photo).decode('ascii')
    return (f'<img src="{uri}" style="position:absolute;left:{left}px;top:{top}px;'
            f'width:{width}px;height:{height}px">'), '#fff'


BASE_CSS = (
    '*{margin:0;padding:0;box-sizing:border-box}'
    f'html,body{{width:{DESIGN_W}px;height:{DESIGN_H}px;overflow:hidden;background:#000}}'
    '.abs{position:absolute}'
    '.white{filter:brightness(0) invert(1)}'
)


def overlay_preview(name, kit, width=540):
    """Livello fisso Canva rimpicciolito, da mostrare nell'editor foto della Mini App."""
    import io

    from PIL import Image

    meta = json.loads((asset_dir() / 'canva' / f'{name}.json').read_text(encoding='utf-8'))
    with Image.open(asset_dir() / 'canva' / meta[kit]['overlay']) as image:
        small = image.resize((width, round(width * DESIGN_H / DESIGN_W)), Image.LANCZOS)
        out = io.BytesIO()
        small.save(out, format='PNG', optimize=True)
        return out.getvalue()


# Colore dello sfondo delle foto home (crema): la sfumatura chiara Canva lo prende.
HOME_FX_COLOR = (237, 231, 221)


def canva_layers(meta, photo, frame):
    """Livelli Canva sopra la foto: sfumature/grana + titolo e JR.

    - senza foto (anteprima nell'editor): solo titolo e JR, niente sfumature;
    - sfumatura chiara (home): ricolorata nel crema dello sfondo delle foto home,
      così non si vede lo stacco col bianco freddo di Canva (grana intatta).
    """
    canva = asset_dir() / 'canva'
    full = f'style="position:absolute;left:0;top:0;width:{DESIGN_W}px;height:{DESIGN_H}px"'
    text = f'<img src="{data_uri(canva / meta["text_overlay"])}" {full}>'
    if photo is None:
        return text
    fx = _home_fx(meta['fx']) if meta.get('fx_light') else data_uri(canva / meta['fx'])
    return f'<img src="{fx}" {full}>' + text


@lru_cache(maxsize=4)
def _home_fx(name):
    import io

    import numpy as np
    from PIL import Image

    a = np.asarray(Image.open(asset_dir() / 'canva' / name).convert('RGBA')).astype(float)
    solid = a[..., 3] > 240
    base = np.median(a[solid][:, :3], axis=0)                   # bianco Canva della sfumatura
    a[..., :3] = np.clip(a[..., :3] * (np.array(HOME_FX_COLOR) / base), 0, 255)
    out = io.BytesIO()
    Image.fromarray(a.astype('uint8'), 'RGBA').save(out, format='PNG')
    return 'data:image/png;base64,' + base64.b64encode(out.getvalue()).decode('ascii')
