"""STORIE IG - collage su carta (1080x1920).

Carta stropicciata con grana (le texture del Compleanno) e, in colonna al centro:

- etichetta scelta nella Mini App (ULTIM'ORA, NOTIZIA, UFFICIALE, ...; o nessuna): ogni
  parola su una striscia strappata, nero e oro alternati;
- foto (facoltativa): stampa con bordo bianco, inclinata, con due pezzi di nastro adesivo;
- testo (facoltativo): battuto a macchina (Special Elite), una riga per striscia di carta bianca,
  centrato. La grandezza dipende da quanto è lungo e si riduce finché tutto sta nella zona;
- in basso il logo JR nero su un adesivo bianco ritagliato a forbici intorno alla forma.

Tutto sta tra SAFE_T e SAFE_B (fuori dalle barre di Instagram). Gli angoli di strisce, foto e
logo cambiano a ogni grafica (mai capovolti: pochi gradi), decisi da `seed`: la stessa grafica
rifatta con lo stesso seed esce identica.

Dal testo vengono tolti in automatico gli emoji e la firma "👉 @Juventus_Reborn".
"""
import io
import re
from functools import lru_cache

import cv2
import numpy as np
from PIL import Image, ImageFilter, ImageOps

from graphics import compleanno as cp
from graphics.common import asset_dir
from graphics.starting_xi import check_photo

W, H = 1080, 1920
SAFE_T, SAFE_B = 230, 1650           # sopra e sotto: barre di Instagram
TOP, BOTTOM = SAFE_T + 20, SAFE_B - 30   # zona del contenuto (sotto c'è il logo)
GAP = 56                             # tra etichetta, foto e testo
TEXT_W = 880                         # larghezza massima di una riga di testo
PHOTO_W = 880                        # larghezza massima della foto
PHOTO_MIN_H = 300                    # con il testo, alla foto resta almeno questa altezza...
PHOTO_LOW = 220                      # ...o questa, se il testo è già sceso a FS_KEEP
FS_KEEP = 40
FS_MIN = 30
# Grandezza del testo in base ai caratteri: (fino a N caratteri, grandezza)
FS_PHOTO_STEPS = ((120, 62), (240, 54), (10**9, 46))
FS_SOLO_STEPS = ((80, 84), (150, 72), (240, 64), (10**9, 54))

PAPER = (226, 220, 206)
STRIP = (250, 248, 242)
TAPE = (236, 228, 200)
STICKER = (247, 245, 239)
BLACK = cp.INK
GOLD = cp.GOLD
CREAM = np.array(cp.CREAM, np.float32) / 255
ANTON, MONO = cp.ANTON, cp.MONO
FONT_FILE = 'Poppins-Medium.ttf'     # usato dalle citazioni (ig_quote)
MAX_TEXT = 500

# Etichetta in alto: chiave della Mini App -> parole (una striscia ciascuna)
LABELS = {
    'ultimora': ('ULTIM’ORA',),             # notizia urgente (quella di base)
    'news': ('NEWS',),                      # notizia normale
    'ufficiale': ('UFFICIALE',),            # confermata dal club
    'mercato': ('CALCIOMERCATO',),          # trattative e voci di mercato
    'infortunio': ('INFORTUNIO',),          # aggiornamenti medici
    'none': (),
}
DEFAULT_LABEL = 'ultimora'

TEXT_COLOR = '#1a1612'
# Colori del testo scelti nella Mini App (tavolozza dei testi di Instagram). 'black' è quello di base.
TEXT_COLORS = {
    'black': TEXT_COLOR, 'blue': '#3897F0', 'green': '#70C050', 'yellow': '#FDCB5C',
    'orange': '#FD8D32', 'red': '#ED4956', 'pink': '#D10869', 'purple': '#A307BA',
}


def text_color(value):
    """Nome del colore valido ('black' se manca o non è nella tavolozza)."""
    return value if value in TEXT_COLORS else 'black'


def label_key(value):
    """Chiave dell'etichetta valida (ULTIM'ORA se manca o non esiste)."""
    return value if value in LABELS else DEFAULT_LABEL


