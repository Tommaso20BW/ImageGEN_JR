"""Timbri Juve sullo sfondo delle storie IG ("vedo non vedo").

Due timbri grandi e sbiaditi, stampati sulla carta prima di tutto il resto: uno in un angolo in
alto e l'altro nell'angolo opposto in basso, così non si toccano mai e restano lontani dal
contenuto al centro. Stile, posizione, grandezza e inclinazione cambiano con il seed (due stili
sempre diversi tra loro), con il seed uguale escono identici.

Venti stili (STYLES): timbro postale, francobolli, ovale, annullo con le onde, stella, scudo,
gomma, esagono, tre stelle, sigillo, biglietto, nastro, data, pallone, righe, campioni, etichetta,
fascia diagonale, J con le foglie.
"""
import numpy as np
from PIL import Image, ImageDraw

from graphics import compleanno as cp

ANTON, MONO = cp.ANTON, cp.MONO
INK = np.array((0.07, 0.07, 0.075), np.float32)
STRENGTH = 0.08        # quanto si vedono (0 = niente, 1 = inchiostro pieno)


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


# ---------------------------------------------------------------- gli stili
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


def _ring_text(im, text, c, rr, size, font=MONO):
    """Scritta che fa tutto il giro del cerchio, spaziata per chiuderlo."""
    fnt = cp._font(font, size)
    span = sum(size * .9 if ch == '*' else fnt.getlength(ch) for ch in text)
    _arc(im, text, c, rr, size, font=font, gap=2 * np.pi * rr / span)


def _circle(d, c, r, width, fill=None):
    d.ellipse((c[0] - r, c[1] - r, c[0] + r, c[1] + r), outline=255 if width else None, width=width or 0,
              fill=fill)


def _clip_paste(im, layer, clip):
    """Incolla `layer` solo dentro `clip` (stesse misure di im)."""
    im.paste(255, (0, 0), Image.fromarray(np.minimum(np.asarray(layer), np.asarray(clip))))


