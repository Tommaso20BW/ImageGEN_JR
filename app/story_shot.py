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


def _jpeg(image):
    out = io.BytesIO()
    image.convert('RGB').save(out, 'JPEG', quality=92)
    return out.getvalue()


def crop(raw):
    """(foto della storia, foto profilo o None). Senza riquadro riconosciuto: (raw, None)."""
    try:
        image = Image.open(io.BytesIO(raw))
        image.load()
        box = _frame(image)
    except Exception:
        return raw, None
    if not box:
        return raw, None
    top, bottom = box
    w = image.width
    cx, cy, r = round(AVATAR[0] * w), round(top + AVATAR[1] * w), round(AVATAR[2] * w)
    avatar = image.crop((cx - r, cy - r, cx + r, cy + r))
    story = image.convert('RGB').crop((0, top, w, bottom))
    band = round(HEADER * w)
    cover = story.crop((0, band, w, band + max(4, band // 10))).resize((w, band)).filter(ImageFilter.GaussianBlur(band / 6))
    story.paste(cover, (0, 0))
    return _jpeg(story), _jpeg(avatar)
