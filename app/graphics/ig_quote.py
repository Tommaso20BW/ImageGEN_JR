"""CITAZIONE IG / X: post Instagram o X in formato 3:4 (1080x1440 design, uscita 1920x2560).

- sfondo: una foto del post (scelta nella Mini App se sono più di una), a tutta pagina e scurita,
  posizione e zoom scelti nell'editor;
- logo JR bianco in alto a destra (lo stesso della FOTO + JR);
- al centro un riquadro scuro semitrasparente fatto come un post di Instagram:
  in alto foto profilo (anello con i colori di Instagram), nome, "Instagram" e l'icona;
  poi il testo, allineato a sinistra, che si rimpicciolisce da solo se è lungo;
  in basso le icone di Instagram (mi piace, commenta, condividi; salva a destra).
  Il testo ha la stessa distanza dal nome sopra e dalle icone sotto.
- X (platform='x'): stesso riquadro; sotto il nome l'@account, logo X, icone di X
  (rispondi, ripubblica, mi piace, visualizzazioni; salva e condividi a destra). Se il post non ha
  foto lo sfondo è canva/x_quote_bg.jpg (lo aggiunge il servizio come foto da scegliere).

Il calcolo della grandezza del testo lo fa Chrome (a-capo reali): il renderer aspetta `window.__ready`.
"""
import base64
import json

from graphics.common import DESIGN_H, DESIGN_W, asset_dir, data_uri, esc, photo_layer, render_html
from graphics.ig_story import FONT_FILE, tidy
from graphics.starting_xi import check_photo

MAX_NAME = 40
# Zona del riquadro (pixel design): sotto il logo JR, il riquadro sta al centro e non la supera.
ZONE = (110, 200, DESIGN_W - 220, 1040)
FS_MAX, FS_MIN = 64, 16          # testo lungo: si rimpicciolisce fin qui (nessun limite di caratteri)
PAD = 56                         # margine interno del riquadro
TEXT_GAP = 68                    # distanza del testo dal nome (sopra) e dalle icone (sotto): uguale
AVATAR = 84
CARD_BLUR = 5                    # sfocatura della foto dietro il riquadro (px)
DARKEN = .52                     # luminosità della foto di sfondo (1 = com'è)
IG_GRADIENT = 'linear-gradient(45deg,#F58529,#DD2A7B 50%,#8134AF 80%,#515BD4)'

_S = 'fill="none" stroke="#fff" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"'
ICON_IG = (f'<svg viewBox="0 0 24 24" {_S}><rect x="3" y="3" width="18" height="18" rx="5"/>'
           '<circle cx="12" cy="12" r="4.2"/><circle cx="17.4" cy="6.6" r="1.1" fill="#fff" stroke="none"/></svg>')
ICON_LIKE = (f'<svg viewBox="0 0 24 24" {_S}><path d="M12 20.5s-7.5-4.6-9.3-9.3C1.4 7.6 3.6 4 7.1 4c2 0 3.6 1.1 '
             '4.9 2.9C13.3 5.1 14.9 4 16.9 4c3.5 0 5.7 3.6 4.4 7.2-1.8 4.7-9.3 9.3-9.3 9.3z"/></svg>')
ICON_COMMENT = f'<svg viewBox="0 0 24 24" {_S}><path d="M20.7 16.4A9 9 0 1 0 17.3 20l3.7 1-1-3.6z"/></svg>'
ICON_SHARE = f'<svg viewBox="0 0 24 24" {_S}><path d="M22 3 9.2 10.1M22 3l-7.5 18-5.3-10.9L2.2 6.5z"/></svg>'
X_SHARE = (f'<svg viewBox="0 0 24 24" {_S}><path d="M12 3v12M7.5 7.5 12 3l4.5 4.5"/>'
           '<path d="M4 14v5a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-5"/></svg>')
X_REPLY = (f'<svg viewBox="0 0 24 24" {_S}><path d="M4 11.5a7.5 7.5 0 0 1 7.5-7.5h1a7.5 7.5 0 0 1 0 15H9.5L5 22v-4.6'
           'A7.5 7.5 0 0 1 4 11.5z"/></svg>')
X_REPOST = (f'<svg viewBox="0 0 24 24" {_S}><path d="M4 9V7a3 3 0 0 1 3-3h11M15 1l3 3-3 3"/>'
            '<path d="M20 15v2a3 3 0 0 1-3 3H6M9 23l-3-3 3-3"/></svg>')
X_VIEWS = f'<svg viewBox="0 0 24 24" {_S}><path d="M5 20V12M10 20V5M15 20v-9M20 20V8"/></svg>'
X_LOGO = ('<svg viewBox="0 0 24 24"><path fill="#fff" d="M17.75 3h3.07l-6.7 7.66L22 21h-6.17l-4.83-6.32L5.47 21H2.4'
          'l7.17-8.2L2 3h6.33l4.37 5.77L17.75 3zm-1.08 16.17h1.7L7.4 4.73H5.58l11.09 14.44z"/></svg>')
ICON_SAVE = f'<svg viewBox="0 0 24 24" {_S}><path d="M19 21l-7-5-7 5V4a1 1 0 0 1 1-1h12a1 1 0 0 1 1 1z"/></svg>'


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
    from graphics.ig_story import strip_emoji
    name = ' '.join(strip_emoji(str(value or '')).split()).lstrip('@')
    return name[:MAX_NAME]


