"""STORIE IG - collage su carta (1080x1920).

Carta stropicciata con grana (le texture del Compleanno) e, in colonna al centro:

- etichetta scelta nella Mini App (BREAKING NEWS, CALCIOMERCATO, UFFICIALE o nessuna): ogni
  parola su una striscia strappata, nero e oro alternati;
- foto (facoltativa): stampa con bordo bianco, inclinata, con due pezzi di nastro adesivo;
- testo (facoltativo): battuto a macchina (Special Elite), una riga per striscia di carta bianca,
  centrato. La grandezza dipende da quanto è lungo e si riduce finché tutto sta nella zona;
- in basso il logo JR dritto, stampato come un timbro: senza bordo, un po' sbiadito.

Tutto sta tra SAFE_T e SAFE_B (fuori dalle barre di Instagram). Gli angoli di strisce e foto
cambiano a ogni grafica (mai capovolti: pochi gradi), decisi da `seed`: la stessa grafica
rifatta con lo stesso seed esce identica.

Dal testo vengono tolti in automatico gli emoji e la firma "👉 @Juventus_Reborn".
"""
import io
import re
import unicodedata
from functools import lru_cache

import numpy as np
from PIL import Image, ImageFilter, ImageOps

from graphics import compleanno as cp
from graphics.common import asset_dir
from graphics.starting_xi import check_photo

W, H = 1080, 1920
SAFE_T, SAFE_B = 230, 1650           # sopra e sotto: barre di Instagram
TOP, BOTTOM = SAFE_T + 20, SAFE_B - 30   # zona del contenuto (sotto c'è il logo)
LOGO_Y = SAFE_B + 46                 # cima del logo JR
GAP = 56                             # tra etichetta, foto e testo
TILT_PAD = 34                        # in più tra etichetta e foto: la foto è inclinata e ha il nastro
TEXT_W = 880                         # larghezza massima di una riga di testo
PHOTO_W = 960                        # larghezza massima della foto
PHOTO_MIN_H = 420                    # con il testo, alla foto resta almeno questa altezza...
PHOTO_LOW = 320                      # ...o questa, se il testo è già sceso a FS_KEEP
FS_KEEP = 36
FS_MIN = 28
# Grandezza del testo in base ai caratteri: (fino a N caratteri, grandezza)
FS_PHOTO_STEPS = ((120, 46), (240, 42), (10**9, 38))
FS_SOLO_STEPS = ((80, 62), (150, 54), (240, 48), (10**9, 42))

PAPER = (226, 220, 206)
STRIP = (250, 248, 242)
TAPE = (236, 228, 200)
BLACK = cp.INK
GOLD = cp.GOLD
CREAM = np.array(cp.CREAM, np.float32) / 255
ANTON, MONO = cp.ANTON, cp.MONO
FONT_FILE = 'Poppins-Medium.ttf'     # usato dalle citazioni (ig_quote)
MAX_TEXT = 500

# Etichetta in alto: chiave della Mini App -> parole (una striscia ciascuna)
LABELS = {
    'breaking': ('BREAKING', 'NEWS'),       # notizia (quella di base): due pezzi staccati, stessa riga
    'mercato': ('CALCIOMERCATO',),          # trattative e voci di mercato
    'ufficiale': ('UFFICIALE',),            # confermata dal club
    'none': (),
}
DEFAULT_LABEL = 'breaking'

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
    """Chiave dell'etichetta valida (BREAKING NEWS se manca o non esiste)."""
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
    # NFKC: le lettere "grassetto" Unicode copiate dai post (𝐗𝐈 𝐔𝐅𝐅𝐈𝐂𝐈𝐀𝐋𝐄) diventano lettere
    # normali, che il font sa disegnare
    # Prima però via gli emoji: NFKC trasformerebbe ‼️ in "!!" e ⁉️ in "!?".
    text = unicodedata.normalize('NFKC', strip_emoji(str(value or '')))
    text = strip_emoji(text.replace('\r\n', '\n').replace('\r', '\n'))
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


LABEL_PAD, LABEL_SEP, LABEL_W = 45, 26, 990   # margine nel pezzo, spazio tra i pezzi, larghezza massima


