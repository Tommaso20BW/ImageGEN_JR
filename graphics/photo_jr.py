"""FOTO + JR: foto caricate dall'utente con il solo logo JR (compleanni, MOTM...).

Tre stili:
- classic: la foto a tutta pagina (design Canva delle pagine 6/11/16);
- blur: come la pagina 26 Canva. Sfondo = una delle foto, a tutta pagina, sfocata e un
  po' scurita; sopra, fino a 4 foto nitide con le loro proporzioni, angoli arrotondati e
  un'ombra morbida, ognuna spostata e ingrandita dall'utente;
- collage: da 2 a 9 foto in un layout a riquadri (come i collage di Canva). I riquadri li
  sceglie la Mini App (layout automatici) e arrivano qui già pronti: fondo bianco con linee
  sottili, ogni foto riempie il suo riquadro (ritaglio al centro, un po' verso l'alto per non
  tagliare i volti).

Il logo ha posizione e misura del design Canva; il colore lo sceglie l'utente.
"""
import base64
import json
import math
from functools import lru_cache

from graphics.common import photo_layer, DESIGN_H, DESIGN_W, asset_dir, data_uri, render_html
from graphics.starting_xi import check_photo

COLORS = ('black', 'white', 'gold')
STYLES = ('classic', 'blur', 'collage')
MAX_CARDS = 4                  # foto nitide nello stile Sfocata
MAX_COLLAGE = 9                # foto nel collage
# Pagina 26 Canva (misure sulla pagina 1080x1440): sfondo ingrandito del 6% per
# nascondere i bordi della sfocatura, foto con ombra nera morbida tutto intorno.
BLUR_PX = 36
BLUR_ZOOM = 1.1                # la sfocatura più forte sfuma i bordi: sfondo più grande per coprirli
BLUR_FILTER = f'blur({BLUR_PX}px) brightness(.78) saturate(1.12)'   # un po' scuro: le foto nitide risaltano
CARD_SHADOW = '0 8px 48px rgba(0,0,0,.62)'
CARD_RADIUS = 14
# Collage (come i collage di Instagram/Canva): fondo bianco, bordo e linee sottili, angoli vivi. Il logo JR
# sta sopra la foto in alto a destra, senza fascia riservata. Misure in pixel pagina 1080x1440.
COLLAGE_MARGIN, COLLAGE_GAP = 10, 5
COLLAGE_FOCUS_Y = 38           # ritaglio verticale in % (sotto 50: tiene la parte alta, dove stanno i volti)
COLLAGE_MIN = 0.06             # lato minimo di un riquadro, in frazione della pagina
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


def clean_cells(value, photo_id):
    """Riquadri del collage: [{'photo_id','x','y','w','h'}] in frazione della pagina, o ValueError."""
    if not isinstance(value, list) or not 2 <= len(value) <= MAX_COLLAGE:
        raise ValueError(f'Il collage vuole da 2 a {MAX_COLLAGE} foto.')
    cells, seen = [], set()
    for item in value:
        if not isinstance(item, dict):
            raise ValueError('Layout non valido.')
        try:
            rect = {k: float(item[k]) for k in ('x', 'y', 'w', 'h')}
        except (KeyError, TypeError, ValueError):
            raise ValueError('Layout non valido.') from None
        if not all(math.isfinite(v) for v in rect.values()):
            raise ValueError('Layout non valido.')
        if (rect['w'] < COLLAGE_MIN or rect['h'] < COLLAGE_MIN or rect['x'] < -.001 or rect['y'] < -.001
                or rect['x'] + rect['w'] > 1.001 or rect['y'] + rect['h'] > 1.001):
            raise ValueError('Layout non valido.')
        pid = photo_id(item.get('photo_id'))
        if pid in seen:
            raise ValueError('Ogni riquadro vuole una foto diversa.')
        seen.add(pid)
        cells.append({'photo_id': pid, **{k: round(v, 5) for k, v in rect.items()}})
    return cells


def _collage(cells):
    """Riquadri con foto che li riempiono. cells = [(byte, {'x','y','w','h'})]."""
    html = []
    for raw, c in cells:
        check_photo(raw)
        html.append(f'<div class="cell" style="left:{c["x"] * DESIGN_W}px;top:{c["y"] * DESIGN_H}px;'
                    f'width:{c["w"] * DESIGN_W}px;height:{c["h"] * DESIGN_H}px">'
                    f'<img src="{_uri(raw)}"></div>')
    css = ('.cell{position:absolute;overflow:hidden;background:#ddd}'
           f'.cell img{{left:0;top:0;width:100%;height:100%;object-fit:cover;object-position:50% {COLLAGE_FOCUS_Y}%}}')
    return ''.join(html), '#fff', css


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
            f'width:{bw}px;height:{bh}px;filter:{BLUR_FILTER}">']
    for raw, card in cards:
        cw, ch = check_photo(raw)
        width = card['w'] * DESIGN_W
        height = width * ch / cw
        html.append(f'<img class="card" src="{_uri(raw)}" style="left:{card["x"] * DESIGN_W - width / 2}px;'
                    f'top:{card["y"] * DESIGN_H - height / 2}px;width:{width}px;height:{height}px">')
    return ''.join(html), '#111', f'.card{{box-shadow:{CARD_SHADOW};border-radius:{CARD_RADIUS}px}}'


def build_html(*, color, photo=None, frame=None, style='classic', background=None, cards=(), cells=(), **_):
    if color not in COLORS:
        raise ValueError('Colore JR non valido.')
    if style not in STYLES:
        raise ValueError('Stile non valido.')
    if style == 'collage':
        body, page_bg, css = _collage(cells) if cells else ('', 'transparent', '')
    elif style == 'blur':
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
        kwargs['cells'] = ()
    return render_html(build_html(**kwargs), ghost=ghost)
