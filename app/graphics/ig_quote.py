"""CITAZIONE IG: post Instagram in formato 3:4 (1080x1440 design, uscita 1920x2560).

- sfondo: una foto del post (scelta nella Mini App se sono più di una), a tutta pagina e scurita;
- logo JR bianco in alto a destra (lo stesso della FOTO + JR);
- al centro il testo del post, che si rimpicciolisce da solo se è lungo. Due stili:
  'card'  = dentro un riquadro scuro semitrasparente (quello scelto, il predefinito);
  'plain' = scritto direttamente sulla foto scurita;
- in basso, al centro, la foto profilo tonda e il nome dell'account.

Il calcolo della grandezza del testo lo fa Chrome (a-capo reali): il renderer aspetta `window.__ready`.
"""
import base64
import json

from graphics.common import DESIGN_H, DESIGN_W, asset_dir, data_uri, esc, photo_layer, render_html
from graphics.ig_story import FONT_FILE, tidy
from graphics.starting_xi import check_photo

STYLES = ('card', 'plain')
MAX_NAME = 40
# Zona del testo (pixel design): tra il logo in alto e la firma in basso.
ZONE = (110, 250, DESIGN_W - 220, 900)
FS_MAX, FS_MIN = 64, 16          # testo lungo: si rimpicciolisce fin qui (nessun limite di caratteri)
AVATAR = 92
SIGN_LEFT, SIGN_BOTTOM = 96, 92
CARD_BLUR = 5           # sfocatura della foto dietro il riquadro (px)
DARKEN = .52            # luminosità della foto di sfondo (1 = com'è)


def _uri(raw):
    mime = 'image/png' if raw.startswith(b'\x89PNG') else 'image/jpeg'
    return f'data:{mime};base64,' + base64.b64encode(raw).decode('ascii')


def _font_css():
    return (f"@font-face{{font-family:'Poppins';font-weight:500;font-style:normal;"
            f"src:url({data_uri(asset_dir() / 'fonts' / FONT_FILE)})}}")


def clean_text(value):
    """Testo della citazione: senza emoji, a-capo mantenuti, nessun limite di lunghezza."""
    return tidy(value)


def clean_name(value):
    name = ' '.join(str(value or '').split()).lstrip('@')
    return name[:MAX_NAME]


SCRIPT = '''
const C = %s;
window.__ready = (async () => {
  try { await document.fonts.load('500 60px Poppins'); } catch (e) {}
  for (const img of document.images) { try { await img.decode(); } catch (e) {} }
  const box = document.getElementById('box'), txt = document.getElementById('txt');
  if (txt) {
    const room = C.zone[3] - (C.card ? 2 * C.pad : 0);
    let fs = C.max;
    const set = v => { txt.style.fontSize = v + 'px'; txt.style.lineHeight = v >= 48 ? 1.24 : 1.32; };
    set(fs);
    while (fs > C.min && txt.getBoundingClientRect().height > room) { fs -= 1; set(fs); }
  }
})();
'''


def build_html(*, photo, text='', name='', avatar=None, style='card', frame=None):
    """photo=None: sagoma per l'editor (sfondo trasparente, la foto la mette la Mini App).
    frame = posizione e zoom della foto scelti nell'editor ({'x','y','zoom'}, come la FOTO + JR)."""
    if photo is not None:
        check_photo(photo)
    img, page_bg = photo_layer(photo, frame or {'x': 0, 'y': 0, 'zoom': 1})
    text = clean_text(text)
    name = clean_name(name)
    style = style if style in STYLES else 'card'
    from graphics.photo_jr import _logo
    zx, zy, zw, zh = ZONE
    card = style == 'card'
    pad = 56
    cfg = {'zone': list(ZONE), 'max': FS_MAX, 'min': FS_MIN, 'card': card, 'pad': pad}
    avatar_html = (f'<img id="av" src="{_uri(avatar)}">' if avatar
                   else f'<div id="av" class="none">{esc(name[:1].upper())}</div>')
    sign = (f'<div id="sign">{avatar_html}<div id="name">{esc(name)}</div></div>' if name or avatar else '')
    body = f'<div id="box"><div id="txt">{esc(text)}</div></div>' if text else ''
    return f'''<!doctype html><html><head><meta charset="utf-8"><style>
{_font_css()}
*{{margin:0;padding:0;box-sizing:border-box}}
html,body{{width:{DESIGN_W}px;height:{DESIGN_H}px;overflow:hidden;background:{'#000' if photo is not None else 'transparent'}}}
#bg{{position:absolute;inset:0;overflow:hidden;filter:brightness({DARKEN}) saturate(1.05)}}
#shade{{position:absolute;inset:0;background:linear-gradient(180deg,rgba(0,0,0,.28) 0%,rgba(0,0,0,0) 22%,
  rgba(0,0,0,0) 62%,rgba(0,0,0,.55) 100%)}}
#zone{{position:absolute;left:{zx}px;top:{zy}px;width:{zw}px;height:{zh}px;display:flex;
  align-items:center;justify-content:center}}
#box{{width:100%;max-height:100%;display:flex;align-items:center;justify-content:center;
  {f"padding:{pad}px;border-radius:30px;background:rgba(8,8,10,.46);border:1.5px solid rgba(255,255,255,.14);"
   f"backdrop-filter:blur({CARD_BLUR}px);-webkit-backdrop-filter:blur({CARD_BLUR}px);box-shadow:0 18px 60px rgba(0,0,0,.35);"
   if card else ""}}}
#txt{{width:100%;color:#fff;text-align:center;white-space:pre-wrap;overflow-wrap:anywhere;text-wrap:balance;
  font-family:'Poppins',sans-serif;font-weight:500;letter-spacing:-0.005em;font-size:60px;
  {"" if card else "text-shadow:0 2px 18px rgba(0,0,0,.55);"}}}
#sign{{position:absolute;left:{SIGN_LEFT}px;right:{SIGN_LEFT}px;bottom:{SIGN_BOTTOM}px;display:flex;
  align-items:center;justify-content:center;gap:22px}}
#av{{width:{AVATAR}px;height:{AVATAR}px;flex:none;border-radius:50%;object-fit:cover;
  border:3px solid #fff;box-shadow:0 6px 22px rgba(0,0,0,.4)}}
#av.none{{display:grid;place-items:center;background:#2a2a2e;color:#fff;font:500 40px Poppins}}
#name{{color:#fff;font-family:'Poppins',sans-serif;font-weight:500;font-size:36px;line-height:1.2;
  white-space:nowrap;overflow:hidden;text-overflow:ellipsis;text-shadow:0 2px 14px rgba(0,0,0,.5)}}
img[style*="left:0"]{{position:absolute}}
</style></head><body>
<div id="bg">{img}</div>
<div id="shade"></div>
<div id="zone">{body}</div>
{sign}
{_logo('white')}
<script>{SCRIPT % json.dumps(cfg)}</script>
</body></html>'''


def render(*, photo, text='', name='', avatar=None, style='card', frame=None, ghost=False):
    return render_html(build_html(photo=None if ghost else photo, text=text, name=name, avatar=avatar,
                                  style=style, frame=frame), ghost=ghost)