def _scudo(r, rng):
    """Scudo a contorno con righe bianconere e JUVE sopra."""
    w, h = r * 1.5, r * 1.85
    im, d = _canvas(w + 20, h + 20)
    x0, y0 = 10, 10
    pts = [(x0, y0), (x0 + w, y0), (x0 + w, y0 + h * .55), (x0 + w / 2, y0 + h), (x0, y0 + h * .55)]
    d.polygon(pts, outline=255, width=max(6, r // 26))
    m = r * .1
    inner = [(x0 + m, y0 + m), (x0 + w - m, y0 + m), (x0 + w - m, y0 + h * .53), (x0 + w / 2, y0 + h - m * 1.6),
             (x0 + m, y0 + h * .53)]
    strip = Image.new('L', im.size, 0)
    sd = ImageDraw.Draw(strip)
    sw = (w - 2 * m) / 7
    for i in range(0, 7, 2):
        sd.rectangle((x0 + m + i * sw, y0 + h * .34, x0 + m + (i + 1) * sw, y0 + h), fill=255)
    clip = Image.new('L', im.size, 0)
    ImageDraw.Draw(clip).polygon(inner, fill=255)
    _clip_paste(im, strip, clip)
    d.line((x0 + m, y0 + h * .34, x0 + w - m, y0 + h * .34), fill=255, width=3)
    _text(im, 'JUVE', (x0 + w / 2, y0 + h * .19), int(r * .32), ANTON, 3)
    return im


def _gomma(r, rng):
    """Timbro di gomma rettangolare: doppia cornice, parola grande, scritta piccola."""
    w, h = r * 2.4, r * 1.1
    im, d = _canvas(w + 20, h + 20)
    d.rectangle((10, 10, 10 + w, 10 + h), outline=255, width=max(7, r // 24))
    d.rectangle((10 + r * .08, 10 + r * .08, 10 + w - r * .08, 10 + h - r * .08), outline=255, width=3)
    big, small = (('BIANCONERI', 'TORINO · 1897'), ('UFFICIALE', 'JUVENTUS · TORINO'),
                  ('JUVENTUS', 'FINO ALLA FINE'))[int(rng.integers(3))]
    _text(im, big, (10 + w / 2, 10 + h * .42), int(r * .4), ANTON, 4)
    _text(im, small, (10 + w / 2, 10 + h * .78), int(r * .15), MONO, 3)
    return im


def _esagono(r, rng):
    """Esagono doppio con 1897 e tre stelle."""
    im, d = _canvas(2 * r + 20, 2 * r + 20)
    c = (r + 10, r + 10)
    for rr, wd in ((r, max(6, r // 26)), (r * .86, 3)):
        d.polygon([(c[0] + rr * np.cos(a), c[1] + rr * np.sin(a)) for a in np.arange(6) * np.pi / 3],
                  outline=255, width=wd)
    _text(im, '1897', (c[0], c[1] + r * .08), int(r * .5), ANTON, 3)
    for i in (-1, 0, 1):
        _star(d, c[0] + i * r * .2, c[1] - r * .4, r * .07)
    _text(im, 'TORINO', (c[0], c[1] + r * .5), int(r * .14), MONO, 4)
    return im


def _tre_stelle(r, rng):
    """Tondo con tre stelle grandi in fila e JUVE sotto, corona di puntini."""
    im, d = _canvas(2 * r + 20, 2 * r + 20)
    c = (r + 10, r + 10)
    _circle(d, c, r, max(6, r // 26))
    for k in range(48):
        a = 2 * np.pi * k / 48
        _circle(d, (c[0] + r * .88 * np.sin(a), c[1] - r * .88 * np.cos(a)), r * .025, 0, fill=255)
    for i in (-1, 0, 1):
        _star(d, c[0] + i * r * .38, c[1] - r * .22 - (r * .06 if i == 0 else 0), r * .17)
    _text(im, 'JUVE', (c[0], c[1] + r * .32), int(r * .42), ANTON, 4)
    return im


def _sigillo(r, rng):
    """Sigillo a bordo seghettato con FINO ALLA FINE al centro."""
    im, d = _canvas(2 * r + 20, 2 * r + 20)
    c = (r + 10, r + 10)
    n = 36
    pts = [(c[0] + (r if i % 2 == 0 else r * .9) * np.sin(np.pi * i / n),
            c[1] - (r if i % 2 == 0 else r * .9) * np.cos(np.pi * i / n)) for i in range(2 * n)]
    d.polygon(pts, outline=255, width=max(5, r // 30))
    _circle(d, c, r * .76, 3)
    for k, word in enumerate(('FINO', 'ALLA', 'FINE')):
        _text(im, word, (c[0], c[1] + (k - 1) * r * .32), int(r * .26), ANTON, 3)
    return im


def _biglietto(r, rng):
    """Biglietto dello stadio: rettangolo con le tacche, matrice tratteggiata."""
    w, h = r * 2.5, r * 1.1
    im, d = _canvas(w + 20, h + 20)
    x0, y0, x1, y1 = 10, 10, 10 + w, 10 + h
    d.rectangle((x0, y0, x1, y1), outline=255, width=max(6, r // 26))
    nr, my = r * .13, (y0 + y1) / 2
    for cx in (x0, x1):
        _circle(d, (cx, my), nr, 0, fill=0)
        d.arc((cx - nr, my - nr, cx + nr, my + nr), 0, 360, fill=255, width=4)
    sx = x0 + w * .72
    for y in np.arange(y0 + 10, y1 - 10, 22):
        d.line((sx, y, sx, y + 11), fill=255, width=4)
    _text(im, 'INGRESSO', ((x0 + sx) / 2, y0 + h * .22), int(r * .14), MONO, 4)
    _text(im, 'JUVENTUS', ((x0 + sx) / 2, y0 + h * .52), int(r * .36), ANTON, 3)
    _text(im, 'TORINO', ((x0 + sx) / 2, y0 + h * .82), int(r * .14), MONO, 4)
    _text(im, 'SETTORE', ((sx + x1) / 2 - r * .04, y0 + h * .22), int(r * .1), MONO, 1)
    _text(im, '1897', ((sx + x1) / 2 - r * .06, y0 + h * .76), int(r * .2), ANTON, 2)
    return im


def _nastro(r, rng):
    """Nastro con le code a coda di rondine e tre stelline sopra."""
    w, h = r * 2.6, r * .62
    im, d = _canvas(w + 20, h + r * .5 + 20)
    y0, t = 10 + r * .4, r * .3
    d.polygon([(10, y0), (10 + w, y0), (10 + w - t, y0 + h / 2), (10 + w, y0 + h), (10, y0 + h), (10 + t, y0 + h / 2)],
              outline=255, width=max(6, r // 26))
    for y in (y0 + r * .07, y0 + h - r * .07):
        d.line((10 + t * 1.6, y, 10 + w - t * 1.6, y), fill=255, width=3)
    _text(im, ('FORZA JUVE', 'BIANCONERI', 'FINO ALLA FINE')[int(rng.integers(3))],
          (10 + w / 2, y0 + h / 2), int(r * .3), ANTON, 4)
    for i in (-1, 0, 1):
        _star(d, 10 + w / 2 + i * r * .3, 10 + r * .2 - (r * .05 if i == 0 else 0), r * .1)
    return im


def _data(r, rng):
    """Timbro con la data di nascita della Juve, cornice arrotondata."""
    w, h = r * 1.9, r * 1.5
    im, d = _canvas(w + 20, h + 20)
    d.rounded_rectangle((10, 10, 10 + w, 10 + h), r * .15, outline=255, width=max(6, r // 26))
    for f in (.28, .74):
        d.line((10 + r * .1, 10 + h * f, 10 + w - r * .1, 10 + h * f), fill=255, width=3)
    _text(im, 'TORINO', (10 + w / 2, 10 + h * .15), int(r * .17), MONO, 5)
    _text(im, '1 NOV 1897', (10 + w / 2, 10 + h * .51), int(r * .36), ANTON, 3)
    _text(im, 'NASCE LA JUVE', (10 + w / 2, 10 + h * .87), int(r * .14), MONO, 3)
    return im


def _pallone(r, rng):
    """Pallone vecchio stile (a spicchi) dentro una corona di scritte."""
    im, d = _canvas(2 * r + 20, 2 * r + 20)
    c = (r + 10, r + 10)
    _circle(d, c, r, max(5, r // 30))
    _circle(d, c, r * .72, 3)
    _ring_text(im, '* JUVENTUS * FOOTBALL CLUB ', c, r * .86, int(r * .14))
    br = r * .55
    _circle(d, c, br, max(5, r // 32))
    for f in (.18, .55):          # cuciture curve degli spicchi
        d.ellipse((c[0] - br * f, c[1] - br, c[0] + br * f, c[1] + br), outline=255, width=4)
    d.arc((c[0] - br, c[1] - br * .35, c[0] + br, c[1] + br * .35), 0, 360, fill=255, width=3)
    return im


def _zebra(r, rng):
    """Tondo pieno di righe bianconere con una fascia JUVENTUS 1897."""
    im, d = _canvas(2 * r + 20, 2 * r + 20)
    c = (r + 10, r + 10)
    _circle(d, c, r, max(6, r // 26))
    stripes = Image.new('L', im.size, 0)
    sd = ImageDraw.Draw(stripes)
    sw = r * 1.7 / 9
    for i in range(0, 9, 2):
        sd.rectangle((c[0] - r * .85 + i * sw, 0, c[0] - r * .85 + (i + 1) * sw, im.height), fill=255)
    clip = Image.new('L', im.size, 0)
    ImageDraw.Draw(clip).ellipse((c[0] - r * .85, c[1] - r * .85, c[0] + r * .85, c[1] + r * .85), fill=255)
    _clip_paste(im, stripes, clip)
    d.rectangle((c[0] - r, c[1] - r * .2, c[0] + r, c[1] + r * .2), fill=0)
    d.rectangle((c[0] - r * .95, c[1] - r * .2, c[0] + r * .95, c[1] + r * .2), outline=255, width=4)
    _text(im, 'JUVENTUS 1897', c, int(r * .24), ANTON, 3)
    return im


def _campioni(r, rng):
    """Corona con CAMPIONI D'ITALIA e la stella al centro."""
    im, d = _canvas(2 * r + 20, 2 * r + 20)
    c = (r + 10, r + 10)
    _circle(d, c, r, 3)
    _circle(d, c, r * .96, max(5, r // 32))
    _circle(d, c, r * .7, 3)
    _arc(im, "CAMPIONI D'ITALIA", c, r * .83, int(r * .15), gap=1.15)
    _arc(im, 'JUVENTUS', c, r * .83, int(r * .15), start=np.pi, gap=1.3, flip=True)
    for s in (-1, 1):
        _star(d, c[0] + s * r * .83, c[1], r * .06)
    _star(d, c[0], c[1] - r * .05, r * .42, outline=max(5, r // 30))
    _star(d, c[0], c[1] - r * .05, r * .2)
    return im


def _etichetta(r, rng):
    """Etichetta da valigia: angoli tagliati, foro, TORINO grande."""
    w, h = r * 2.3, r * 1.15
    im, d = _canvas(w + 20, h + 20)
    x0, y0, x1, y1 = 10, 10, 10 + w, 10 + h
    cut = h * .3
    d.polygon([(x0 + cut, y0), (x1, y0), (x1, y1), (x0 + cut, y1), (x0, y1 - cut), (x0, y0 + cut)],
              outline=255, width=max(6, r // 26))
    _circle(d, (x0 + cut * .9, (y0 + y1) / 2), r * .09, 4)
    tx = (x0 + cut * 1.8 + x1) / 2
    _text(im, 'TORINO', (tx, y0 + h * .4), int(r * .42), ANTON, 4)
    _text(im, 'DESTINAZIONE JUVE', (tx, y0 + h * .78), int(r * .13), MONO, 2)
    return im


def _diagonale(r, rng):
    """Tondo tagliato da una fascia diagonale piena con BIANCONERI in negativo."""
    im, d = _canvas(2 * r + 20, 2 * r + 20)
    c = (r + 10, r + 10)
    _circle(d, c, r, max(6, r // 26))
    _circle(d, c, r * .9, 3)
    band = Image.new('L', (int(r * 2.2), int(r * .5)), 255)
    w = cp._word('BIANCONERI', int(r * .3), ANTON, 4)
    band.paste(0, ((band.width - w.width) // 2, (band.height - w.height) // 2), w)
    band = band.rotate(25, Image.BICUBIC, expand=True)
    layer = Image.new('L', im.size, 0)
    layer.paste(band, (int(c[0] - band.width / 2), int(c[1] - band.height / 2)))
    clip = Image.new('L', im.size, 0)
    ImageDraw.Draw(clip).ellipse((c[0] - r * .9, c[1] - r * .9, c[0] + r * .9, c[1] + r * .9), fill=255)
    _clip_paste(im, layer, clip)
    _star(d, c[0] - r * .4, c[1] - r * .45, r * .12)
    _text(im, '1897', (c[0] + r * .35, c[1] + r * .5), int(r * .22), ANTON, 2)
    return im


def _lettera(r, rng):
    """J grande al centro tra due rami di foglioline, TORINO in alto."""
    im, d = _canvas(2 * r + 20, 2 * r + 20)
    c = (r + 10, r + 10)
    _circle(d, c, r, max(6, r // 26))
    t = np.linspace(0, 2 * np.pi, 24, endpoint=False)
    for s in (-1, 1):                          # due rami di foglioline lungo il bordo
        for k in range(7):
            a = np.pi * (.32 + k * .075) * s
            x, y = c[0] + r * .7 * np.sin(a), c[1] - r * .7 * np.cos(a)
            ex, ey = r * .1 * np.cos(t), r * .045 * np.sin(t)      # foglia lungo il cerchio
            ca, sa = np.cos(a), np.sin(a)
            d.polygon(list(zip(x + ex * ca - ey * sa, y + ex * sa + ey * ca)), outline=255, width=3)
    _text(im, 'J', (c[0], c[1] - r * .05), int(r * .95), ANTON)
    _arc(im, 'TORINO', c, r * .84, int(r * .14), gap=1.4)
    for i in (-1, 0, 1):
        _star(d, c[0] + i * r * .16, c[1] + r * .68, r * .05)
    return im


def _poste(r, rng):
    """Francobollo orizzontale a dentini vuoti: POSTE BIANCONERE, stella e JUVE."""
    w, h = r * 2.2, r * 1.5
    im, d = _canvas(w + 20, h + 20)
    x0, y0, x1, y1 = 10, 10, 10 + w, 10 + h
    d.rectangle((x0, y0, x1, y1), outline=255, width=3)
    hole, step = r * .045, r * .13
    for x in np.arange(x0, x1 + 1, (x1 - x0) / round((x1 - x0) / step)):
        for y in (y0, y1):
            _circle(d, (x, y), hole, 3)
    for y in np.arange(y0, y1 + 1, (y1 - y0) / round((y1 - y0) / step)):
        for x in (x0, x1):
            _circle(d, (x, y), hole, 3)
    m = r * .14
    d.rectangle((x0 + m, y0 + m, x1 - m, y1 - m), outline=255, width=4)
    _text(im, 'POSTE BIANCONERE', ((x0 + x1) / 2, y0 + m + r * .15), int(r * .13), MONO, 2)
    _star(d, x0 + m + r * .4, (y0 + y1) / 2 + r * .08, r * .25, outline=5)
    _text(im, 'JUVE', (x1 - m - r * .6, (y0 + y1) / 2 + r * .05), int(r * .4), ANTON, 3)
    _text(im, '1897', (x1 - m - r * .6, y1 - m - r * .17), int(r * .16), MONO, 2)
    return im


STYLES = (_tondo, _francobollo, _ovale, _annullo, _stella, _scudo, _gomma, _esagono, _tre_stelle, _sigillo,
          _biglietto, _nastro, _data, _pallone, _zebra, _campioni, _etichetta, _diagonale, _lettera, _poste)


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
        r = rng.uniform(.25, .29) * W         # grandi: circa metà della larghezza
        left = left_top if k == 0 else not left_top
        cx = rng.uniform(.2, .3) * W
        cx = cx if left else W - cx
        cy = rng.uniform(.13, .2) * H if k == 0 else H - rng.uniform(.17, .24) * H
        _place(m, STYLES[style](int(r), rng), cx, cy, float(rng.uniform(-24, 24)))
    return m


def stamp(paper, seed, strength=STRENGTH):
    """Stampa i timbri sulla carta (array HxWx3 0..1) con inchiostro consumato."""
    H, W = paper.shape[:2]
    m = stamps_mask((W, H), seed) * cp._ink_breakup((W, H), seed + 1, .6) * strength
    return paper * (1 - m[..., None] * (1 - INK[None, None]))