# Firma da togliere (con l'eventuale manina davanti) e emoji: pittogrammi, simboli, bandiere, ZWJ,
# selettori di variante e tasti. Lettere accentate, punteggiatura e simboli come € restano.
_SIGNATURE = re.compile('[\U0001F446-\U0001F450☝☜☞]?️?\\s*@Juventus_Reborn\\b', re.I)
_EMOJI = re.compile('[\U0001F000-\U0001FAFF⌀-⏿☀-➿⬀-⯿'
                    '‼⁉™ℹ↔-↪Ⓜ▪-◾〰〽㊗㊙'
                    '‍⃣︎️\U000E0020-\U000E007F]')


def strip_emoji(text):
    """Toglie la firma "👉 @Juventus_Reborn" e tutti gli emoji."""
    return _EMOJI.sub('', _SIGNATURE.sub('', text))


def tidy(value):
    """Niente emoji né firma, a-capo mantenuti, righe vuote di fila ridotte a una (nessun limite)."""
    text = strip_emoji(str(value or '').replace('\r\n', '\n').replace('\r', '\n'))
    lines = [' '.join(line.split()) for line in text.split('\n')]
    return re.sub(r'\n{3,}', '\n\n', '\n'.join(lines)).strip()


def clean_text(value):
    """Testo della Storia IG: come tidy(), al massimo MAX_TEXT caratteri."""
    text = tidy(value)
    if len(text) > MAX_TEXT:
        raise ValueError(f'Testo troppo lungo (massimo {MAX_TEXT} caratteri).')
    return text


def font_max(text, with_photo):
    """Grandezza di partenza del testo in base a quanti caratteri ha."""
    n = len(text.replace('\n', ''))
    for limit, size in (FS_PHOTO_STEPS if with_photo else FS_SOLO_STEPS):
        if n <= limit:
            return size
    return FS_MIN


def _rgb(hex_color):
    return np.array([int(hex_color[i:i + 2], 16) for i in (1, 3, 5)], np.float32) / 255


# ---------------------------------------------------------------- testo
def wrap(text, size, width=TEXT_W):
    """Righe del testo a questa grandezza: rispetta gli a-capo, '' = riga vuota; parole più
    lunghe della riga spezzate a lettere."""
    fnt = cp._font(MONO, size)
    out = []
    for para in text.split('\n'):
        if not para.strip():
            out.append('')
            continue
        cur = ''
        for word in para.split():
            while fnt.getlength(word) > width:          # parola troppo lunga (link, ecc.)
                k = len(word)
                while k > 1 and fnt.getlength(word[:k]) > width:
                    k -= 1
                if cur:
                    out.append(cur); cur = ''
                out.append(word[:k]); word = word[k:]
            test = f'{cur} {word}'.strip()
            if fnt.getlength(test) <= width or not cur:
                cur = test
            else:
                out.append(cur); cur = word
        if cur:
            out.append(cur)
    return out


def _line_h(size):
    """Altezza della striscia di una riga (carta sopra e sotto in proporzione al testo)."""
    return int(size * 1.15) + int(size * 0.55)


def _line_gap(size):
    return int(size * 0.24)


def text_height(lines, size):
    if not lines:
        return 0
    return sum(_line_h(size) if ln else int(size * 0.6) for ln in lines) + _line_gap(size) * (len(lines) - 1)


def _label_words(words, size):
    out = []
    for w in words:
        t = cp._word(w, size, ANTON, 5)
        if t.width > 900:
            t = t.resize((900, max(1, int(t.height * 900 / t.width))), Image.LANCZOS)
        out.append(t)
    return out


def _label_height(parts):
    return sum(p.height + 32 for p in parts) + 30 * max(len(parts) - 1, 0)


