"""PLAYER OF THE MONTH: sfondo grigio chiaro sfumato, foto intera in bianco e nero (un po' sfocata)
dentro un rettangolo con ombra, giocatore scontornato sopra che esce dal rettangolo (mani dentro
PLAYER, piedi sotto) con ombra leggera solo dove esce. PLAYER e MONTH grandi in oro, OF e THE neri,
linee verticali con le tre stelle, mese a sinistra e nome a destra in verticale, grana su tutto.
L'utente carica la foto intera: lo scontornato è della stessa misura e sta allineato."""
import io
import math

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageEnhance, ImageFilter, ImageOps
from scipy.ndimage import binary_dilation, gaussian_filter

from graphics import motm as M

W, H = M.W, M.H
TITLE_FONT, SMALL_FONT = 'DharmaGothicEBold.otf', 'Teko-Regular.ttf'
GOLD, INK, LINE_INK = (190, 152, 82), (16, 16, 16), (40, 40, 40)
FRAME = (.161, .138, .869, .889)           # rettangolo della foto (frazioni di W e H)
PLAYER_FILL, PLAYER_TOP = 1.13, -.07       # giocatore più alto del rettangolo: esce sopra e sotto
MONTH_MAX = 30                             # "AGOSTO/SETTEMBRE"
# ordine della stagione: più mesi si scrivono in quest'ordine, separati da "/"
MONTHS = ['AGOSTO', 'SETTEMBRE', 'OTTOBRE', 'NOVEMBRE', 'DICEMBRE', 'GENNAIO',
          'FEBBRAIO', 'MARZO', 'APRILE', 'MAGGIO', 'GIUGNO', 'LUGLIO']


def clean_month(value):
    """Mese o mesi: lista o testo con "/" -> "AGOSTO/SETTEMBRE" (in ordine di stagione, senza doppi).
    Un testo che non è un mese resta com'è (scritto a mano)."""
    parts = value if isinstance(value, (list, tuple)) else str(value or '').split('/')
    parts = [M.clean_text(p, MONTH_MAX) for p in parts]
    parts = [p for p in parts if p]
    if parts and all(p in MONTHS for p in parts):
        parts = sorted(set(parts), key=MONTHS.index)
    return M.clean_text('/'.join(parts), MONTH_MAX)


# ---------------------------------------------------------------- testo

def _text(txt, f, fill, spacing=0):
    """Scritta su livello trasparente, ritagliata stretta, con spaziatura tra le lettere."""
    d = ImageDraw.Draw(Image.new('L', (1, 1)))
    ws = [d.textlength(c, font=f) for c in txt]
    asc, desc = f.getmetrics()
    lay = Image.new('RGBA', (int(sum(ws) + spacing * len(txt) + 40), asc + desc + 40), (0, 0, 0, 0))
    dr = ImageDraw.Draw(lay)
    x = 20
    for c, cw in zip(txt, ws):
        dr.text((x, 20), c, font=f, fill=fill)
        x += cw + spacing
    box = lay.getbbox()
    return lay.crop(box) if box else lay


def _fit_h(txt, name, height):
    """Font con altezza delle lettere = height."""
    lo, hi = 10, 2000
    while hi - lo > 1:
        mid = (lo + hi) // 2
        if _text(txt, M._font(name, mid), 'white').height > height:
            hi = mid
        else:
            lo = mid
    return M._font(name, lo)


