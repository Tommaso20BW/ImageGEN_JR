"""COMMENTO IG: foto del post a tutta pagina, leggermente scurita, con UN commento scelto in un
riquadro sfocato (foto profilo, nome, spunta, tempo, testo, "Rispondi", cuore e mi piace).

Due formati: 3:4 e storia 9:16 (nella storia la parte bassa sfuma leggermente verso il nero).
Il riquadro si mette sotto (default), al centro o sopra, in base alla foto.
"""
import io
import json

from graphics.common import DESIGN_H, DESIGN_W, STORY_H, esc, photo_layer, render_html, story_jr_paste
from graphics.ig_quote import (ICON_LIKE, IG_GRADIENT, TICK_PATH, _font_css, _uri, clean_name, clean_text)
from graphics.starting_xi import check_photo

DARKEN = .64                     # luminosità della foto (1 = com'è)
POSITIONS = ('sotto', 'centro', 'sopra')
DEFAULT_POSITION = 'sotto'
MAX_TEXT = 300
MAX_BOX = 460                    # altezza massima del riquadro: il testo lungo si rimpicciolisce
FS_MAX, FS_MIN = 44, 26
# Distanza del riquadro dal bordo (pixel design), per formato.
EDGE = {False: {'sopra': 130, 'sotto': 240}, True: {'sopra': 270, 'sotto': 440}}


def clean_position(value):
    return value if value in POSITIONS else DEFAULT_POSITION


def clean_short(value, limit):
    return ' '.join(str(value or '').split())[:limit]


def _place(position, story):
    if position == 'centro':
        return 'top:50%;transform:translateY(-50%)'
    side = 'top' if position == 'sopra' else 'bottom'
    return f'{side}:{EDGE[story][position]}px'


SCRIPT = '''
const C = %s;
window.__ready = (async () => {
  try { await document.fonts.load('500 44px Poppins'); } catch (e) {}
  for (const img of document.images) { try { await img.decode(); } catch (e) {} }
  const box = document.getElementById('box'), txt = document.getElementById('t');
  let fs = C.max;
  while (fs > C.min && box.getBoundingClientRect().height > C.box) {
    fs -= 1; txt.style.fontSize = fs + 'px'; txt.style.lineHeight = Math.round(fs * 1.1) + 'px';
  }
})();
'''


def build_html(*, photo, text='', name='', avatar=None, frame=None, verified=False, time='', likes='',
               position=DEFAULT_POSITION, story=False):
    """photo=None: sagoma per l'editor (sfondo trasparente, la foto la mette la Mini App)."""
    if photo is not None:
        check_photo(photo)
    height = STORY_H if story else DESIGN_H
    img, _ = photo_layer(photo, frame or {'x': 0, 'y': 0, 'zoom': 1}, page=(DESIGN_W, height))
    from graphics.photo_jr import _logo
    name = clean_name(name)
    avatar_html = (f'<img id="av" src="{_uri(avatar)}">' if avatar
                   else f'<div id="av" class="none">{esc(name[:1].upper())}</div>')
    tick = (f'<svg class="tick" viewBox="0 0 24 24"><path fill="#0095F6" d="{TICK_PATH}"/><path fill="#fff" '
            'd="M10.6 16.2 6.9 12.5l1.4-1.4 2.3 2.3 5.1-5.1 1.4 1.4z"/></svg>' if verified else '')
    when = f'<span>{esc(clean_short(time, 12))}</span>' if clean_short(time, 12) else ''
    count = esc(clean_short(likes, 10))
    fade = '<div id="fade"></div>' if story else ''
    cfg = {'max': FS_MAX, 'min': FS_MIN, 'box': MAX_BOX}
    return f'''<!doctype html><html><head><meta charset="utf-8"><style>
{_font_css()}
*{{margin:0;padding:0;box-sizing:border-box}}
html,body{{width:{DESIGN_W}px;height:{height}px;overflow:hidden;background:{'#000' if photo is not None else 'transparent'}}}
#bg{{position:absolute;inset:0;overflow:hidden;filter:brightness({DARKEN})}}
#fade{{position:absolute;left:0;right:0;bottom:0;height:760px;background:linear-gradient(to bottom,rgba(0,0,0,0),rgba(0,0,0,.28) 45%,rgba(0,0,0,.62))}}
#box{{position:absolute;left:64px;right:64px;{_place(position, story)};display:flex;align-items:center;gap:28px;
  min-height:190px;padding:36px 38px;border-radius:30px;background:rgba(12,12,14,.38);border:1.5px solid rgba(255,255,255,.22);
  backdrop-filter:blur(28px) saturate(1.1);-webkit-backdrop-filter:blur(28px) saturate(1.1);box-shadow:0 14px 44px rgba(0,0,0,.22);
  text-shadow:0 1px 8px rgba(0,0,0,.4);color:#fff;font-family:'Poppins',sans-serif;font-weight:500}}
#av{{width:118px;height:118px;flex:none;display:block;border-radius:50%;object-fit:cover;object-position:center;padding:4px;background:{IG_GRADIENT}}}
#av.none{{display:grid;place-items:center;font-size:46px}}
#m{{flex:1;min-width:0;min-height:118px;display:flex;flex-direction:column;justify-content:center;gap:6px}}
#n{{display:flex;align-items:center;gap:10px;height:32px;line-height:32px;font-size:30px;min-width:0}}
#n b{{font-weight:500;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;min-width:0}}
.tick{{width:30px;height:30px;flex:none}}
#n span{{opacity:.8;font-size:27px;margin-left:6px;flex:none}}
#t{{font-size:{FS_MAX}px;line-height:48px;white-space:pre-wrap;overflow-wrap:anywhere}}
#r{{font-size:25px;line-height:26px;height:26px;color:rgba(255,255,255,.78)}}
#l{{flex:none;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:8px;font-size:27px;line-height:30px}}
#l svg{{width:50px;height:50px;display:block}}
body>img{{position:absolute}}
img[style*="left:0"]{{position:absolute}}
</style></head><body>
<div id="bg">{img}</div>{fade}
<div id="box">{avatar_html}<div id="m"><div id="n"><b>{esc(name)}</b>{tick}{when}</div><div id="t">{esc(text)}</div><div id="r">Rispondi</div></div><div id="l">{ICON_LIKE}{count}</div></div>
{'' if story else _logo('white')}
<script>{SCRIPT % json.dumps(cfg)}</script>
</body></html>'''


def render(*, photo, text='', name='', avatar=None, frame=None, ghost=False, verified=False, time='', likes='',
           position=DEFAULT_POSITION, story=False, **_):
    text = clean_text(text)[:MAX_TEXT]
    story = bool(story) and not ghost            # l'editor della foto lavora sul 3:4
    markup = build_html(photo=None if ghost else photo, text=text, name=name, avatar=avatar, frame=frame,
                        verified=verified, time=time, likes=likes, position=clean_position(position), story=story)
    if not story:
        return render_html(markup, ghost=ghost)
    from PIL import Image
    image = Image.open(io.BytesIO(render_html(markup, page=(DESIGN_W, STORY_H)))).convert('RGB')
    story_jr_paste(image, (255, 255, 255))
    out = io.BytesIO()
    image.save(out, 'PNG')
    return out.getvalue()
