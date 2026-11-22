"""PLAYER OF THE MONTH: sfondo grigio chiaro sfumato, foto intera in bianco e nero (un po' sfocata)
dentro un rettangolo con ombra, giocatore scontornato sopra che esce dal rettangolo (mani dentro
PLAYER, piedi sotto) con ombra leggera solo dove esce. PLAYER e MONTH grandi in oro, OF e THE neri,
linee verticali con le tre stelle, mese a sinistra e nome a destra in verticale, grana su tutto.
L'utente carica la foto intera: lo scontornato è della stessa misura e sta allineato."""
import io
import math

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageEnhance, ImageFilter, ImageOps

from graphics import motm as M

W, H = M.W, M.H
TITLE_FONT, SMALL_FONT = 'DharmaGothicEBold.otf', 'Inter-Medium.ttf'
TITLE_SQUEEZE = 1          # titoli stretti e alti come nel riferimento
SMALL_TITLE_H = round(H * .03)      # OF e THE: stessa altezza, OF in cima a PLAYER e THE in fondo a MONTH
TITLE_BOLD = 0            # quanto ingrossare il tratto dei titoli (in proporzione all'altezza)
GOLD, INK, LINE_INK = (190, 152, 82), (16, 16, 16), (40, 40, 40)
FRAME = (.161, .138, .869, .889)           # rettangolo della foto (frazioni di W e H)
PLAYER_FILL, PLAYER_TOP = 1.13, -.07       # giocatore più alto del rettangolo: esce sopra e sotto
MONTH_MAX = 30                             # "AGOSTO/SETTEMBRE"
PHOTO_DARK, PHOTO_GRAIN = .72, 16          # foto nel rettangolo: luminosità e grana in più
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


def _title(txt, height, fill, gap):
    """Titolo alto e stretto: Bebas schiacciato in larghezza, lettere distanziate di gap pixel."""
    t = _text(txt, _fit_h(txt, TITLE_FONT, height), fill, spacing=round(gap / TITLE_SQUEEZE))
    if TITLE_SQUEEZE == 1 and not TITLE_BOLD:
        return t
    t = t.resize((round(t.width * TITLE_SQUEEZE), t.height), Image.LANCZOS)
    k = max(3, round(height * TITLE_BOLD) | 1)                     # tratto più pieno, come nel riferimento
    a = t.getchannel('A').filter(ImageFilter.MaxFilter(k)).filter(ImageFilter.GaussianBlur(.6))
    out = Image.new('RGBA', t.size, tuple(fill) + (0,))
    out.putalpha(a)
    return out


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
    # facce di luce spigolose come nel riferimento: piani appena più chiari o più scuri, bordi netti
    m = Image.new('L', (W, H), 128)
    d = ImageDraw.Draw(m)
    for pts, tone in (([(.42, 0), (.62, .055), (.80, 0)], 140),                 # punta chiara in alto
                      ([(.62, .055), (1, .17), (1, 0), (.80, 0)], 136),
                      ([(0, .50), (.20, .58), (0, .70)], 137),                  # cuneo a sinistra
                      ([(0, .70), (.20, .58), (.32, .66), (0, .86)], 122),
                      ([(1, .45), (.84, .55), (1, .62)], 121)):                # cuneo scuro a destra
        d.polygon([(x * W, y * H) for x, y in pts], fill=tone)
    v = v + (np.asarray(m.filter(ImageFilter.GaussianBlur(2))).astype(np.float32) - 128)
    return Image.fromarray(np.uint8(np.repeat(v[..., None], 3, 2))).convert('RGBA'), v


def _star(d, cx, cy, r, fill):
    pts = [(cx + (r if k % 2 == 0 else r * .42) * math.sin(k * math.pi / 5),
            cy - (r if k % 2 == 0 else r * .42) * math.cos(k * math.pi / 5)) for k in range(10)]
    d.polygon(pts, fill=fill)


def _side_line(d, x, y0, y1, stars_at):
    d.line((x, y0, x, y1), fill=LINE_INK, width=4)
    for k in range(3):                                         # le tre stelle
        _star(d, x, stars_at + (k - 1) * 30, 11, GOLD)


def _photo_layers(photo, cut, frame_box):
    """Foto in B/N dentro il rettangolo e giocatore tutto a colori sopra, stesso taglio."""
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
    bw = ImageEnhance.Contrast(bw).enhance(1.15).filter(ImageFilter.GaussianBlur(3))
    bw = ImageEnhance.Brightness(bw).enhance(PHOTO_DARK)                        # foto più scura
    g = np.asarray(bw).astype(np.float32)
    g += np.random.default_rng(7).normal(0, PHOTO_GRAIN, g.shape).astype(np.float32)   # più grana solo sulla foto
    bw = Image.fromarray(np.uint8(np.clip(g, 0, 255))).convert('RGBA')
    lay = Image.new('RGBA', (W, H), (0, 0, 0, 0)); lay.alpha_composite(bw, (ox, oy))
    cl = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    cl.alpha_composite(cut.convert('RGBA').resize((pw, ph), Image.LANCZOS), (ox, oy))   # giocatore tutto a colori
    return lay, cl


