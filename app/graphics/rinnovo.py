"""RINNOVI: maglia home stesa al sole con nome e anno di scadenza del contratto.

Nome e anno usano le lettere ufficiali della personalizzazione dello Juventus Store
(maglia home 2026/27): un PNG per carattere in imagegen/rinnovo/font_home/. Il testo viene
messo in prospettiva come la maglia e prende le pieghe del tessuto dalla foto.
"""
import io
import unicodedata

import numpy as np
from PIL import Image, ImageFilter

from graphics.common import asset_dir

W, H = 1500, 2000
NAME_MAX = 16
YEAR_MAX = 4
JR_COLOR = 'white'        # logo JR come nelle altre grafiche (FOTO + JR), in alto a destra

# Dove stanno nome e numero sulla maglia (misurati sulla grafica di riferimento, 1500x2000):
# angolo in alto a sinistra e in basso a sinistra a x0, in alto e in basso a destra a x1.
# La maglia è un po' girata: il lato destro è più in basso. cx = centro della scritta, sull'asse della
# maglia (colletto a x 737, fondo a x 765: la maglia pende un po', quindi più in basso sta più a destra).
NAME_BOX = {'x0': 458, 'x1': 1029, 'top': (487, 517), 'bottom': (595, 627), 'max_w': 640, 'cx': 749}
YEAR_BOX = {'x0': 387, 'x1': 1081, 'top': (656, 707), 'bottom': (961, 998), 'max_w': 760, 'cx': 755}

SPECIAL = {'.': 'dot', ' ': 'space', '-': 'dash', "'": 'apostrophe', '’': 'apostrophe'}


def _dir():
    return asset_dir() / 'imagegen' / 'rinnovo'


def _glyph_names():
    return {p.stem for p in (_dir() / 'font_home').glob('*.png')}


def clean_name(value):
    """Maiuscolo, solo caratteri che esistono nel font (le lettere accentate mancanti
    diventano senza accento). Massimo NAME_MAX caratteri."""
    have = _glyph_names()
    out = []
    for ch in ' '.join(str(value or '').upper().split()):
        if SPECIAL.get(ch, ch) in have:
            out.append(ch)
            continue
        base = unicodedata.normalize('NFD', ch)[0]
        if base in have:
            out.append(base)
    return ''.join(out).strip()[:NAME_MAX]


def clean_year(value):
    return ''.join(c for c in str(value or '') if c.isdigit())[:YEAR_MAX]


def _line(text, content_h):
    """Riga di caratteri affiancati, alta in modo che la parte disegnata sia content_h."""
    folder = _dir() / 'font_home'
    glyphs = [Image.open(folder / f'{SPECIAL.get(ch, ch)}.png').convert('RGBA') for ch in text]
    # altezza "piena" del carattere: la lettera più alta della riga (lo spazio non conta)
    full = max((g.getbbox() or (0, 0, 0, 0))[3] - (g.getbbox() or (0, 0, 0, 0))[1] for g in glyphs) or 1
    top = min((g.getbbox() or (0, 999, 0, 0))[1] for g in glyphs)
    k = content_h / full
    scaled = [g.resize((max(1, round(g.width * k * 2)), round(g.height * k * 2)), Image.LANCZOS) for g in glyphs]
    width = sum(g.width for g in scaled)
    row = Image.new('RGBA', (width, scaled[0].height), (0, 0, 0, 0))
    x = 0
    for g in scaled:
        row.alpha_composite(g, (x, 0))
        x += g.width
    crop_top = round(top * k * 2)
    return row.crop((0, crop_top, width, crop_top + round(content_h * 2)))


def _coeffs(dst, src):
    """Coefficienti PIL PERSPECTIVE: per ogni punto di uscita (dst) il punto sorgente (src)."""
    rows = []
    for (x, y), (u, v) in zip(dst, src):
        rows.append([x, y, 1, 0, 0, 0, -u * x, -u * y])
        rows.append([0, 0, 0, x, y, 1, -v * x, -v * y])
    return np.linalg.solve(np.array(rows, float), np.array(src, float).reshape(8)).tolist()


def _place(canvas, line, box):
    """Mette la riga nel riquadro inclinato `box`, centrata; se è troppo lunga la stringe."""
    x0, x1 = box['x0'], box['x1']
    (t0, t1), (b0, b1) = box['top'], box['bottom']
    cx = box.get('cx', (x0 + x1) / 2)
    h_mid = ((b0 - t0) + (b1 - t1)) / 2
    w = line.width * h_mid / line.height
    w = min(w, box['max_w'])
    lx, rx = cx - w / 2, cx + w / 2

    def at(x, a, b):          # y sulla retta da (x0, a) a (x1, b)
        return a + (b - a) * (x - x0) / (x1 - x0)

    dst = [(lx, at(lx, t0, t1)), (rx, at(rx, t0, t1)), (rx, at(rx, b0, b1)), (lx, at(lx, b0, b1))]
    src = [(0, 0), (line.width, 0), (line.width, line.height), (0, line.height)]
    warped = line.transform((W, H), Image.PERSPECTIVE, _coeffs(dst, src), Image.BICUBIC)
    canvas.alpha_composite(warped)


def _jr_logo():
    """Logo JR bianco in alto a destra: lo stesso overlay 3:4 della FOTO + JR, portato a 1500x2000."""
    from graphics.photo_jr import _meta
    path = asset_dir() / 'canva' / _meta()[JR_COLOR]['overlay']
    return Image.open(path).convert('RGBA').resize((W, H), Image.LANCZOS)


def _shade(background):
    """Pieghe e luce del tessuto: luminosità della maglia rispetto al bianco pieno."""
    lum = np.asarray(background.convert('L'), dtype=np.float32)
    soft = np.asarray(background.convert('L').filter(ImageFilter.GaussianBlur(2)), dtype=np.float32)
    shade = np.clip(soft / 232.0, 0.45, 1.08)
    del lum
    return shade[..., None]


def render(*, name, year):
    name, year = clean_name(name), clean_year(year)
    if not name:
        raise ValueError('Scrivi il nome.')
    if not year:
        raise ValueError("Scrivi l'anno.")
    background = Image.open(_dir() / 'maglia_home.jpg').convert('RGB').resize((W, H))
    text = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    _place(text, _line(name, NAME_BOX['bottom'][0] - NAME_BOX['top'][0]), NAME_BOX)
    _place(text, _line(year, YEAR_BOX['bottom'][0] - YEAR_BOX['top'][0]), YEAR_BOX)
    text = text.filter(ImageFilter.GaussianBlur(0.6))          # morbido come la foto
    rgba = np.asarray(text, dtype=np.float32)
    ink = rgba[..., :3] * _shade(background)
    alpha = rgba[..., 3:] / 255.0
    base = np.asarray(background, dtype=np.float32)
    out = Image.fromarray(np.clip(base * (1 - alpha) + ink * alpha, 0, 255).astype(np.uint8)).convert('RGBA')
    out.alpha_composite(_jr_logo())
    out = out.convert('RGB')
    buf = io.BytesIO()
    out.save(buf, 'PNG')
    return buf.getvalue()
