"""FOTO + JR: foto caricata dall'utente con il solo logo JR (compleanni, MOTM...).

Due stili:
- classic: la foto a tutta pagina (design Canva delle pagine 6/11/16);
- blur: come la pagina 26 Canva. Sfondo = una delle foto, a tutta pagina e sfocata;
  sopra, fino a 3 foto nitide con le loro proporzioni e un'ombra morbida,
  ognuna spostata e ingrandita dall'utente.

Il logo ha posizione e misura del design Canva; il colore lo sceglie l'utente.
"""
import base64
import json
import math
from functools import lru_cache

from graphics.common import photo_layer, DESIGN_H, DESIGN_W, asset_dir, data_uri, render_html
from graphics.starting_xi import check_photo

COLORS = ('black', 'white', 'gold')
STYLES = ('classic', 'blur')
MAX_CARDS = 3
# Pagina 26 Canva (misure sulla pagina 1080x1440): sfondo ingrandito del 6% per
# nascondere i bordi della sfocatura, foto con ombra nera morbida tutto intorno.
BLUR_PX = 28
BLUR_ZOOM = 1.06
CARD_SHADOW = '0 6px 44px rgba(0,0,0,.62)'
CARD_W = (0.12, 1.4)          # larghezza foto: da 12% a 140% della pagina


@lru_cache(maxsize=1)
def _meta():
    return json.loads((asset_dir() / 'canva' / 'jr.json').read_text(encoding='utf-8'))


def _uri(raw):
    mime = 'image/png' if raw.startswith(b'\x89PNG') else 'image/jpeg'
    return f'data:{mime};base64,' + base64.b64encode(raw).decode('ascii')


def clean_card(value):
    """{'x','y'} centro in frazione della pagina, {'w'} larghezza in frazione della pagina."""
    if not isinstance(value, dict):
        raise ValueError('Posizione foto non valida.')
    try:
        card = {k: float(value.get(k, d)) for k, d in (('x', .5), ('y', .5), ('w', .86))}
    except (TypeError, ValueError):
        raise ValueError('Posizione foto non valida.') from None
    if not all(math.isfinite(v) for v in card.values()):
        raise ValueError('Posizione foto non valida.')
    card['x'] = max(-.5, min(1.5, card['x']))
    card['y'] = max(-.5, min(1.5, card['y']))
    card['w'] = max(CARD_W[0], min(CARD_W[1], card['w']))
    return {k: round(v, 5) for k, v in card.items()}


def _classic(photo, frame):
    photo_html, page_bg = photo_layer(photo, frame)
    return photo_html, page_bg, ''


def _blur(background, cards):
    """Sfondo sfocato + foto nitide con ombra. cards = [(byte, {'x','y','w'})]."""
    if background is None:          # "fantasma" per l'editor: solo il logo
        return '', 'transparent', ''
    w, h = check_photo(background)
    cover = max(DESIGN_W / w, DESIGN_H / h) * BLUR_ZOOM
    bw, bh = w * cover, h * cover
    html = [f'<img src="{_uri(background)}" style="left:{(DESIGN_W - bw) / 2}px;top:{(DESIGN_H - bh) / 2}px;'
            f'width:{bw}px;height:{bh}px;filter:blur({BLUR_PX}px)">']
    for raw, card in cards:
        cw, ch = check_photo(raw)
        width = card['w'] * DESIGN_W
        height = width * ch / cw
        html.append(f'<img class="card" src="{_uri(raw)}" style="left:{card["x"] * DESIGN_W - width / 2}px;'
                    f'top:{card["y"] * DESIGN_H - height / 2}px;width:{width}px;height:{height}px">')
    return ''.join(html), '#111', f'.card{{box-shadow:{CARD_SHADOW}}}'


def build_html(*, color, photo=None, frame=None, style='classic', background=None, cards=(), **_):
    if color not in COLORS:
        raise ValueError('Colore JR non valido.')
    if style not in STYLES:
        raise ValueError('Stile non valido.')
    if style == 'blur':
        body, page_bg, css = _blur(background, cards)
    else:
        body, page_bg, css = _classic(photo, frame)
    overlay = data_uri(asset_dir() / 'canva' / _meta()[color]['overlay'])
    return f'''<!doctype html><html><head><meta charset="utf-8"><style>
*{{margin:0;padding:0}}
html,body{{width:{DESIGN_W}px;height:{DESIGN_H}px;overflow:hidden;background:{page_bg}}}
img{{position:absolute}}
{css}
</style></head><body>
{body}
<img src="{overlay}" style="left:0;top:0;width:{DESIGN_W}px;height:{DESIGN_H}px">
</body></html>'''


def render(ghost=False, **kwargs):
    if ghost:
        kwargs['photo'] = None
        kwargs['background'] = None
    return render_html(build_html(**kwargs), ghost=ghost)
