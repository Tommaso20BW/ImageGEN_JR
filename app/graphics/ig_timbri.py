"""Timbri Juve sullo sfondo delle storie IG ("vedo non vedo").

Due timbri grandi e sbiaditi, stampati sulla carta prima di tutto il resto: uno in un angolo in
alto e l'altro nell'angolo opposto in basso, così non si toccano mai e restano lontani dal
contenuto al centro. Stile, posizione, grandezza e inclinazione cambiano con il seed (due stili
sempre diversi tra loro), con il seed uguale escono identici.

Stili: timbro postale tondo, francobollo dentellato, timbro ovale, annullo con le onde,
stella con la corona di scritte.
"""
import numpy as np
from PIL import Image, ImageDraw

from graphics import compleanno as cp

ANTON, MONO = cp.ANTON, cp.MONO
INK = np.array((0.07, 0.07, 0.075), np.float32)
STRENGTH = 0.10        # quanto si vedono (0 = niente, 1 = inchiostro pieno)


# ---------------------------------------------------------------- pezzi di disegno
def _star_pts(cx, cy, r, inner=.4, rot=0.0):
    return [(cx + (r if i % 2 == 0 else r * inner) * np.sin(i * np.pi / 5 + rot),
             cy - (r if i % 2 == 0 else r * inner) * np.cos(i * np.pi / 5 + rot)) for i in range(10)]


def _star(d, cx, cy, r, outline=0):
    pts = _star_pts(cx, cy, r)
    if outline:
        d.polygon(pts, outline=255, width=outline)
    else:
        d.polygon(pts, fill=255)


def _text(im, text, center, size, font=ANTON, tracking=0, angle=0.0):
    w = cp._word(text, size, font, tracking)
    if angle:
        w = w.rotate(angle, Image.BICUBIC, expand=True)
    im.paste(255, (int(center[0] - w.width / 2), int(center[1] - w.height / 2)), w)


def _arc(im, text, c, rr, size, start=0.0, font=MONO, gap=1.0, stars=True, flip=False):
    """Scritta lungo un cerchio di raggio rr, centrata su `start` (radianti, 0 = in alto).
    '*' nel testo diventa una stellina disegnata. flip: per le scritte in basso, che si leggono
    dritte (da sinistra a destra) invece che a testa in giù."""
    fnt = cp._font(font, size)
    widths = [size * .9 if ch == '*' else fnt.getlength(ch) * gap for ch in text]
    sgn = -1 if flip else 1
    a = start - sgn * sum(widths) / rr / 2
    d = ImageDraw.Draw(im)
    for ch, w in zip(text, widths):
        a += sgn * w / rr / 2
        x, y = c[0] + rr * np.sin(a), c[1] - rr * np.cos(a)
        if ch == '*':
            if stars:
                d.polygon(_star_pts(x, y, size * .38, rot=a), fill=255)
        elif ch != ' ':
            g = Image.new('L', (size * 2, size * 2), 0)
            ImageDraw.Draw(g).text((size, size), ch, font=fnt, fill=255, anchor='mm')
            g = g.rotate(-np.degrees(a) + (180 if flip else 0), Image.BICUBIC)
            im.paste(255, (int(x - size), int(y - size)), g)
        a += sgn * w / rr / 2


def _canvas(w, h):
    im = Image.new('L', (int(w), int(h)), 0)
    return im, ImageDraw.Draw(im)