def layout(text, label, photo_size=None):
    """Misure della colonna: (parole etichetta, righe del testo, grandezza, altezza foto, y di partenza).
    photo_size = (larghezza, altezza) della foto o None."""
    parts = _label_words(LABELS[label_key(label)], 150 if photo_size else 200)
    room = BOTTOM - TOP
    lab_h = _label_height(parts)
    gaps = GAP * max(bool(parts) + bool(photo_size) + bool(text) - 1, 0)
    size = font_max(text, bool(photo_size)) if text else 0
    lines, ph_h = [], 0
    while True:
        lines = wrap(text, size) if text else []
        used = lab_h + text_height(lines, size) + gaps
        if photo_size:
            pw, phh = photo_size
            natural = PHOTO_W * phh / pw
            limit = 1100 if not text else 620
            ph_h = int(min(natural, limit, room - used))
            # prima si rimpicciolisce il testo; sotto FS_KEEP tocca alla foto (fino a PHOTO_LOW)
            if (not text or ph_h >= min(PHOTO_MIN_H, natural) or (size <= FS_KEEP and ph_h >= PHOTO_LOW)
                    or size <= FS_MIN):
                break
        elif used <= room or not text or size <= FS_MIN:
            break
        size -= 2
    total = lab_h + text_height(lines, size) + gaps + ph_h
    return parts, lines, size, ph_h, TOP + max((room - total) / 2, 0)


# ---------------------------------------------------------------- pezzi di carta
def _arr(im):
    return np.asarray(im, np.float32) / 255


def _torn(m, seed, amp, base):
    """Bordo strappato su una maschera locale (rumore in proporzione alla sua larghezza)."""
    h, w = m.shape
    n = cp._fbm((w, h), seed, 4, max(2, int(round(base * w / W))))
    soft = np.asarray(Image.fromarray(np.uint8(m * 255)).filter(ImageFilter.GaussianBlur(amp)), np.float32) / 255
    return np.clip((soft - 0.5 + (n - 0.5) * 0.9) * 8 + 0.5, 0, 1) * (soft > 0.02)


def _shadow(m, dx, dy, r, k):
    sh = np.roll(np.roll(m, dy, 0), dx, 1)
    return np.asarray(Image.fromarray(np.uint8(sh * 255)).filter(ImageFilter.GaussianBlur(r)), np.float32) / 255 * k


def _region(img, cx, cy, h, w):
    """Fette di pagina e di pezzo per un pezzo h x w centrato in (cx, cy), tagliate ai bordi."""
    x, y = int(round(cx - w / 2)), int(round(cy - h / 2))
    x0, y0, x1, y1 = max(x, 0), max(y, 0), min(x + w, W), min(y + h, H)
    if x1 <= x0 or y1 <= y0:
        return None
    return (slice(y0, y1), slice(x0, x1)), (slice(y0 - y, y1 - y), slice(x0 - x, x1 - x))


def _composite(img, cx, cy, cover, rgb, shadow):
    """Ombra, poi il pezzo (cover = copertura 0..1, rgb = colori HxWx3) sulla pagina."""
    r = _region(img, cx, cy, *cover.shape)
    if r is None:
        return img
    (pg, pc) = r
    reg = img[pg]
    reg *= 1 - shadow[pc][..., None]
    m = cover[pc][..., None]
    img[pg] = reg * (1 - m) + rgb[pc] * m
    return img


def _piece(img, ink, center, angle, paper_col, ink_col, seed, pad=(25, 16), tear=1.5, sh=(3, 5, 4, .3),
           breakup=.15):
    """Striscia di carta strappata con l'inchiostro sopra, ruotata e con ombra."""
    sw, shh = ink.width + 2 * pad[0], ink.height + 2 * pad[1]
    tl = Image.new('L', (sw, shh), 0)
    tl.paste(ink, pad)
    m = Image.new('L', (sw, shh), 255).rotate(angle, Image.BICUBIC, expand=True)
    t = tl.rotate(angle, Image.BICUBIC, expand=True)
    mg = 40
    m = np.pad(_arr(m), mg)
    t = np.pad(_arr(t), mg)
    m = _torn(m, seed, tear, 70)
    t = t * m * cp._ink_breakup((t.shape[1], t.shape[0]), seed, breakup)
    paper_c = np.array(paper_col, np.float32) / (255 if max(paper_col) > 1 else 1)
    ink_c = np.array(ink_col, np.float32) / (255 if max(ink_col) > 1 else 1)
    rgb = paper_c[None, None] * (1 - t[..., None]) + ink_c[None, None] * t[..., None]
    return _composite(img, center[0], center[1], m, rgb, _shadow(m, *sh) * (1 - m))


