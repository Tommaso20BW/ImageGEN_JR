"""STORIE IG - Breaking News (1080x1920, uscita 1440x2560).

Lo sfondo (asset privati: canva/ig_breaking_news_bg.jpg) ha già in alto la scritta BREAKING NEWS e in basso
il logo JR: tra i due resta una zona libera dove si mette il contenuto scelto nella Mini App:

- solo testo:   il testo più grande possibile che sta nella zona, centrato;
- solo foto:    la foto più grande possibile che sta nella zona (proporzioni intatte), centrata;
- testo + foto: testo sopra e foto sotto. Il testo parte grande e si rimpicciolisce finché alla
                foto resta almeno metà della zona (o l'altezza che ha a tutta larghezza, se minore);
                la foto occupa lo spazio rimasto. Il gruppo è centrato nella zona.

Il calcolo delle altezze lo fa Chrome (testo e a-capo reali) con uno script nella pagina: il
renderer aspetta `window.__ready` prima di scattare (vedi graphics/common.py).

Font: Poppins Medium, dagli asset privati (fonts/Poppins-Medium.ttf).
"""
import base64
import json
import re

from graphics.common import asset_dir, data_uri, esc, render_html
from graphics.starting_xi import check_photo

PAGE_W, PAGE_H = 1080, 1920          # pixel design della storia
OUT_W = 1440                         # uscita 1440x2560 (come lo sfondo originale 1428x2560)

BG_NAME = 'ig_breaking_news_bg.jpg'     # negli asset privati: canva/ig_breaking_news_bg.jpg
BG_SIZE = (1428, 2560)               # pixel dello sfondo originale
# Misurati sullo sfondo originale (pixel dell'immagine): fondo della scritta BREAKING NEWS,
# inizio del logo JR (le stelle) e margini sinistro/destro della scritta.
LABEL_BOTTOM = 479
LOGO_TOP = 2181
LABEL_X = (97, 1330)

GAP_TOP = 60          # tra la scritta e il contenuto (pixel design)
GAP_BOTTOM = 60       # tra il contenuto e il logo
GAP_MIDDLE = 44       # tra testo e foto
IMG_MIN_SHARE = 0.5   # alla foto va almeno questa parte della zona (con testo + foto)
FS_WITH_PHOTO = (88, 36)   # (massimo, minimo) del testo quando c'è anche la foto
FS_SOLO = (140, 30)        # (massimo, minimo) del testo da solo
LINE_HEIGHT = 1.22
TEXT_COLOR = '#1a1612'
PHOTO_RADIUS = 22
MAX_TEXT = 500
FONT_FILE = 'Poppins-Medium.ttf'


def clean_text(value):
    """Testo scelto nella Mini App: a-capo mantenuti, righe vuote di fila ridotte a una."""
    text = str(value or '').replace('\r\n', '\n').replace('\r', '\n')
    lines = [' '.join(line.split()) for line in text.split('\n')]
    text = re.sub(r'\n{3,}', '\n\n', '\n'.join(lines)).strip()
    if len(text) > MAX_TEXT:
        raise ValueError(f'Testo troppo lungo (massimo {MAX_TEXT} caratteri).')
    return text


def background_map():
    """Sfondo a pagina piena (stesso ritaglio di `cover`) e zona libera, in pixel design.
    Ritorna (x, y, w, h dell'immagine, (zx, zy, zw, zh) della zona)."""
    iw, ih = BG_SIZE
    scale = max(PAGE_W / iw, PAGE_H / ih)
    w, h = iw * scale, ih * scale
    x, y = (PAGE_W - w) / 2, (PAGE_H - h) / 2
    left = x + LABEL_X[0] * scale
    right = x + LABEL_X[1] * scale
    top = y + LABEL_BOTTOM * scale + GAP_TOP
    bottom = y + LOGO_TOP * scale - GAP_BOTTOM
    return (x, y, w, h), (left, top, right - left, bottom - top)