# ---------------------------------------------------------------- i cinque stili
def _tondo(r, rng):
    """Timbro postale: doppio cerchio, scritte in giro, 1897 grande al centro."""
    im, d = _canvas(2 * r + 20, 2 * r + 20)
    c = (r + 10, r + 10)
    d.ellipse((c[0] - r, c[1] - r, c[0] + r, c[1] + r), outline=255, width=max(6, r // 28))
    d.ellipse((c[0] - r + r * .26, c[1] - r + r * .26, c[0] + r - r * .26, c[1] + r - r * .26),
              outline=255, width=3)
    words = ('* JUVENTUS * TORINO * BIANCONERI ', '* FINO ALLA FINE * JUVENTUS ')
    txt = words[int(rng.integers(len(words)))]
    fnt = cp._font(MONO, int(r * .17))
    span = sum(fnt.getlength(ch) for ch in txt)
    _arc(im, txt, c, r * .87, int(r * .17), gap=2 * np.pi * r * .87 / span)
    _text(im, '1897', c, int(r * .5), ANTON, 3)
    for s in (-1, 1):
        _star(d, c[0] + s * r * .52, c[1], r * .07)
    return im


def _francobollo(r, rng):
    """Francobollo dentellato: righe bianconere in alto, JUVENTUS e la stella sotto."""
    w, h = int(r * 1.5), int(r * 1.85)
    im, d = _canvas(w + 20, h + 20)
    x0, y0, x1, y1 = 10, 10, 10 + w, 10 + h
    d.rectangle((x0, y0, x1, y1), fill=255)
    hole, step = r * .045, r * .13
    for x in np.arange(x0, x1 + 1, (x1 - x0) / round((x1 - x0) / step)):
        for y in (y0, y1):
            d.ellipse((x - hole, y - hole, x + hole, y + hole), fill=0)
    for y in np.arange(y0, y1 + 1, (y1 - y0) / round((y1 - y0) / step)):
        for x in (x0, x1):
            d.ellipse((x - hole, y - hole, x + hole, y + hole), fill=0)
    m = r * .08                                       # cornice interna vuota
    ix0, iy0, ix1, iy1 = x0 + m, y0 + m, x1 - m, y1 - m
    d.rectangle((ix0, iy0, ix1, iy1), fill=0)
    d.rectangle((ix0, iy0, ix1, iy1), outline=255, width=4)
    band = (iy1 - iy0) * .45
    n = 7
    sw = (ix1 - ix0) / n
    for i in range(0, n, 2):
        d.rectangle((ix0 + i * sw, iy0, ix0 + (i + 1) * sw, iy0 + band), fill=255)
    sx, sy, sr = (ix0 + ix1) / 2, iy0 + band, r * .2
    d.ellipse((sx - sr, sy - sr, sx + sr, sy + sr), fill=0)
    d.ellipse((sx - sr, sy - sr, sx + sr, sy + sr), outline=255, width=3)
    _star(d, sx, sy, r * .13)
    _text(im, 'JUVENTUS', ((ix0 + ix1) / 2, iy0 + band + r * .38), int(r * .27), ANTON, 2)
    _text(im, 'TORINO 1897', ((ix0 + ix1) / 2, iy1 - r * .2), int(r * .14), MONO, 2)
    return im


def _ovale(r, rng):
    """Timbro ovale con FINO ALLA FINE al centro, tra due file di stelle."""
    w, h = int(r * 2.3), int(r * 1.45)
    im, d = _canvas(w + 20, h + 20)
    d.ellipse((10, 10, 10 + w, 10 + h), outline=255, width=max(6, r // 28))
    d.ellipse((10 + r * .1, 10 + r * .1, 10 + w - r * .1, 10 + h - r * .1), outline=255, width=3)
    c = (10 + w / 2, 10 + h / 2)
    top = ('FINO ALLA', 'BIANCONERI', 'TORINO')[int(rng.integers(3))]
    bottom = {'FINO ALLA': 'FINE', 'BIANCONERI': 'DAL 1897', 'TORINO': '1897'}[top]
    _text(im, top, (c[0], c[1] - r * .2), int(r * .3), ANTON, 3)
    _text(im, bottom, (c[0], c[1] + r * .2), int(r * .3), ANTON, 3)
    for i in range(5):
        dx = (i - 2) * r * .26
        _star(d, c[0] + dx, c[1] - r * .5, r * .055)
        _star(d, c[0] + dx, c[1] + r * .5, r * .055)
    return im


def _annullo(r, rng):
    """Annullo postale: cerchio con TORINO e la data, onde di annullamento a fianco."""
    cr = r * .72
    w = int(cr * 2 + r * 1.5)
    im, d = _canvas(w + 20, cr * 2 + 20)
    c = (10 + cr, 10 + cr)
    d.ellipse((c[0] - cr, c[1] - cr, c[0] + cr, c[1] + cr), outline=255, width=max(5, r // 32))
    _arc(im, 'JUVENTUS', c, cr * .78, int(cr * .22), gap=1.25)
    _arc(im, 'TORINO', c, cr * .78, int(cr * .22), start=np.pi, gap=1.25, flip=True)
    d.line((c[0] - cr * .62, c[1] - cr * .28, c[0] + cr * .62, c[1] - cr * .28), fill=255, width=3)
    d.line((c[0] - cr * .62, c[1] + cr * .28, c[0] + cr * .62, c[1] + cr * .28), fill=255, width=3)
    _text(im, '1 · XI · 1897', c, int(cr * .2), MONO, 1)
    ph = rng.uniform(0, np.pi)
    x = np.arange(c[0] + cr * .9, w + 10)
    for k in range(5):
        y = c[1] + (k - 2) * cr * .34 + np.sin((x - x[0]) / (r * .16) + ph) * r * .07
        d.line(list(zip(x, y)), fill=255, width=max(5, r // 30))
    return im


def _stella(r, rng):
    """Stella grande a contorno dentro una corona di scritte."""
    im, d = _canvas(2 * r + 20, 2 * r + 20)
    c = (r + 10, r + 10)
    d.ellipse((c[0] - r, c[1] - r, c[0] + r, c[1] + r), outline=255, width=3)
    d.ellipse((c[0] - r * .74, c[1] - r * .74, c[0] + r * .74, c[1] + r * .74), outline=255, width=3)
    fnt = cp._font(MONO, int(r * .15))
    txt = '* BIANCONERI * DAL 1897 * TORINO '
    span = sum(r * .15 * .9 if ch == '*' else fnt.getlength(ch) for ch in txt)
    _arc(im, txt, c, r * .87, int(r * .15), gap=2 * np.pi * r * .87 / span)
    d.polygon(_star_pts(c[0], c[1], r * .66, inner=.42), outline=255, width=max(6, r // 26))
    _text(im, 'JUVE', (c[0], c[1] + r * .03), int(r * .15), ANTON, 2)
    return im


STYLES = (_tondo, _francobollo, _ovale, _annullo, _stella)


# ---------------------------------------------------------------- sulla carta
def _place(dst, m, cx, cy, angle):
    m = m.rotate(angle, Image.BICUBIC, expand=True)
    a = np.asarray(m, np.float32) / 255
    h, w = a.shape
    H, W = dst.shape
    x, y = int(cx - w / 2), int(cy - h / 2)
    x0, y0, x1, y1 = max(x, 0), max(y, 0), min(x + w, W), min(y + h, H)
    if x1 > x0 and y1 > y0:
        dst[y0:y1, x0:x1] = np.maximum(dst[y0:y1, x0:x1], a[y0 - y:y1 - y, x0 - x:x1 - x])


def stamps_mask(size, seed):
    """Maschera (0..1) dei due timbri per una carta di `size` = (larghezza, altezza)."""
    W, H = size
    rng = np.random.default_rng(seed)
    first, second = rng.choice(len(STYLES), 2, replace=False)
    left_top = bool(rng.integers(2))          # diagonale: alto-sinistra/basso-destra o il contrario
    m = np.zeros((H, W), np.float32)
    for k, style in enumerate((first, second)):
        r = rng.uniform(.19, .23) * W         # grandi: circa 2/5 della larghezza
        left = left_top if k == 0 else not left_top
        cx = rng.uniform(.17, .27) * W
        cx = cx if left else W - cx
        cy = rng.uniform(.13, .2) * H if k == 0 else H - rng.uniform(.17, .24) * H
        _place(m, STYLES[style](int(r), rng), cx, cy, float(rng.uniform(-24, 24)))
    return m


def stamp(paper, seed, strength=STRENGTH):
    """Stampa i timbri sulla carta (array HxWx3 0..1) con inchiostro consumato."""
    H, W = paper.shape[:2]
    m = stamps_mask((W, H), seed) * cp._ink_breakup((W, H), seed + 1, .6) * strength
    return paper * (1 - m[..., None] * (1 - INK[None, None]))
