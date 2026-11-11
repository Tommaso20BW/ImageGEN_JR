"""CITAZIONE IG, storia: dallo screenshot di una storia (telefono) prende la storia senza l'interfaccia
di Instagram e la foto profilo.

Nello screenshot la storia è un riquadro 9:16 su sfondo scuro uniforme: sopra ora e batteria, sotto
la barra "Invia messaggio". La storia resta intera (9:16); in cima si cancellano
solo barrette, foto profilo, nome, orario e icone, ricostruendo lo sfondo dai colori vicini: lì la
grafica rimette le sue. Se lo screenshot non ha questa forma (storia a tutto schermo, foto normale)
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
    if not 1.6 <= ratio <= 1.95:
        return None
    full = np.asarray(image.convert('RGB')).astype(int)        # bordo preciso, a piena risoluzione
    def story_row(y):
        return 0 <= y < full.shape[0] and (np.abs(full[y] - bg).max(axis=1) >= 14).mean() > .5
    for _ in range(8):
        if story_row(top - 1): top -= 1
        elif not story_row(top): top += 1
        else: break
    for _ in range(8):
        if story_row(bottom): bottom += 1
        elif not story_row(bottom - 1): bottom -= 1
        else: break
    return top, bottom


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


def _erase_header(story, avatar_box):
    """Toglie barrette, foto profilo, nome, orario e icone di Instagram in cima alla storia: solo quei
    pixel (più chiari dello sfondo intorno, più il cerchio della foto profilo) e li ricostruisce dai
    colori vicini. Il resto della foto resta com'è, quindi niente stacchi."""
    import cv2
    import numpy as np
    w = story.width
    band = round(HEADER * w)
    rgb = np.asarray(story.crop((0, 0, w, band))).copy()
    grey = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    k = max(3, (w // 8) | 1)                  # sfondo misurato largo: anche le scritte grandi spiccano
    bg = cv2.medianBlur(grey, min(k, 255))
    mask = ((grey.astype(int) - bg) > 28).astype(np.uint8)          # scritte, icone, barrette
    x0, y0, x1, y1 = avatar_box
    pad = round((x1 - x0) * .12)
    cv2.circle(mask, ((x0 + x1) // 2, (y0 + y1) // 2), (x1 - x0) // 2 + pad, 1, -1)
    grow = max(3, round(w * .008))
    mask = cv2.dilate(mask, np.ones((grow, grow), np.uint8), iterations=2)
    small = cv2.resize(rgb, (w // 2, band // 2), interpolation=cv2.INTER_AREA)
    small_mask = cv2.resize(mask, (w // 2, band // 2), interpolation=cv2.INTER_NEAREST)
    filled = cv2.inpaint(small, small_mask * 255, max(3, w // 60), cv2.INPAINT_TELEA)
    filled = cv2.GaussianBlur(cv2.resize(filled, (w, band), interpolation=cv2.INTER_CUBIC), (0, 0), max(2, w / 150))
    soft = cv2.GaussianBlur(mask.astype(np.float32), (0, 0), grow)[..., None].clip(0, 1)
    soft = np.maximum(soft, mask[..., None].astype(np.float32))
    out = (rgb * (1 - soft) + filled * soft).round().astype(np.uint8)
    story = story.copy()
    story.paste(Image.fromarray(out), (0, 0))
    return story


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
    edge = max(1, round(w * .002))           # il bordo dello screenshot è sfumato: via 2 px
    story = image.convert('RGB').crop((0, top + edge, w, bottom - edge))
    try:
        story = _erase_header(story, avatar_box=(cx - r, cy - top - edge - r, cx + r, cy - top - edge + r))
    except Exception:            # senza OpenCV: copre la fascia con la foto subito sotto
        band = round(HEADER * w)
        cover = story.crop((0, band, w, band + max(4, band // 10))).resize((w, band)).filter(ImageFilter.GaussianBlur(band / 6))
        story.paste(cover, (0, 0))
    try:
        fills = bars(image, top)
    except Exception:
        fills = None
    return _jpeg(story), _jpeg(avatar), fills