def _label_words(words, size):
    """Parole dell'etichetta, una per pezzo di carta, tutte sulla stessa riga (rimpicciolite se non ci stanno)."""
    out = [cp._word(w, size, ANTON, 5) for w in words]
    total = sum(t.width + 2 * LABEL_PAD for t in out) + LABEL_SEP * max(len(out) - 1, 0)
    if total > LABEL_W:
        k = (LABEL_W - (2 * LABEL_PAD * len(out) + LABEL_SEP * (len(out) - 1))) / sum(t.width for t in out)
        out = [t.resize((max(1, int(t.width * k)), max(1, int(t.height * k))), Image.LANCZOS) for t in out]
    return out


def _label_height(parts):
    return max((p.height for p in parts), default=-32) + 32


def layout(text, label, photo_size=None):
    """Misure della colonna: (parole etichetta, righe del testo, grandezza, altezza foto, y di partenza).
    photo_size = (larghezza, altezza) della foto o None."""
    parts = _label_words(LABELS[label_key(label)], 150 if photo_size else 200)
    room = BOTTOM - TOP
    lab_h = _label_height(parts)
    gaps = GAP * max(bool(parts) + bool(photo_size) + bool(text) - 1, 0) + (TILT_PAD if parts and photo_size else 0)
    size = font_max(text, bool(photo_size)) if text else 0
    lines, ph_h = [], 0
    while True:
        lines = wrap(text, size) if text else []
        used = lab_h + text_height(lines, size) + gaps
        if photo_size:
            pw, phh = photo_size
            natural = PHOTO_W * phh / pw
            limit = 1150 if not text else 860
            ph_h = int(min(natural, limit, room - used))
            # prima si rimpicciolisce il testo; sotto FS_KEEP tocca alla foto (fino a PHOTO_LOW)
            if (not text or ph_h >= min(PHOTO_MIN_H, natural) or (size <= FS_KEEP and ph_h >= PHOTO_LOW)
                    or size <= FS_MIN):
                break
        elif used <= room or not text or size <= FS_MIN:
            break
        size -= 2
    total = lab_h + text_height(lines, size) + gaps + ph_h
    # con l'etichetta: lei fissa in alto (sotto il nome di Instagram), il resto centrato dopo
    return parts, lines, size, ph_h, TOP if parts else TOP + max((room - total) / 2, 0)


def content_y(top, lines, size, ph_h):
    """y di foto + testo sotto l'etichetta: a metà tra l'etichetta e il logo JR, senza uscire da BOTTOM."""
    rest = text_height(lines, size) + ph_h + (GAP if lines and ph_h else 0)
    return top + max(min((LOGO_Y - top - rest) / 2, BOTTOM - top - rest), 0)


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


def _erode(m, px):
    return _arr(Image.fromarray(np.uint8(m * 255)).filter(ImageFilter.MinFilter(px * 2 + 1)))


def _piece(img, ink, center, angle, paper_col, ink_col, seed, pad=(25, 16), tear=1.5, sh=(3, 5, 4, .3),
           breakup=.15, fringe=False):
    """Striscia di carta strappata con l'inchiostro sopra, ruotata e con ombra.
    fringe: bordo bianco e fibroso dello strappo e grana della carta dentro (le etichette)."""
    if fringe:
        return _torn_label(img, ink, center, angle, paper_col, ink_col, seed, pad, tear, sh, breakup)
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


def _torn_label(img, ink, center, angle, paper_col, ink_col, seed, pad, tear, sh, breakup):
    sw, shh = ink.width + 2 * pad[0], ink.height + 2 * pad[1]
    tl = Image.new('L', (sw, shh), 0)
    tl.paste(ink, pad)
    mg = 40
    m0 = np.pad(_arr(Image.new('L', (sw, shh), 255).rotate(angle, Image.BICUBIC, expand=True)), mg)
    t = np.pad(_arr(tl.rotate(angle, Image.BICUBIC, expand=True)), mg)
    h, w = m0.shape
    outer = _torn(m0, seed, tear * 1.6, 110)                       # fin dove arriva la carta
    core = np.minimum(_torn(_erode(m0, 5), seed + 7, tear, 70), outer)   # dove arriva la stampa
    t = t * core * cp._ink_breakup((w, h), seed, breakup)
    pc = np.array(paper_col, np.float32) / (255 if max(paper_col) > 1 else 1)
    ic = np.array(ink_col, np.float32) / (255 if max(ink_col) > 1 else 1)
    tex = cp._paper((w, h), (200, 200, 200), seed + 3).mean(-1) / (200 / 255)
    dark = pc.mean() < .3
    col = np.clip(pc[None, None] * (1 + (tex - 1)[..., None] * (1.6 if dark else .9))
                  + (.05 * (tex[..., None] - .95) if dark else 0), 0, 1)
    rgb = col * (1 - t[..., None]) + ic[None, None] * t[..., None]
    fr = np.clip(outer - core, 0, 1)[..., None]
    white = np.array((.95, .93, .88), np.float32)[None, None] * (1 + (tex[..., None] - 1) * .5)
    rgb = rgb * (1 - fr) + white * fr
    return _composite(img, center[0], center[1], outer, rgb, _shadow(outer, *sh) * (1 - outer))


