"""CITAZIONE IG, storia: dallo screenshot di una storia (telefono) prende la storia senza l'interfaccia
di Instagram e la foto profilo.

Nello screenshot la storia è un riquadro 9:16 su sfondo scuro uniforme: sopra ora e batteria, sotto
la barra "Invia messaggio". La storia resta intera (9:16); in cima, barrette e riga foto profilo /
account si coprono con una sfumatura della foto subito sotto: lì la grafica rimette le sue. Se lo screenshot non ha questa forma (storia a tutto schermo, foto normale)
la foto resta com'è.
"""
import io

from PIL import Image, ImageFilter

HEADER = 0.135        # barrette + riga dell'account, in parti della larghezza della storia
AVATAR = (0.07, 0.085, 0.04)      # centro x, centro y (dall'alto della storia) e raggio, in parti della larghezza


def _frame(image):
    """(alto, basso) del riquadro della storia, oppure None."""
    import numpy as np
    a = np.asarray(image.convert('RGB').resize((image.width // 4, image.height // 4))).astype(int)
    h, w, _ = a.shape
    bg = a[-2].mean(axis=0)
    if np.abs(a[-2] - bg).max() > 14 or bg.max() > 60:      # in basso niente sfondo scuro uniforme
        return None
    plain = (np.abs(a - bg).max(axis=2) < 14).mean(axis=1) > 0.97
    best, start = (0, 0), None
    for y, flat in enumerate([*plain, True]):
        if not flat and start is None:
            start = y
        if flat and start is not None:
            if y - start > best[1] - best[0]:
                best = (start, y)
            start = None
    top, bottom = best[0] * 4, best[1] * 4
    ratio = (bottom - top) / image.width
    return (top, bottom) if 1.6 <= ratio <= 1.95 else None


def bars(image, top):
    """Barrette in cima alla storia: quanto è piena ciascuna (1 = vista, 0 = da vedere), da sinistra.
    None se non si trovano."""
    import numpy as np
    w = image.width
    a = np.asarray(image.convert('L').crop((0, top, w, top + round(.07 * w)))).astype(int)
    d = max(3, round(.012 * w))                          # le barrette sono più sottili di così
    if a.shape[0] < 2 * d + 2:
        return None
    mid = a[d:-d]
    thin = (mid - a[:-2 * d] > 25) & (mid - a[2 * d:] > 25)   # più chiara di sopra e di sotto
    count = thin.sum(axis=1)
    y = int(np.argmax(count))
    if count[y] < w * .3:
        return None
    on = thin[y]
    row = mid[y]
    segs, start = [], None
    for x, v in enumerate([*on, False]):
        if v and start is None:
            start = x
        elif not v and start is not None:
            segs.append((start, x))
            start = None
    merged = []                                          # buchi di 1-2 px dentro una barretta
    for s0, s1 in segs:
        if merged and s0 - merged[-1][1] <= 2:
            merged[-1] = (merged[-1][0], s1)
        else:
            merged.append((s0, s1))
    merged = [(s0, s1) for s0, s1 in merged if s1 - s0 > w * .015]
    if not 1 <= len(merged) <= 30:
        return None
    white = row.max() - 25                               # parte vista: il bianco pieno
    fills = [float((row[s0:s1] >= white).mean()) for s0, s1 in merged]
    return [1.0 if f > .92 else 0.0 if f < .05 else round(f, 2) for f in fills]   # bordi sfumati


def _jpeg(image):
    out = io.BytesIO()
    image.convert('RGB').save(out, 'JPEG', quality=92)
    return out.getvalue()


def crop(raw):
    """(foto della storia, foto profilo o None). Senza riquadro riconosciuto: (raw, None)."""
    photo, avatar, _ = read(raw)
    return photo, avatar


def read(raw):
    """(foto della storia, foto profilo o None, barrette o None). Senza riquadro: (raw, None, None)."""
    try:
        image = Image.open(io.BytesIO(raw))
        image.load()
        box = _frame(image)
    except Exception:
        return raw, None, None
    if not box:
        return raw, None, None
    top, bottom = box
    w = image.width
    cx, cy, r = round(AVATAR[0] * w), round(top + AVATAR[1] * w), round(AVATAR[2] * w)
    avatar = image.crop((cx - r, cy - r, cx + r, cy + r))
    story = image.convert('RGB').crop((0, top, w, bottom))
    band = round(HEADER * w)
    cover = story.crop((0, band, w, band + max(4, band // 10))).resize((w, band)).filter(ImageFilter.GaussianBlur(band / 6))
    story.paste(cover, (0, 0))
    try:
        fills = bars(image, top)
    except Exception:
        fills = None
    return _jpeg(story), _jpeg(avatar), fills