def _out_shadow(cl, frame_m):
    """Ombra leggera dietro la parte che esce dal rettangolo + ombra a terra sotto i piedi."""
    out_m = ImageOps.invert(frame_m)
    sh = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    sh.putalpha(ImageChops.multiply(cl.getchannel('A'), out_m).point(lambda v: v * .32))
    sh = sh.filter(ImageFilter.GaussianBlur(10))
    shl = Image.new('RGBA', (W, H), (0, 0, 0, 0)); shl.alpha_composite(sh, (10, 12))
    shl.putalpha(ImageChops.multiply(shl.getchannel('A'), out_m))
    g = _ground_shadow(np.asarray(cl.getchannel('A')) > 60)
    if g is not None:
        shl.putalpha(ImageChops.lighter(shl.getchannel('A'), g))
    return shl


GROUND_SHADOW = (.45, .18)   # forza: contatto (stretta, sotto i punti d'appoggio), alone (larga e chiara)


def _ground_shadow(solid):
    """Ombra a terra solo dove il giocatore tocca (o quasi) il pavimento: più scura dove appoggia,
    più chiara dove resta sollevato, e sfuma da sola ai lati."""
    from scipy.ndimage import gaussian_filter
    has = solid.any(0)
    if not has.any():
        return None
    low = H - 1 - np.argmax(solid[::-1], 0)           # punto più basso di ogni colonna
    ground = low[has].max()
    near = np.where(has, np.exp(-((ground - low) / 30) ** 2), 0).astype(np.float32)
    core_x = gaussian_filter(near, 10)
    halo_x = gaussian_filter(near, 46)
    halo_x /= max(halo_x.max(), 1e-6)
    d = np.arange(H, dtype=np.float32) - ground
    core = np.exp(-.5 * ((d - 1) / 6) ** 2)[:, None] * core_x[None] * GROUND_SHADOW[0]
    halo = np.exp(-.5 * ((d - 7) / 19) ** 2)[:, None] * halo_x[None] * GROUND_SHADOW[1]
    sh = 1 - (1 - core) * (1 - halo)
    return Image.fromarray(np.uint8(np.clip(sh, 0, 1) * 255 + .5))


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
    t1 = _title('PLAYER', round(H * .152), GOLD, W * .006)
    _place(img, t1, W * .116, H * .04)
    # OF in alto allineato all'inizio di PLAYER (come nel riferimento)
    _place(img, _title('OF', SMALL_TITLE_H, INK, 4), W * .116 + t1.width + W * .022, H * .04 + 2)   # 2 px più in basso
    if cl is not None:
        img.alpha_composite(shl)
        img.alpha_composite(cl)
    # MONTH oro in basso a destra (davanti al giocatore), THE nero
    t2 = _title('MONTH', round(H * .152), GOLD, W * .006)
    mx = fx1 + W * .035                   # MONTH esce un po' a destra del rettangolo, come PLAYER a sinistra
    _place(img, t2, mx, H * .95, 'rb')
    _place(img, _title('THE', SMALL_TITLE_H, INK, 4), mx - t2.width - W * .022, H * .95 - 2, 'rb')   # 2 px più in alto

    # come il riferimento: ogni scritta parte dal bordo del rettangolo (mese a sinistra finisce sul
    # bordo in basso, nome a destra parte dal bordo in alto) e la linea con le stelle continua da lì
    d = ImageDraw.Draw(img)
    gap = round(W * .022)
    lx, rx = fx0 - gap, fx1 + gap
    small = M._font(SMALL_FONT, round(H * .016))
    who = ' '.join(p for p in (name.upper(), surname) if p)

    def side(txt, rot):
        sp = round(H * .006)               # spazio tra le lettere delle scritte laterali
        while True:                       # lettere larghe come nel riferimento, ma mai oltre metà pagina
            t = _text(txt, small, LINE_INK, spacing=sp).rotate(rot, expand=True)
            if t.height <= H * .45 or sp <= 2:
                return t
            sp -= 1

    sep = round(H * .026)                 # spazio tra scritta e linea
    inset = round(H * .008)               # la scritta parte poco dentro il bordo
    tm = side(month, 90)
    _place(img, tm, lx, fy1 - inset, 'mb')
    _side_line(d, lx, H * .26, fy1 - inset - tm.height - sep, H * .26 - 52)
    tw = side(who, -90)
    _place(img, tw, rx, fy0 + inset, 'mt')
    _side_line(d, rx, fy0 + inset + tw.height + sep, H * .69, H * .69 + 52)

    # grana su tutto (sfondo e giocatore), poi il logo JR
    a = np.asarray(img.convert('RGB')).astype(np.float32)
    a += np.random.default_rng(1).normal(0, 9, a.shape[:2]).astype(np.float32)[..., None]
    out = np.clip(a / 255, 0, 1)
    jr = M._jr_logo()
    out = out * (1 - jr[..., 3:]) + jr[..., :3] * jr[..., 3:]
    buf = io.BytesIO()
    Image.fromarray(np.uint8(out * 255 + .5)).save(buf, 'PNG')
    return buf.getvalue()
