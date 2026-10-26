"""STARTING XI: pagine 6 (home), 11 (away), 16 (third).

Livelli dal basso: foto caricata dall'utente (spostata/zoomata nella Mini App),
livello fisso Canva (sfumature, grana, titolo, JR), loghi, numeri e nomi.
"""
import base64
import io
import json
import re
from functools import lru_cache

from PIL import Image

from graphics.common import photo_layer
from graphics.common import (
    DESIGN_H, DESIGN_W, asset_dir, data_uri, esc, font_face, render_html, team_logo,
)

KITS = ('home', 'away', 'third')

# Misure dal PDF Canva (pixel 1080x1440).
NAME_X, NAME_BASE = 174.28, 490.69
NUMBER_RIGHT, NUMBER_BASE = 157.27, 496.69
ROW_STEP = 87
NAME_SIZE, NAME_SPACING = 69.77, -2.444
NUMBER_SIZE = 91.08
LOGO_BOXES = ((313.02, 213.2), (427.43, 213.2))
LOGO_SIZE = 138.09

PLAYERS = 11
MAX_PHOTO_BYTES = 12 * 1024 * 1024


@lru_cache(maxsize=1)
def _meta():
    return json.loads((asset_dir() / 'canva' / 'starting_xi.json').read_text(encoding='utf-8'))


def parse_lineup(text):
    """11 giocatori nell'ordine scelto. Dalla Mini App arriva una lista
    [{'number': '25', 'name': 'Guglielmo Vicario'}]; resta valido anche il testo
    con 11 righe 'numero nome' (es. '25 Vicario')."""
    if isinstance(text, list):
        rows = []
        for item in text:
            if not isinstance(item, dict):
                raise ValueError('Formazione non valida.')
            number, name = str(item.get('number') or '').strip(), str(item.get('name') or '').strip()
            if not re.fullmatch(r'\d{1,2}', number):
                raise ValueError(f'Manca il numero di maglia di {name or "un giocatore"}.')
            if not name:
                raise ValueError('Scegli tutti gli 11 giocatori.')
            rows.append((str(int(number)), name))
        if len(rows) != PLAYERS:
            raise ValueError(f'Servono 11 giocatori, ne ho trovati {len(rows)}.')
        return rows
    rows = []
    for line in str(text or '').splitlines():
        line = ' '.join(line.split())
        if not line or line.endswith(':'):
            continue
        match = re.fullmatch(r'#?(\d{1,2})\s*[-.)–—]?\s*(.+?)', line) or \
            re.fullmatch(r'(.+?)\s*[-–—]?\s*#?(\d{1,2})', line)
        if not match:
            raise ValueError(f'Riga senza numero di maglia: “{line}”.')
        number, name = match.groups()
        if not number.isdigit():
            number, name = name, number
        rows.append((str(int(number)), name.strip()))
    if len(rows) != PLAYERS:
        raise ValueError(f'Servono 11 giocatori, ne ho trovati {len(rows)}.')
    return rows


def check_photo(raw):
    """Verifica la foto caricata e ritorna (larghezza, altezza)."""
    if not raw or len(raw) > MAX_PHOTO_BYTES:
        raise ValueError('Foto mancante o troppo grande (max 12 MB).')
    try:
        with Image.open(io.BytesIO(raw)) as image:
            image.verify()
        with Image.open(io.BytesIO(raw)) as image:
            return image.size
    except Exception:
        raise ValueError('Foto non valida: usa JPG o PNG.') from None