# Il testo si rimpicciolisce finché tutto il riquadro (nome, testo, icone) sta nella zona.
SCRIPT = '''
const C = %s;
window.__ready = (async () => {
  try { await document.fonts.load('500 60px Poppins'); } catch (e) {}
  for (const img of document.images) { try { await img.decode(); } catch (e) {} }
  const box = document.getElementById('box'), txt = document.getElementById('txt');
  if (box && txt) {
    let fs = C.max;
    const set = v => { txt.style.fontSize = v + 'px'; txt.style.lineHeight = v >= 48 ? 1.24 : 1.32; };
    set(fs);
    while (fs > C.min && box.getBoundingClientRect().height > C.zone[3]) { fs -= 1; set(fs); }
  }
})();
'''


def build_html(*, photo, text='', name='', avatar=None, frame=None, platform='ig', handle='', **_):
    """photo=None: sagoma per l'editor (sfondo trasparente, la foto la mette la Mini App).
    frame = posizione e zoom della foto scelti nell'editor ({'x','y','zoom'}, come la FOTO + JR)."""
    if photo is not None:
        check_photo(photo)
    img, _page_bg = photo_layer(photo, frame or {'x': 0, 'y': 0, 'zoom': 1})
    # Sfondo di X (già scuro, con i graffi): non si scurisce come le foto.
    darken = 1 if photo is not None and platform == 'x' and photo == x_background() else DARKEN
    text = clean_text(text)
    name = clean_name(name)
    from graphics.photo_jr import _logo
    zx, zy, zw, zh = ZONE
    cfg = {'zone': list(ZONE), 'max': FS_MAX, 'min': FS_MIN}
    avatar_html = (f'<img id="av" src="{_uri(avatar)}">' if avatar
                   else f'<div id="av" class="none">{esc(name[:1].upper())}</div>')
    x = platform == 'x'
    handle = clean_name(handle)
    sub = f'@{esc(handle)}' if x and handle else ('X' if x else 'Instagram')
    head = (f'<div id="hd">{avatar_html}<div id="who"><b>{esc(name or handle)}</b><span>{sub}</span></div>'
            f'<i id="ig">{X_LOGO if x else ICON_IG}</i></div>')
    if x:
        acts = (f'<div id="act"><div>{X_REPLY}{X_REPOST}{ICON_LIKE}{X_VIEWS}</div>'
                f'<div>{ICON_SAVE}{X_SHARE}</div></div>')
    else:
        acts = f'<div id="act"><div>{ICON_LIKE}{ICON_COMMENT}{ICON_SHARE}</div><div>{ICON_SAVE}</div></div>'
    body = f'<div id="box">{head}<div id="txt">{esc(text)}</div>{acts}</div>' if text else ''
    return f'''<!doctype html><html><head><meta charset="utf-8"><style>
{_font_css()}
*{{margin:0;padding:0;box-sizing:border-box}}
html,body{{width:{DESIGN_W}px;height:{DESIGN_H}px;overflow:hidden;background:{'#000' if photo is not None else 'transparent'}}}
#bg{{position:absolute;inset:0;overflow:hidden;filter:brightness({darken}) saturate(1.05)}}
#shade{{position:absolute;inset:0;background:linear-gradient(180deg,rgba(0,0,0,.28) 0%,rgba(0,0,0,0) 22%,
  rgba(0,0,0,0) 62%,rgba(0,0,0,.45) 100%)}}
#zone{{position:absolute;left:{zx}px;top:{zy}px;width:{zw}px;height:{zh}px;display:flex;
  align-items:center;justify-content:center}}
#box{{width:100%;display:flex;flex-direction:column;align-items:stretch;gap:{TEXT_GAP}px;padding:{PAD}px;
  border-radius:30px;background:rgba(8,8,10,.46);border:1.5px solid rgba(255,255,255,.14);
  backdrop-filter:blur({CARD_BLUR}px);-webkit-backdrop-filter:blur({CARD_BLUR}px);box-shadow:0 18px 60px rgba(0,0,0,.35)}}
#hd{{display:flex;align-items:center;gap:20px;color:#fff;font-family:'Poppins',sans-serif;flex:none}}
#av{{width:{AVATAR}px;height:{AVATAR}px;flex:none;border-radius:50%;object-fit:cover;
  {"border:3px solid rgba(255,255,255,.9)" if x else f"padding:4px;background:{IG_GRADIENT};background-clip:padding-box"}}}
#av.none{{display:grid;place-items:center;color:#fff;font:500 36px Poppins}}
#who{{min-width:0}}
#who b{{display:block;font-weight:500;font-size:34px;line-height:1.2;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}
#who span{{display:block;font-size:24px;line-height:1.3;opacity:.65}}
#ig{{margin-left:auto;flex:none;opacity:.9}}
#ig svg{{width:{40 if x else 44}px;height:{40 if x else 44}px;display:block}}
#txt{{width:100%;color:#fff;text-align:left;white-space:pre-wrap;overflow-wrap:anywhere;text-wrap:pretty;
  font-family:'Poppins',sans-serif;font-weight:500;letter-spacing:-0.005em;font-size:60px}}
#act{{display:flex;align-items:center;justify-content:space-between;flex:none}}
#act div{{display:flex;gap:{36 if x else 30}px}}
#act svg{{width:52px;height:52px;display:block}}
img[style*="left:0"]{{position:absolute}}
</style></head><body>
<div id="bg">{img}</div>
<div id="shade"></div>
<div id="zone">{body}</div>
{_logo('white')}
<script>{SCRIPT % json.dumps(cfg)}</script>
</body></html>'''


def render(*, photo, text='', name='', avatar=None, frame=None, ghost=False, platform='ig', handle='', **_):
    return render_html(build_html(photo=None if ghost else photo, text=text, name=name, avatar=avatar,
                                  frame=frame, platform=platform, handle=handle), ghost=ghost)


def x_background():
    """Sfondo per i post di X senza foto."""
    return (asset_dir() / 'canva' / 'x_quote_bg.jpg').read_bytes()