def _tape(img, center, angle, seed):
    m = Image.new('L', (200, 64), 255).rotate(angle, Image.BICUBIC, expand=True)
    m = _torn(np.pad(_arr(m), 20), seed, 3, 40) * .55
    rgb = np.ones(m.shape + (3,), np.float32) * np.array(TAPE, np.float32)[None, None] / 255
    return _composite(img, center[0], center[1], m, rgb, np.zeros_like(m))


def _photo(img, raw, cx, cy, ph_h, angle, rng):
    im = ImageOps.exif_transpose(Image.open(io.BytesIO(raw))).convert('RGB')
    ar = im.height / im.width
    pw = int(min(PHOTO_W, ph_h / ar))
    phh = int(min(ph_h, pw * ar))
    im = ImageOps.fit(im, (pw, phh), Image.LANCZOS, centering=(.5, .35))
    border = 18
    fr = Image.new('RGB', (pw + 2 * border, phh + 2 * border), (245, 242, 235))
    fr.paste(im, (border, border))
    fa = Image.new('L', fr.size, 255)
    fr = fr.rotate(angle, Image.BICUBIC, expand=True)
    fa = fa.rotate(angle, Image.BICUBIC, expand=True)
    mg = 40
    a = np.pad(_arr(fa), mg)
    rgb = np.pad(_arr(fr) * .92 + .05, ((mg, mg), (mg, mg), (0, 0)))
    img = _composite(img, cx, cy, a, rgb, _shadow(a, 12, 20, 18, .5) * (1 - a))
    w, h = fr.size
    x0, y0 = cx - w / 2, cy - h / 2
    img = _tape(img, (x0 + 50, y0 + 12), rng.uniform(25, 42), int(rng.integers(1 << 20)))
    return _tape(img, (x0 + w - 50, y0 + h - 12), rng.uniform(22, 38), int(rng.integers(1 << 20)))


@lru_cache(maxsize=1)
def _logo_alpha():
    """Forma del logo JR (alpha), ritagliata dall'overlay nero della FOTO + JR."""
    from graphics.photo_jr import _meta
    with Image.open(asset_dir() / 'canva' / _meta()['black']['overlay']) as im:
        a = im.convert('RGBA').getchannel('A')
        return a.crop(a.getbbox())


