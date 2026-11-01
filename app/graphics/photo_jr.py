"""FOTO + JR: foto caricate dall'utente con il solo logo JR (compleanni, MOTM...).

Tre stili:
- classic: la foto a tutta pagina (design Canva delle pagine 6/11/16), in vari formati (3:4, 1:1, 16:9...);
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
import re
from functools import lru_cache

from graphics.common import photo_layer, DESIGN_H, DESIGN_W, OUT_W, asset_dir, data_uri, render_html
from graphics.starting_xi import check_photo

COLORS = ('black', 'white', 'gold')      # i tre loghi già pronti (PNG Canva, l'oro ha la sua texture)
HEX_RE = re.compile(r'#[0-9a-fA-F]{6}')
MAX_STOPS = 6
# Formati della Classica (larghezza:altezza). La pagina resta larga 1080 px design (uscita 1920 px):
# cambia solo l'altezza. Il logo JR sta sempre in alto a destra, alla stessa distanza dal bordo alto e
# destro e con la stessa misura che ha nel 3:4: l'overlay Canva (1080x1440) è ancorato in alto a sinistra
# di una pagina sempre larga 1080, quindi il logo non si sposta e non si ridimensiona.
RATIOS = {'3:4': (3, 4), '4:5': (4, 5), '1:1': (1, 1), '4:3': (4, 3), '3:2': (3, 2), '16:9': (16, 9), '9:16': (9, 16)}
DEFAULT_RATIO = '3:4'


def page_size(ratio=DEFAULT_RATIO):
    """Pagina in pixel design (1080 x altezza); l'uscita è 1920 x round(1920 * h / w), es. 16:9 -> 1920x1080."""
    if ratio not in RATIOS:
        raise ValueError('Formato non valido.')
    rw, rh = RATIOS[ratio]
    out_h = round(OUT_W * rh / rw)
    return DESIGN_W, out_h * DESIGN_W / OUT_W
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
COLLAGE_ZOOM = (1.0, 6.0)      # zoom della foto dentro il riquadro (1 = riempie giusto il riquadro)
CARD_W = (0.12, 1.4)          # larghezza foto: da 12% a 140% della pagina


@lru_cache(maxsize=1)
def _meta():
    return json.loads((asset_dir() / 'canva' / 'jr.json').read_text(encoding='utf-8'))


def _uri(raw):
    mime = 'image/png' if raw.startswith(b'\x89PNG') else 'image/jpeg'
    return f'data:{mime};base64,' + base64.b64encode(raw).decode('ascii')


def clean_color(value):
    """Colore del logo: 'black' | 'white' | 'gold' (PNG pronti) oppure un colore libero:
    {'type':'solid','hex':'#RRGGBB'} o {'type':'gradient','angle':0-360,'stops':[{'c':'#RRGGBB','p':0-100}, ...]}.
    Ritorna il valore normalizzato (stringa o dict) o ValueError."""
    if isinstance(value, str) and value in COLORS:
        return value
    if not isinstance(value, dict):
        raise ValueError('Colore JR non valido.')
    kind = value.get('type')
    try:
        if kind == 'solid':
            hex_ = str(value.get('hex'))
            if not HEX_RE.fullmatch(hex_):
                raise ValueError
            return {'type': 'solid', 'hex': hex_.lower()}
        if kind == 'gradient':
            stops = value.get('stops')
            if not isinstance(stops, list) or not 2 <= len(stops) <= MAX_STOPS:
                raise ValueError
            out = []
            for stop in stops:
                c, p = str(stop.get('c')), float(stop.get('p'))
                if not HEX_RE.fullmatch(c) or not math.isfinite(p):
                    raise ValueError
                out.append({'c': c.lower(), 'p': round(max(0.0, min(100.0, p)), 2)})
            angle = float(value.get('angle', 135))
            if not math.isfinite(angle):
                raise ValueError
            out.sort(key=lambda stop: stop['p'])
            return {'type': 'gradient', 'angle': round(angle % 360, 2), 'stops': out}
    except (AttributeError, TypeError, ValueError):
        pass
    raise ValueError('Colore JR non valido.')


@lru_cache(maxsize=1)
def _logo_shape():
    """Sagoma del logo: PNG nero (solo la forma conta, il canale alfa) e il suo riquadro in pixel design."""
    from PIL import Image

    path = asset_dir() / 'canva' / _meta()['black']['overlay']
    with Image.open(path) as image:
        alpha = image.convert('RGBA').getchannel('A')
        box = alpha.point(lambda a: 255 if a > 8 else 0).getbbox() or (0, 0, image.width, image.height)
        sx, sy = DESIGN_W / image.width, DESIGN_H / image.height
    left, top, right, bottom = box
    pad = 1.5      # il bordo sfumato del logo non va tagliato
    return (data_uri(path), max(0.0, left * sx - pad), max(0.0, top * sy - pad),
            min(DESIGN_W, right * sx + pad), min(DESIGN_H, bottom * sy + pad))


def logo_fill(color):
    """Riempimento CSS (tinta unita o linear-gradient) di un colore libero già validato."""
    if color['type'] == 'solid':
        return color['hex']
    stops = ','.join(f'{s["c"]} {s["p"]}%' for s in color['stops'])
    return f'linear-gradient({color["angle"]}deg,{stops})'


