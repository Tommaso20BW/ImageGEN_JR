"""FOTO + JR: foto caricata dall'utente con il solo logo JR (compleanni, MOTM...).

Il logo ha posizione e misura del design Canva; il colore lo sceglie l'utente.
"""
import base64
import json
from functools import lru_cache

from graphics.common import photo_layer, DESIGN_H, DESIGN_W, asset_dir, data_uri, render_html
from graphics.starting_xi import check_photo, photo_box

COLORS = ('black', 'white', 'gold')


@lru_cache(maxsize=1)
def _meta():
    return json.loads((asset_dir() / 'canva' / 'jr.json').read_text(encoding='utf-8'))


def build_html(*, color, photo, frame, **_):
    if color not in COLORS:
        raise ValueError('Colore JR non valido.')
    photo_html, page_bg = photo_layer(photo, frame)
    overlay = data_uri(asset_dir() / 'canva' / _meta()[color]['overlay'])
    return f'''<!doctype html><html><head><meta charset="utf-8"><style>
*{{margin:0;padding:0}}
html,body{{width:{DESIGN_W}px;height:{DESIGN_H}px;overflow:hidden;background:{page_bg}}}
img{{position:absolute}}
</style></head><body>
{photo_html}
<img src="{overlay}" style="left:0;top:0;width:{DESIGN_W}px;height:{DESIGN_H}px">
</body></html>'''


def render(ghost=False, **kwargs):
    if ghost:
        kwargs['photo'] = None
    return render_html(build_html(**kwargs), ghost=ghost)