def _logo_sticker(img, y_top, angle, seed, size=140, border=14):
    """Logo JR nero su adesivo bianco: bordo uniforme intorno alla forma, tagliato a forbici
    (tanti tagli dritti corti), calcolato a 4x per avere i bordi puliti."""
    S = 4
    lg = _logo_alpha()
    lw = int(lg.width * size / lg.height)
    a = np.asarray(lg.resize((lw * S, size * S), Image.LANCZOS))
    a = np.pad(a, (border + 12) * S)
    k = lambda r: cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * r + 1, 2 * r + 1))
    blob = cv2.dilate((a > 60).astype(np.uint8) * 255, k(border * S))
    blob = cv2.morphologyEx(blob, cv2.MORPH_CLOSE, k(4 * S))      # stelle e lettere in un pezzo
    cnts, _ = cv2.findContours(blob, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    poly = cv2.approxPolyDP(max(cnts, key=cv2.contourArea), 1.6 * S, True).reshape(-1, 2).astype(np.float32)
    poly += np.random.default_rng(seed).normal(0, 0.35 * S, poly.shape)
    cut = np.zeros_like(a)
    cv2.fillPoly(cut, [np.int32(poly)], 255, cv2.LINE_AA)
    sz = (a.shape[1] // S, a.shape[0] // S)
    cut = Image.fromarray(cut).resize(sz, Image.LANCZOS).rotate(angle, Image.BICUBIC, expand=True)
    ink = Image.fromarray(a).resize(sz, Image.LANCZOS).rotate(angle, Image.BICUBIC, expand=True)
    mg = 30
    m, t = np.pad(_arr(cut), mg), np.pad(_arr(ink), mg)
    rgb = (np.array(STICKER, np.float32) / 255)[None, None] * (1 - t[..., None]) + BLACK[None, None] * t[..., None]
    return _composite(img, W / 2, y_top + sz[1] / 2, m, rgb, _shadow(m, 4, 7, 6, .4) * (1 - m))


def _finish(img, light, grain, seed, vignette=.18):
    img = img + np.random.default_rng(seed).normal(0, grain, (H, W, 1)).astype(np.float32)
    img = img * light[..., None]
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    r = np.sqrt(((xx - W / 2) / (W / 2)) ** 2 + ((yy - H / 2) / (H / 2)) ** 2) / np.sqrt(2)
    return np.clip(img * (1 - vignette * r ** 2)[..., None], 0, 1)


def _tilt(rng, lo, hi):
    """Pochi gradi, a destra o a sinistra."""
    return float(rng.uniform(lo, hi) * rng.choice((-1, 1)))


# ---------------------------------------------------------------- grafica
def render(*, text='', photo=None, color='black', label=DEFAULT_LABEL, seed=None):
    text = clean_text(text)
    if not text and photo is None:
        raise ValueError('Scrivi un testo o scegli una foto.')
    psize = None
    if photo is not None:
        check_photo(photo)
        with Image.open(io.BytesIO(photo)) as im:
            psize = ImageOps.exif_transpose(im).size
    if seed is None:
        seed = int(np.random.default_rng().integers(1 << 30))
    rng = np.random.default_rng(seed)
    parts, lines, size, ph_h, y = layout(text, label, psize)

    img = cp._paper((W, H), PAPER, seed=int(rng.integers(1 << 20))).copy()
    light = cp._crumple((W, H), int(rng.integers(1 << 20)), 0.7, folds=3)

    # etichetta: strisce sfalsate, nero/oro alternati, inclinazioni opposte
    sign = rng.choice((-1, 1))
    for i, p in enumerate(parts):
        h = p.height + 32
        dx = 0 if len(parts) == 1 else (-1) ** (i + 1) * min(90, (980 - p.width) / 2 - 20)
        col, tcol = (BLACK, CREAM) if i % 2 == 0 else (GOLD, BLACK)
        ang = float(sign * (-1) ** i * rng.uniform(1.5, 3.5))
        img = _piece(img, p, (W / 2 + dx, y + h / 2), ang, col, tcol, int(rng.integers(1 << 20)),
                     pad=(45, 16), tear=2, sh=(6, 10, 8, .4), breakup=.08)
        y += h + 30
    if parts:
        y += GAP - 30

    if photo is not None:
        img = _photo(img, photo, W / 2, y + ph_h / 2, ph_h, _tilt(rng, 1.5, 4), rng)
        y += ph_h + GAP

    ink = _rgb(TEXT_COLORS[text_color(color)])
    for ln in lines:
        if not ln:
            y += int(size * 0.6) + _line_gap(size)
            continue
        t = cp._word(ln, size, MONO, 1)
        h = _line_h(size)
        img = _piece(img, t, (W / 2 + rng.uniform(-8, 8), y + h / 2), float(rng.uniform(-1.2, 1.2)),
                     STRIP, ink, int(rng.integers(1 << 20)), pad=(25, (h - t.height) // 2))
        y += h + _line_gap(size)

    img = _logo_sticker(img, SAFE_B + 20, _tilt(rng, 2, 5), int(rng.integers(1 << 20)))
    img = _finish(img, light, .035, int(rng.integers(1 << 20)))
    out = Image.fromarray(np.uint8(np.clip(img, 0, 1) * 255 + 0.5))
    buf = io.BytesIO()
    out.save(buf, 'PNG')
    return buf.getvalue()