def photo_box(size, frame):
    """Posizione della foto in pixel del design.

    frame = {'x', 'y', 'zoom'} dalla Mini App: x/y spostamento del centro
    (in frazione della pagina), zoom >= 1 rispetto a "riempi la pagina".
    """
    w, h = size
    cover = max(DESIGN_W / w, DESIGN_H / h)
    zoom = min(max(float(frame.get('zoom', 1)), 1), 6)
    width, height = w * cover * zoom, h * cover * zoom
    left = (DESIGN_W - width) / 2 + float(frame.get('x', 0)) * DESIGN_W
    top = (DESIGN_H - height) / 2 + float(frame.get('y', 0)) * DESIGN_H
    # Mai bordi vuoti: la foto copre sempre tutta la pagina.
    left = min(0, max(DESIGN_W - width, left))
    top = min(0, max(DESIGN_H - height, top))
    return left, top, width, height


def _text_rows(role, values, style, x, base, anchor, attrs):
    out = []
    for k, value in enumerate(values):
        y = base + k * ROW_STEP
        text = f'<text x="{x}" y="{y}" text-anchor="{anchor}" {attrs}>{esc(value)}</text>'
        if 'rows' in style:
            plate = style['rows'][k]
            out.append(
                f'<clipPath id="{role}{k}">{text}</clipPath>'
                f'<image href="{data_uri(asset_dir() / "canva" / plate["file"])}" '
                f'x="{plate["x"]}" y="{plate["y"]}" width="{plate["w"]}" height="{plate["h"]}" '
                f'preserveAspectRatio="none" clip-path="url(#{role}{k})"/>'
            )
        else:
            out.append(text.replace('<text ', f'<text fill="{style["color"]}" ', 1))
    return ''.join(out)


def build_html(*, kit, lineup, photo, frame, home_name, home_id, away_name, away_id, **_):
    if kit not in KITS:
        raise ValueError('Maglia non valida.')
    meta = _meta()[kit]
    canva = asset_dir() / 'canva'
    photo_html, page_bg = photo_layer(photo, frame)

    numbers = _text_rows(
        'n', [n for n, _ in lineup], meta['text']['number'], NUMBER_RIGHT, NUMBER_BASE, 'end',
        f'font-family="Allogist" font-style="italic" font-size="{NUMBER_SIZE}"',
    )
    names = _text_rows(
        'p', [name.upper() for _, name in lineup], meta['text']['name'], NAME_X, NAME_BASE, 'start',
        f'font-family="Bebas Neue" font-size="{NAME_SIZE}" letter-spacing="{NAME_SPACING}"',
    )
    logos = ''.join(
        f'<div class="logo" style="left:{x}px;top:{y}px;background:{meta["logo_color"]};'
        f'--m:url({data_uri(team_logo(name, team_id))})"></div>'
        for (x, y), (name, team_id) in zip(LOGO_BOXES, ((home_name, home_id), (away_name, away_id)))
    )

    return f'''<!doctype html><html><head><meta charset="utf-8"><style>
*{{margin:0;padding:0;box-sizing:border-box}}
html,body{{width:{DESIGN_W}px;height:{DESIGN_H}px;overflow:hidden;background:{page_bg}}}
.abs{{position:absolute}}
.logo{{position:absolute;width:{LOGO_SIZE}px;height:{LOGO_SIZE}px;
-webkit-mask:var(--m) center/100% 100% no-repeat;mask:var(--m) center/100% 100% no-repeat}}
{font_face('Bebas Neue', 'BebasNeue2014-Regular.ttf')}
@font-face{{font-family:'Allogist';font-style:italic;src:url({data_uri(asset_dir() / 'fonts' / 'AllogistItalic.ttf')})}}
svg{{position:absolute;left:0;top:0}}
</style></head><body>
{photo_html}
<img class="abs" src="{data_uri(canva / meta['overlay'])}" style="left:0;top:0;width:{DESIGN_W}px;height:{DESIGN_H}px">
{logos}
<svg width="{DESIGN_W}" height="{DESIGN_H}" viewBox="0 0 {DESIGN_W} {DESIGN_H}">{numbers}{names}</svg>
</body></html>'''


def render(ghost=False, **kwargs):
    if ghost:
        kwargs['photo'] = None
    return render_html(build_html(**kwargs), ghost=ghost)