def _logo(color):
    """HTML del logo JR. I tre colori pronti sono PNG; un colore libero ricolora la stessa sagoma:
    un riquadro grande quanto il logo, con il riempimento (così la sfumatura corre sul logo e non
    sulla pagina) e il logo nero come maschera."""
    if isinstance(color, str):
        overlay = data_uri(asset_dir() / 'canva' / _meta()[color]['overlay'])
        return f'<img src="{overlay}" style="left:0;top:0;width:{DESIGN_W}px;height:{DESIGN_H}px">'
    uri, left, top, right, bottom = _logo_shape()
    mask = f'var(--m) {-left:.2f}px {-top:.2f}px/{DESIGN_W}px {DESIGN_H}px no-repeat'
    return (f'<div style="position:absolute;left:{left:.2f}px;top:{top:.2f}px;width:{right - left:.2f}px;'
            f'height:{bottom - top:.2f}px;background:{logo_fill(color)};--m:url({uri});'
            f'-webkit-mask:{mask};mask:{mask}"></div>')


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
        # Ritaglio scelto dall'utente: px/py = quanto la foto è spostata (0 = allineata a sinistra/in alto,
        # 1 = a destra/in basso), z = zoom. Senza questi valori: ritaglio automatico di prima.
        try:
            crop = {'px': float(item.get('px', .5)), 'py': float(item.get('py', COLLAGE_FOCUS_Y / 100)),
                    'z': float(item.get('z', 1))}
        except (TypeError, ValueError):
            raise ValueError('Ritaglio foto non valido.') from None
        if not all(math.isfinite(v) for v in crop.values()):
            raise ValueError('Ritaglio foto non valido.')
        crop['px'] = max(0.0, min(1.0, crop['px']))
        crop['py'] = max(0.0, min(1.0, crop['py']))
        crop['z'] = max(COLLAGE_ZOOM[0], min(COLLAGE_ZOOM[1], crop['z']))
        cells.append({'photo_id': pid, **{k: round(v, 5) for k, v in {**rect, **crop}.items()}})
    return cells


def collage_crop(photo_size, cell_px, px, py, z):
    """Posizione della foto nel suo riquadro (stessi calcoli della Mini App), in percentuali del riquadro:
    la foto copre il riquadro, si ingrandisce di z e si sposta di px/py nello spazio che avanza."""
    pw, ph = photo_size
    width_ar = (pw / ph) / (cell_px[0] / cell_px[1])      # proporzione foto / proporzione riquadro
    w = 100 * z * max(1.0, width_ar)
    h = 100 * z * max(1.0, 1 / width_ar)
    return (100 - w) * px, (100 - h) * py, w, h


def _collage(cells):
    """Riquadri con foto che li riempiono. cells = [(byte, {'x','y','w','h','px','py','z'})]."""
    html = []
    for raw, c in cells:
        size = check_photo(raw)
        cw, ch = c['w'] * DESIGN_W, c['h'] * DESIGN_H
        left, top, w, h = collage_crop(size, (cw, ch), c.get('px', .5), c.get('py', COLLAGE_FOCUS_Y / 100),
                                       c.get('z', 1))
        html.append(f'<div class="cell" style="left:{c["x"] * DESIGN_W}px;top:{c["y"] * DESIGN_H}px;'
                    f'width:{cw}px;height:{ch}px">'
                    f'<img src="{_uri(raw)}" style="left:{left:.4f}%;top:{top:.4f}%;width:{w:.4f}%;height:{h:.4f}%"></div>')
    css = '.cell{position:absolute;overflow:hidden;background:#ddd}'
    return ''.join(html), '#fff', css


def _classic(photo, frame, page):
    photo_html, page_bg = photo_layer(photo, frame, page)
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


def build_html(*, color, photo=None, frame=None, style='classic', background=None, cards=(), cells=(),
               ratio=DEFAULT_RATIO, **_):
    if style != 'classic':
        ratio = DEFAULT_RATIO          # Sfocata e Collage restano 3:4
    page = page_size(ratio)
    color = clean_color(color)
    if style not in STYLES:
        raise ValueError('Stile non valido.')
    if style == 'collage':
        body, page_bg, css = _collage(cells) if cells else ('', 'transparent', '')
    elif style == 'blur':
        body, page_bg, css = _blur(background, cards)
    else:
        body, page_bg, css = _classic(photo, frame, page)
    return f'''<!doctype html><html><head><meta charset="utf-8"><style>
*{{margin:0;padding:0}}
html,body{{width:{page[0]}px;height:{page[1]}px;overflow:hidden;background:{page_bg}}}
img{{position:absolute}}
{css}
</style></head><body>
{body}
{_logo(color)}
</body></html>'''


def render(ghost=False, **kwargs):
    if ghost:
        kwargs['photo'] = None
        kwargs['background'] = None
        kwargs['cells'] = ()
    page = page_size(kwargs.get('ratio', DEFAULT_RATIO) if kwargs.get('style', 'classic') == 'classic' else DEFAULT_RATIO)
    return render_html(build_html(**kwargs), ghost=ghost, page=page)