def _tape(img, center, angle, seed):
    m = Image.new('L', (200, 64), 255).rotate(angle, Image.BICUBIC, expand=True)
    m = _torn(np.pad(_arr(m), 20), seed, 3, 40) * .55
    rgb = np.ones(m.shape + (3,), np.float32) * np.array(TAPE, np.float32)[None, None] / 255
    return _composite(img, center[0], center[1], m, rgb, np.zeros_like(m))


def _photo(img, raw, cx, cy, ph_h, angle, rng, min_ratio=0):
    """Foto con bordo e nastro. min_ratio: larghezza minima rispetto all'altezza (con il testo una foto
    verticale si ritaglia un po' più larga, invece di restare stretta)."""
    im = ImageOps.exif_transpose(Image.open(io.BytesIO(raw))).convert('RGB')
    ar = im.height / im.width
    pw = int(min(PHOTO_W, max(ph_h / ar, ph_h * min_ratio)))
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


def _logo_stamp(img, y_top, seed, size=140, k=.78):
    """Logo JR dritto stampato sulla carta come un timbro: niente bordo, inchiostro un po'
    sbiadito e consumato (più chiaro in alcuni punti, cambia con il seed)."""
    lg = _logo_alpha()
    lw = int(lg.width * size / lg.height)
    a = lg.resize((lw, size), Image.LANCZOS).filter(ImageFilter.GaussianBlur(.6))
    m = np.zeros((H, W), np.float32)
    x, y = int(W / 2 - lw / 2), int(y_top)
    m[y:y + size, x:x + lw] = _arr(a)
    m *= cp._ink_breakup((W, H), seed, .55) * k
    return img * (1 - m[..., None]) + BLACK[None, None] * m[..., None]


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

    # etichetta: un pezzo di carta nero per parola, affiancati sulla stessa riga, inclinazioni opposte
    sign = rng.choice((-1, 1))
    h = _label_height(parts)
    x = W / 2 - (sum(p.width + 2 * LABEL_PAD for p in parts) + LABEL_SEP * max(len(parts) - 1, 0)) / 2
    for i, p in enumerate(parts):
        pw = p.width + 2 * LABEL_PAD
        ang = float(sign * (-1) ** i * rng.uniform(1.5, 3) * (1 if len(parts) > 1 else 1.1))
        img = _piece(img, p, (x + pw / 2, y + h / 2 + rng.uniform(-6, 6)), ang, BLACK, CREAM,
                     int(rng.integers(1 << 20)), pad=(LABEL_PAD, 16 + (h - 32 - p.height) // 2), tear=2,
                     sh=(6, 10, 8, .4), breakup=.08, fringe=True)
        x += pw + LABEL_SEP
    if parts:
        y = content_y(y + h + GAP + (TILT_PAD if photo is not None else 0), lines, size, ph_h)

    if photo is not None:
        img = _photo(img, photo, W / 2, y + ph_h / 2, ph_h, _tilt(rng, 1.5, 4), rng, 1.6 if lines else 0)
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

    img = _logo_stamp(img, LOGO_Y, int(rng.integers(1 << 20)))
    img = _finish(img, light, .035, int(rng.integers(1 << 20)))
    out = Image.fromarray(np.uint8(np.clip(img, 0, 1) * 255 + 0.5))
    buf = io.BytesIO()
    out.save(buf, 'PNG')
    return buf.getvalue()
