"""FOTO + JR: foto caricata dall'utente con il solo logo JR (compleanni, MOTM...).

Il logo ha posizione e misura del design Canva; il colore lo sceglie l'utente.
"""
import base64
import json
from functools import lru_cache

from graphics.common import DESIGN_H, DESIGN_W, asset_dir, data_uri, render_html
from graphics.starting_xi import check_photo, photo_box

COLORS = ('black', 'white', 'gold')


@lru_cache(maxsize=1)
def _meta():
    return json.loads((asset_dir() / 'canva' / 'jr.json').read_text(encoding='utf-8'))


def build_html(*, color, photo, frame, **_):
    if color not in COLORS:
        raise ValueError('Colore JR non valido.')
    left, top, width, height = photo_box(check_photo(photo), frame)
    mime = 'image/png' if photo.startswith(b'\x89PNG') else 'image/jpeg'
    photo_uri = f'data:{mime};base64,' + base64.b64encode(photo).decode('ascii')
    overlay = data_uri(asset_dir() / 'canva' / _meta()[color]['overlay'])
    return f'''<!doctype html><html><head><meta charset="utf-8"><style>
*{{margin:0;padding:0}}
html,body{{width:{DESIGN_W}px;height:{DESIGN_H}px;overflow:hidden;background:#fff}}
img{{position:absolute}}
</style></head><body>
<img src="{photo_uri}" style="left:{left}px;top:{top}px;width:{width}px;height:{height}px">
<img src="{overlay}" style="left:0;top:0;width:{DESIGN_W}px;height:{DESIGN_H}px">
</body></html>'''


def render(**kwargs):
    return render_html(build_html(**kwargs))
