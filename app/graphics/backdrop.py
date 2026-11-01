"""Analisi dello sfondo dietro la scritta di HALF TIME / END OF 90' / FULL TIME.

Misura quanto è chiaro o scuro lo sfondo nella zona della scritta e decide se serve
un'ombra e quanto forte:

- scritta chiara su sfondo chiaro  -> ombra scura;
- scritta scura su sfondo scuro    -> alone chiaro;
- buon contrasto                   -> nessuna ombra (strength = 0).

La decisione usa il rapporto di contrasto WCAG fra il colore della scritta e la
luminanza dello sfondo (percentili, non la media: un volto chiaro in un angolo
non deve contare quanto tutta la zona).
"""
import io

import numpy as np
from PIL import Image

from graphics.common import DESIGN_H, DESIGN_W

# Zone della scritta in frazione della pagina (x, y, larghezza, altezza), misurate sulla
# grafica FULL TIME. Solo il titolo (in alto, ~7-18% dell'altezza): il risultato in basso
# sta gia' sulla sfumatura scura della grafica e ha la sua ombra.
_PHASE_REGIONS = [(0.07, 0.06, 0.86, 0.13)]
TEXT_REGIONS = {
    'half': _PHASE_REGIONS,
    'end_of_90': _PHASE_REGIONS,
    'full': _PHASE_REGIONS,
}

CONTRAST_OK = 4.5      # da qui in su la scritta si legge bene: niente ombra
CONTRAST_BAD = 2.0     # da qui in giù serve l'ombra al massimo
MAX_ALPHA = 0.85       # opacità massima dell'ombra
MAX_BLUR = 28          # sfocatura massima dell'ombra, in pixel pagina 1080x1440


def _linear(channel):
    c = channel / 255.0
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def luminance(rgb):
    """Luminanza relativa 0..1 (WCAG). rgb: array (..., 3) con valori 0..255."""
    rgb = np.asarray(rgb, dtype=float)
    lin = _linear(rgb)
    return 0.2126 * lin[..., 0] + 0.7152 * lin[..., 1] + 0.0722 * lin[..., 2]


def contrast_ratio(lum_a, lum_b):
    hi, lo = np.maximum(lum_a, lum_b), np.minimum(lum_a, lum_b)
    return (hi + 0.05) / (lo + 0.05)


def page_backdrop(photo, frame):
    """Sfondo come appare sulla pagina 1080x1440: la foto posizionata con `frame`.
    Ridotto (270x360) perché serve solo a misurare."""
    from graphics.starting_xi import photo_box

    with Image.open(io.BytesIO(photo)) as src:
        src = src.convert('RGB')
        left, top, width, height = photo_box(src.size, frame or {})
    scale = 0.25
    page = Image.new('RGB', (round(DESIGN_W * scale), round(DESIGN_H * scale)))
    fitted = src.resize((max(1, round(width * scale)), max(1, round(height * scale))), Image.BILINEAR)
    page.paste(fitted, (round(left * scale), round(top * scale)))
    return page


def analyze(page, regions, text_rgb=(255, 255, 255)):
    """Decide l'ombra per la scritta.

    page: immagine PIL della pagina (qualsiasi risoluzione, proporzioni della pagina);
    regions: zone della scritta in frazione della pagina;
    text_rgb: colore della scritta.

    Ritorna {'strength': 0..1, 'color': (r, g, b), 'alpha': 0..1, 'blur': px,
             'contrast': rapporto, 'backdrop': luminanza 0..1}.
    """
    image = np.asarray(page.convert('RGB'))
    h, w = image.shape[:2]
    text_lum = float(luminance(np.array(text_rgb)))

    worst, backdrop = 99.0, 0.0
    for x, y, rw, rh in regions:
        x0, x1 = max(0, int(x * w)), min(w, max(int((x + rw) * w), int(x * w) + 1))
        y0, y1 = max(0, int(y * h)), min(h, max(int((y + rh) * h), int(y * h) + 1))
        lum = luminance(image[y0:y1, x0:x1]).ravel()
        if not lum.size:
            continue
        # La scritta è chiara -> conta la parte più chiara dello sfondo (5% più luminoso, 90° percentile);
        # è scura -> conta la parte più scura. Il caso peggiore decide.
        probe = np.percentile(lum, 90 if text_lum >= 0.18 else 10)
        ratio = float(contrast_ratio(text_lum, probe))
        if ratio < worst:
            worst, backdrop = ratio, float(probe)

    strength = float(np.clip((CONTRAST_OK - worst) / (CONTRAST_OK - CONTRAST_BAD), 0, 1))
    # Ombra del colore opposto alla scritta.
    color = (0, 0, 0) if text_lum >= 0.18 else (255, 255, 255)
    return {
        'strength': round(strength, 3),
        'color': color,
        'alpha': round(strength * MAX_ALPHA, 3),
        'blur': round(strength * MAX_BLUR, 1),
        'contrast': round(worst, 2),
        'backdrop': round(backdrop, 3),
    }


def shadow_for(kind, photo, frame, text_rgb=(255, 255, 255), regions=None):
    """Scorciatoia: analizza la foto di sfondo di una fase (half / end_of_90 / full)."""
    return analyze(page_backdrop(photo, frame), regions or TEXT_REGIONS[kind], text_rgb)


def css_shadow(decision, offset=4):
    """Valore CSS per text-shadow / drop-shadow, o '' se non serve."""
    if decision['strength'] <= 0.02:
        return ''
    r, g, b = decision['color']
    return f'0 {offset}px {decision["blur"]}px rgba({r},{g},{b},{decision["alpha"]})'