def _place(base, lay, x, y, anchor='lt'):
    x -= {'l': 0, 'm': lay.width // 2, 'r': lay.width}[anchor[0]]
    y -= {'t': 0, 'm': lay.height // 2, 'b': lay.height}[anchor[1]]
    base.alpha_composite(lay, (int(round(x)), int(round(y))))


# ---------------------------------------------------------------- parti

def _background():
    """Grigio chiaro sfumato: luce morbida in alto a sinistra."""
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    r = np.hypot((xx - W * .25) / W, (yy - H * .2) / H)
    v = 246 - np.clip(r, 0, 1.1) * 34
    return Image.fromarray(np.uint8(np.repeat(v[..., None], 3, 2))).convert('RGBA'), v


def _skin_bw(c):
    """Viso, braccia e gambe in bianco e nero; maglia e scarpini restano a colori."""
    hsv = np.asarray(c.convert('RGB').convert('HSV')).astype(np.float32)
    hh, ss, vv = hsv[..., 0], hsv[..., 1], hsv[..., 2]
    skin = binary_dilation(((hh <= 38) | (hh >= 235)) & (ss > 22) & (vv > 25), iterations=3)
    sm = np.clip(gaussian_filter(skin.astype(np.float32), 2.5) * 1.4, 0, 1)[..., None]
    rgb = np.asarray(c.convert('RGB')).astype(np.float32)
    grey = (rgb @ np.array([.299, .587, .114], np.float32))[..., None]
    out = Image.fromarray(np.uint8(np.clip(rgb * (1 - sm) + grey * sm, 0, 255))).convert('RGBA')
    out.putalpha(c.getchannel('A'))
    return out


def _star(d, cx, cy, r, fill):
    pts = [(cx + (r if k % 2 == 0 else r * .42) * math.sin(k * math.pi / 5),
            cy - (r if k % 2 == 0 else r * .42) * math.cos(k * math.pi / 5)) for k in range(10)]
    d.polygon(pts, fill=fill)


def _side_line(d, x, y0, y1, stars_at):
    d.line((x, y0, x, y1), fill=LINE_INK, width=3)
    for k in range(3):                                         # le tre stelle
        _star(d, x, stars_at + (k - 1) * 30, 11, GOLD)


def _photo_layers(photo, cut, frame_box):
    """Foto in B/N dentro il rettangolo e livello del giocatore a colori, stesso taglio."""
    fx0, fy0, fx1, fy1 = frame_box
    fw, fh = fx1 - fx0, fy1 - fy0
    if cut.size != photo.size:
        cut = cut.resize(photo.size, Image.LANCZOS)
    box = cut.getchannel('A').point(lambda v: 255 if v > 40 else 0).getbbox()
    if box is None:
        raise ValueError('Nella foto non trovo nessuna persona.')
    bx0, by0, bx1, by1 = box
    sc = max(fw / photo.width, fh / photo.height, fh * PLAYER_FILL / (by1 - by0))
    pw, ph = round(photo.width * sc), round(photo.height * sc)
    ox = round(fx0 + fw / 2 - (bx0 + bx1) / 2 * sc)
    oy = round(fy0 + fh * PLAYER_TOP - by0 * sc)
    ox, oy = min(fx0, max(fx1 - pw, ox)), min(fy0, max(fy1 - ph, oy))   # la foto copre sempre il rettangolo
    bw = ImageOps.grayscale(photo.convert('RGB').resize((pw, ph), Image.LANCZOS))
    bw = ImageEnhance.Contrast(bw).enhance(1.15).filter(ImageFilter.GaussianBlur(3)).convert('RGBA')
    lay = Image.new('RGBA', (W, H), (0, 0, 0, 0)); lay.alpha_composite(bw, (ox, oy))
    cl = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    cl.alpha_composite(_skin_bw(cut.resize((pw, ph), Image.LANCZOS)), (ox, oy))
    return lay, cl


def _out_shadow(cl, frame_m):
    """Ombra leggera dietro la parte che esce dal rettangolo + ombra a terra sotto i piedi."""
    out_m = ImageOps.invert(frame_m)
    sh = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    sh.putalpha(ImageChops.multiply(cl.getchannel('A'), out_m).point(lambda v: v * .32))
    sh = sh.filter(ImageFilter.GaussianBlur(10))
    shl = Image.new('RGBA', (W, H), (0, 0, 0, 0)); shl.alpha_composite(sh, (10, 12))
    shl.putalpha(ImageChops.multiply(shl.getchannel('A'), out_m))
    a = np.asarray(cl.getchannel('A')) > 60
    rows = np.where(a.any(1))[0]
    if len(rows):
        foot = rows.max()
        xs = np.where(a[max(0, foot - int(H * .03)):foot + 1].any(0))[0]
        cx, half = (xs.min() + xs.max()) / 2, (xs.max() - xs.min()) / 2 * 1.3 + 25
        g = Image.new('L', (W, H), 0)
        ImageDraw.Draw(g).ellipse((cx - half, foot - 14, cx + half, foot + 16), fill=95)
        shl.putalpha(ImageChops.lighter(shl.getchannel('A'), g.filter(ImageFilter.GaussianBlur(12))))
    return shl


def _open(image):
    if isinstance(image, (bytes, bytearray)):
        from livescore.graphics import phase_layers
        return phase_layers.open_photo(bytes(image))
    return image.convert('RGBA')


def render(*, surname, name='', month='', person=None, photo=None, ghost=False, frame=None):
    """PNG del poster Player of the Month. person = scontornato (stessa misura di photo),
    photo = foto intera; senza photo lo sfondo è lo scontornato su grigio."""
    surname = M.clean_text(surname, M.SURNAME_MAX)
    name = M.clean_name(name)
    month = clean_month(month)
    if not surname:
        raise ValueError('Scrivi il cognome.')
    if not month:
        raise ValueError('Scrivi il mese.')
    if not ghost and person is None:
        raise ValueError('Carica la foto.')

    img, bg = _background()
    fx0, fy0, fx1, fy1 = [round(v * s) for v, s in zip(FRAME, (W, H, W, H))]
    frame_m = Image.new('L', (W, H), 0)
    ImageDraw.Draw(frame_m).rectangle((fx0, fy0, fx1 - 1, fy1 - 1), fill=255)
    fs = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(fs).rectangle((fx0, fy0, fx1, fy1), fill=(0, 0, 0, 90))
    img.alpha_composite(fs.filter(ImageFilter.GaussianBlur(14)), (6, 10))      # ombra del rettangolo
    if ghost:
        ImageDraw.Draw(img).rectangle((fx0, fy0, fx1 - 1, fy1 - 1), fill=(120, 120, 120, 255))
        cl = shl = None
    else:
        cut = _open(person)
        if photo is None:
            photo = Image.new('RGBA', cut.size, (128, 128, 128, 255))
            photo.alpha_composite(cut)
        lay, cl = _photo_layers(_open(photo), cut, (fx0, fy0, fx1, fy1))
        lay.putalpha(ImageChops.multiply(lay.getchannel('A'), frame_m))
        img.alpha_composite(lay)
        shl = _out_shadow(cl, frame_m)

    # PLAYER oro in alto (dietro al giocatore), OF nero
    f = _fit_h('PLAYER', TITLE_FONT, round(H * .152))
    t1 = _text('PLAYER', f, GOLD, spacing=round(W * .006))
    _place(img, t1, W * .119, H * .028)
    sf = _fit_h('OF', TITLE_FONT, round(H * .028))
    _place(img, _text('OF', sf, INK, spacing=4), W * .119 + t1.width + W * .022, H * .040)
    if cl is not None:
        img.alpha_composite(shl)
        img.alpha_composite(cl)
    # MONTH oro in basso a destra (davanti al giocatore), THE nero
    t2 = _text('MONTH', f, GOLD, spacing=round(W * .006))
    _place(img, t2, fx1, H * .962, 'rb')
    _place(img, _text('THE', sf, INK, spacing=4), fx1 - t2.width - W * .022, H * .962, 'rb')

    # linee con le tre stelle, mese a sinistra e nome a destra in verticale (fuori dal rettangolo)
    d = ImageDraw.Draw(img)
    gap = round(W * .042)
    lx, rx = fx0 - gap, fx1 + gap
    _side_line(d, lx, H * .30, H * .865, H * .30 - 52)
    _side_line(d, rx, H * .155, H * .72, H * .72 + 52)
    small = M._font(SMALL_FONT, round(H * .022))
    bgcol = lambda x, y: (int(bg[int(y), int(x)]),) * 3 + (255,)
    who = ' '.join(p for p in (name.upper(), surname) if p)
    for txt, x, y, rot in ((month, lx, H * .68, 90), (who, rx, H * .33, -90)):
        t = _text(txt, small, LINE_INK, spacing=round(H * .006)).rotate(rot, expand=True)
        _place(img, Image.new('RGBA', (t.width + 24, t.height + 30), bgcol(x, y)), x, y, 'mm')
        _place(img, t, x, y, 'mm')

    # grana su tutto (sfondo e giocatore), poi il logo JR
    a = np.asarray(img.convert('RGB')).astype(np.float32)
    a += np.random.default_rng(1).normal(0, 9, a.shape[:2]).astype(np.float32)[..., None]
    out = np.clip(a / 255, 0, 1)
    jr = M._jr_logo()
    out = out * (1 - jr[..., 3:]) + jr[..., :3] * jr[..., 3:]
    buf = io.BytesIO()
    Image.fromarray(np.uint8(out * 255 + .5)).save(buf, 'PNG')
    return buf.getvalue()