def _font_css():
    """@font-face di Poppins Medium dagli asset privati (fonts/Poppins-Medium.ttf, lo stesso
    della Probabile XI). Dichiarato come peso 500: niente grassetto finto."""
    return (f"@font-face{{font-family:'Poppins';font-weight:500;font-style:normal;"
            f"src:url({data_uri(asset_dir() / 'fonts' / FONT_FILE)})}}")


def _uri(raw):
    mime = 'image/png' if raw.startswith(b'\x89PNG') else 'image/jpeg'
    return f'data:{mime};base64,' + base64.b64encode(raw).decode('ascii')


# Script di layout: parte quando Poppins è caricato e mette in `window.__ready` la promessa che il
# renderer aspetta. Tutte le misure arrivano da Python in `CFG`.
SCRIPT = '''
const C = %s;
window.__ready = (async () => {
  try { await document.fonts.load('500 80px Poppins'); } catch (e) {}
  const text = document.getElementById('txt'), pic = document.getElementById('pic');
  const W = C.zone[2], H = C.zone[3];
  const th = fs => { text.style.fontSize = fs + 'px'; return text.getBoundingClientRect().height; };
  const fit = (max, min, room) => { let fs = max; while (fs > min && th(fs) > room()) fs -= 1; th(fs); return fs; };
  let ph = 0, pw = 0;
  if (pic) {
    await pic.decode();
    const ar = pic.naturalHeight / pic.naturalWidth;
    if (text) {
      const want = Math.min(W * ar, H * C.share);
      fit(C.withPhoto[0], C.withPhoto[1], () => H - C.gap - want);
      ph = Math.min(W * ar, H - text.getBoundingClientRect().height - C.gap);
    } else {
      ph = Math.min(W * ar, H);
    }
    pw = ph / ar;
    pic.style.width = pw + 'px'; pic.style.height = ph + 'px';
  } else {
    fit(C.solo[0], C.solo[1], () => H);
  }
  document.body.dataset.ready = '1';
})();
'''


def build_html(*, text='', photo=None):
    text = clean_text(text)
    if not text and photo is None:
        raise ValueError('Scrivi un testo o scegli una foto.')
    if photo is not None:
        check_photo(photo)
    (bx, by, bw, bh), (zx, zy, zw, zh) = background_map()
    cfg = {'zone': [zx, zy, zw, zh], 'gap': GAP_MIDDLE, 'share': IMG_MIN_SHARE,
           'withPhoto': FS_WITH_PHOTO, 'solo': FS_SOLO}
    body = ''
    if text:
        body += f'<div id="txt">{esc(text)}</div>'
    if photo is not None:
        body += f'<img id="pic" src="{_uri(photo)}">'
    return f'''<!doctype html><html><head><meta charset="utf-8"><style>
{_font_css()}
*{{margin:0;padding:0;box-sizing:border-box}}
html,body{{width:{PAGE_W}px;height:{PAGE_H}px;overflow:hidden;background:#f3eee6}}
#bg{{position:absolute;left:{bx}px;top:{by}px;width:{bw}px;height:{bh}px}}
#zone{{position:absolute;left:{zx}px;top:{zy}px;width:{zw}px;height:{zh}px;display:flex;
  flex-direction:column;align-items:center;justify-content:center;gap:{GAP_MIDDLE}px}}
#txt{{width:100%;text-align:center;white-space:pre-wrap;overflow-wrap:anywhere;text-wrap:balance;
  font-family:'Poppins',sans-serif;font-weight:500;line-height:{LINE_HEIGHT};letter-spacing:-0.01em;
  color:{TEXT_COLOR};font-size:60px;flex:none}}
#pic{{display:block;flex:none;border-radius:{PHOTO_RADIUS}px;box-shadow:0 14px 40px rgba(60,45,20,.22)}}
</style></head><body>
<img id="bg" src="{data_uri(asset_dir() / "canva" / BG_NAME)}">
<div id="zone">{body}</div>
<script>{SCRIPT % json.dumps(cfg)}</script>
</body></html>'''


def render(*, text='', photo=None):
    return render_html(build_html(text=text, photo=photo), page=(PAGE_W, PAGE_H), out_w=OUT_W)
