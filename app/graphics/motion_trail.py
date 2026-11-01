"""Effetto movimento (scia orizzontale a sinistra) per la foto del MATCHDAY.

La scia nasce dal bordo sinistro della persona scontornata e si allunga a sinistra,
con righe sottili che svaniscono. Sul viso resta stretta, quasi sul limite; sugli
abiti scende più larga verso l'interno. Non si usa la maschera per ritagliare
(niente contorni visibili): scia e foto si fondono in modo continuo.

Tutte le misure sono frazioni della foto, quindi valgono per qualsiasi risoluzione.
"""
import io

import cv2
import numpy as np
from PIL import Image

LENGTH = 0.40        # lunghezza della scia (frazione della larghezza)
INSIDE = 0.12        # quanto entra negli abiti prima di sparire
INSIDE_FACE = 0.021  # sul viso: solo sul bordo
STRENGTH = 0.715     # intensità (massimo 0,8 di opacità)
FACE_END = 0.33      # altezza (frazione) sotto cui finisce il viso e iniziano gli abiti
BAND = (0.06, 1.12)  # fascia verticale (frazione dell'altezza) in cui compare la scia


def apply(photo, person):
    """Ritorna la foto con la scia. `photo`: byte della foto; `person`: PNG scontornato
    (la trasparenza è la maschera della persona, anche a risoluzione diversa).

    Foto normale -> JPEG. Foto già scontornata (PNG trasparente) -> PNG trasparente:
    la scia è semitrasparente e sotto si vede lo sfondo della grafica."""
    with Image.open(io.BytesIO(photo)) as image:
        rgba = np.asarray(image.convert('RGBA')).astype(np.float32) / 255
    rgb, own = rgba[..., :3], rgba[..., 3]
    h, w = rgb.shape[:2]
    buf = io.BytesIO()
    if own.min() < 0.98:
        mask = own
        color, g = trail_parts(rgb, mask)
        alpha = mask + g[..., 0] * (1 - mask)
        out = (rgb * mask[..., None] * (1 - g) + color * g) / np.maximum(alpha[..., None], 1e-4)
        done = np.dstack([np.clip(out, 0, 1), np.clip(alpha, 0, 1)])
        Image.fromarray((done * 255 + 0.5).astype(np.uint8), 'RGBA').save(buf, 'PNG')
        return buf.getvalue()
    with Image.open(io.BytesIO(person)) as cut:
        alpha = cut.convert('RGBA').getchannel('A').resize((w, h), Image.Resampling.LANCZOS)
    mask = np.asarray(alpha).astype(np.float32) / 255
    out = trail(rgb, mask)
    Image.fromarray((np.clip(out, 0, 1) * 255 + 0.5).astype(np.uint8)).save(buf, 'JPEG', quality=95, subsampling=0)
    return buf.getvalue()


def _left_edge(mask, sigma):
    """Primo pixel della persona in ogni riga, reso liscio tra le righe."""
    h, w = mask.shape
    solid = mask > 0.5
    has = solid.any(1)
    if not has.any():
        return None
    edge = np.argmax(solid, 1).astype(np.float32)
    rows = np.arange(h)
    edge = np.interp(rows, rows[has], edge[has]).astype(np.float32)   # righe vuote: la più vicina
    return cv2.GaussianBlur(edge[:, None], (1, 0), sigmaX=0.1, sigmaY=sigma)


def trail(rgb, mask, seed=3):
    color, g = trail_parts(rgb, mask, seed)
    return rgb * (1 - g) + color * g


def trail_parts(rgb, mask, seed=3):
    """(colore della scia, opacità per pixel (h, w, 1))."""
    h, w = mask.shape
    edge = _left_edge(mask, sigma=max(1.0, h * 0.0057))
    if edge is None:
        return rgb, np.zeros((h, w, 1), np.float32)
    length = max(8, int(w * LENGTH))
    t = np.linspace(1, 0, length, dtype=np.float32)
    kern = np.zeros((1, length * 2 + 1), np.float32)
    kern[0, length + 1:] = t                       # ogni pixel prende da quelli a destra: scia verso sinistra
    kern /= kern.sum()
    a = cv2.filter2D(mask, -1, kern, borderType=cv2.BORDER_REPLICATE)
    p = cv2.filter2D(rgb * mask[..., None], -1, kern, borderType=cv2.BORDER_REPLICATE)
    color = np.clip(p / np.maximum(a[..., None], 1e-4), 0, 1)

    # Righe sottili e irregolari.
    noise = np.random.default_rng(seed).random((h, 1)).astype(np.float32)
    noise = cv2.GaussianBlur(noise, (1, 0), sigmaX=0.1, sigmaY=max(1.0, h * 0.0028))
    noise = 0.8 + 0.4 * (noise - noise.min()) / max(float(np.ptp(noise)), 1e-6)

    y = np.linspace(0, 1, h, dtype=np.float32)[:, None]
    band = np.clip((y - BAND[0]) / 0.04, 0, 1) * np.clip((BAND[1] - y) / 0.2, 0, 1)
    body = np.clip((y - FACE_END) / 0.08, 0, 1)    # 0 = viso, 1 = collo e abiti
    opacity = np.clip(a * noise * band * (0.55 + 0.45 * body) * STRENGTH, 0, 0.8)

    # Peso lungo la riga: pieno fuori dal bordo, poi sfuma verso l'interno (smoothstep).
    inside = w * (INSIDE_FACE + (INSIDE - INSIDE_FACE) * body)
    x = np.arange(w, dtype=np.float32)[None, :]
    k = np.clip(1 - (x - edge) / inside, 0, 1)
    k = k * k * (3 - 2 * k)
    return color, (opacity * k)[..., None]
