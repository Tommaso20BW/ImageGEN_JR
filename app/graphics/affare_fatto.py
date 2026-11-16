"""AFFARE FATTO: poster crema e oro per un acquisto ufficiale. Allianz Stadium dorato sullo sfondo,
nome piccolo e spaziato in alto, cognome enorme in Didot oro (alto e stretto) dietro al giocatore,
giocatore davanti con un filtro caldo dorato, pennellate d'oro ai lati, sei frecce a destra,
AFFARE FATTO tra due fili in fondo, logo JR oro in alto a destra, grana fine su tutto.
L'utente carica la foto (scontornata dal servizio) e la sposta a mano nell'editor.
Asset: imagegen/affare_fatto/stadio.jpg e pennellate.png, fonts GFSDidot-Regular e BebasNeue2014."""
import io
import unicodedata
from functools import lru_cache

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont

from graphics import motm as M
from graphics.common import asset_dir

W, H = 1500, 2000
SERIF, SANS = 'JRDidoneCondensed-Regular.ttf', 'BebasNeue2014-Regular.ttf'
CREAM = (252, 235, 211)
FOG = (247, 224, 195)                     # crema della sfumatura in basso
INK = (196, 146, 70)                      # oro di AFFARE FATTO e dei fili
ARROWS = (190, 136, 56)
# firma in basso a sinistra, sopra il filo di AFFARE FATTO: dentro il riquadro, appoggiata in basso,
# nome rientrato un po' a destra, tutto inclinato di SIGN_TILT gradi (in salita)
SIGN_X0, SIGN_X1, SIGN_BOTTOM, SIGN_MAX_H, SIGN_NAME_IN, SIGN_TILT = 50, 360, 1885, 135, 40, 7
NAME_MAX, SURNAME_MAX = 16, M.SURNAME_MAX

# cognome: maiuscole da TITLE_TOP a TITLE_BASE, largo da TITLE_X0 a TITLE_X1
TITLE_TOP, TITLE_BASE, TITLE_X0, TITLE_X1 = 200, 785, 65, W - 65
FIRST_Y, FIRST_SIZE, FIRST_MAX_W = 84, 88, W - 300

# giocatore: altezza e piedi della posizione automatica (i piedi escono un po' sotto la pagina)
PLAYER_H, PLAYER_FOOT, PLAYER_CX = H + 40 - 430, H + 40, W / 2
ZOOM_MIN, ZOOM_MAX = 0.3, 2.5
MOVE = 1.0                                # spostamento libero: fino a una pagina intera

# filtro del giocatore: colori portati verso quelli del giocatore nell'esempio (media e contrasto
# in Lab), in parte, più calore (pelle calda, bianchi crema)
REF_MU = np.array((161.9, 136.2, 142.5), np.float32)
REF_SD = np.array((71.5, 9.4, 13.2), np.float32)
FILTER, WARM = .4, .5


def _dir():
    return asset_dir() / 'imagegen' / 'affare_fatto'


def clean_frame(frame):
    """x = spostamento del centro (frazione della larghezza), y = dei piedi (frazione dell'altezza),
    zoom = scala. 0, 0, 1 = posizione automatica."""
    frame = frame if isinstance(frame, dict) else {}
    out = {}
    for k, lo, hi, d in (('x', -MOVE, MOVE, 0.0), ('y', -MOVE, MOVE, 0.0), ('zoom', ZOOM_MIN, ZOOM_MAX, 1.0)):
        try:
            v = float(frame.get(k, d))
        except (TypeError, ValueError):
            v = d
        out[k] = round(min(hi, max(lo, v if np.isfinite(v) else d)), 5)
    return out


def base_scale(size):
    w, h = size
    return min(PLAYER_H / h, W * 1.1 / w)


def person_box(size, frame=None, ax=0.5):
    """(x, y, larghezza, altezza) della persona nella pagina (stessi conti dell'editor)."""
    f = clean_frame(frame)
    w, h = size
    s = base_scale(size) * f['zoom']
    pw, ph = max(1, round(w * s)), max(1, round(h * s))
    foot = PLAYER_FOOT + f['y'] * H
    cx = PLAYER_CX + f['x'] * W
    return round(cx - pw * ax), round(foot - ph), pw, ph


def page_info(person=None):
    """Misure per l'editor della Mini App (09b-compleanno.js, bdLayout)."""
    return {'w': W, 'h': H, 'cx': PLAYER_CX, 'foot': PLAYER_FOOT, 'cut': H, 'zoom': [ZOOM_MIN, ZOOM_MAX], 'move': MOVE}


# ---------------------------------------------------------------- aiuti

def _f32(im):
    return np.asarray(im, np.float32)


def _blur(a, r):
    return _f32(Image.fromarray(np.uint8(np.clip(a, 0, 1) * 255)).filter(ImageFilter.GaussianBlur(r))) / 255


def _font(name, size):
    return ImageFont.truetype(str(asset_dir() / 'fonts' / name), max(1, int(size)))


def _text_mask(text, name, size, tracking=0):
    f = _font(name, size)
    w = int(sum(f.getlength(c) for c in text) + tracking * max(len(text) - 1, 0)) + size
    m = Image.new('L', (max(w, 1), int(size * 2)), 0)
    d = ImageDraw.Draw(m)
    x = size // 2
    for c in text:
        d.text((x, int(size * .4)), c, font=f, fill=255)
        x += f.getlength(c) + tracking
    return m


def _cover(im, w, h, cy=.5):
    k = max(w / im.width, h / im.height)
    im = im.resize((round(im.width * k), round(im.height * k)), Image.LANCZOS)
    x, y = (im.width - w) // 2, int((im.height - h) * cy)
    return im.crop((x, y, x + w, y + h))


def _paste(dst, a, x, y):
    """Maschera a (0-1) dentro dst in (x, y), tenendo il massimo."""
    h, w = a.shape
    x0, y0, x1, y1 = max(x, 0), max(y, 0), min(x + w, W), min(y + h, H)
    if x1 > x0 and y1 > y0:
        dst[y0:y1, x0:x1] = np.maximum(dst[y0:y1, x0:x1], a[y0 - y:y1 - y, x0 - x:x1 - x])


def _over(img, rgb, a):
    return img * (1 - a[..., None]) + np.asarray(rgb, np.float32) * a[..., None]


def _plain(text):
    return ''.join(c for c in unicodedata.normalize('NFKD', text) if not unicodedata.combining(c))


# ---------------------------------------------------------------- parti fisse

@lru_cache(maxsize=1)
def _background():
    """Allianz virato seppia (ombre marroni, luci crema), crema pieno in alto."""
    with Image.open(_dir() / 'stadio.jpg') as im:
        img = _f32(_cover(im.convert('RGB'), W, H, .2).filter(ImageFilter.GaussianBlur(1.5)))
    lum = img.mean(-1, keepdims=True) / 255
    sh, mid, hi = (np.array(c, np.float32) for c in ((62, 42, 20), (196, 146, 78), (255, 241, 214)))
    tone = np.where(lum < .5, sh + (mid - sh) * (lum / .5), mid + (hi - mid) * ((lum - .5) / .5))
    img = img * .2 + tone * .8
    yy = np.arange(H, dtype=np.float32)[:, None]
    sky = np.broadcast_to(np.clip(1 - (yy - 300) / 450, 0, 1) ** 1.5 * .85, (H, W))
    return _over(img, CREAM, sky)


@lru_cache(maxsize=1)
def _gold():
    """Oro piatto con la grana fine della foglia d'oro."""
    with Image.open(asset_dir() / 'word_textures' / 'potm_oro.jpg') as im:
        foil = _f32(_cover(im.convert('L'), W, H)) / 255
    l = np.clip(.5 + (foil - _blur(foil, 20)) * 2.2, 0, 1)[..., None]
    return np.array((198, 146, 66), np.float32) * (1 - l) + np.array((230, 190, 118), np.float32) * l


@lru_cache(maxsize=1)
def _strokes():
    """Pennellate d'oro ai lati (colore, alpha): la luce della pennellata fa da sfumatura tra oro
    pieno e riflesso chiaro."""
    with Image.open(_dir() / 'pennellate.png') as im:
        rc = _f32(_cover(im.convert('RGB'), W, H))
    a = np.clip((rc.max(-1) - 30) / 110, 0, 1)
    l = np.clip((rc.max(-1) - 60) / 170, 0, 1)[..., None]
    rgb = np.array((214, 160, 74), np.float32) * (1 - l) + np.array((252, 222, 150), np.float32) * l
    return rgb, a


@lru_cache(maxsize=1)
def _arrows():
    ch = Image.new('L', (60, 200), 0)
    d = ImageDraw.Draw(ch)
    for i in range(6):
        y = 6 + i * 29
        d.polygon([(4, y + 20), (30, y), (56, y + 20), (56, y + 32), (30, y + 12), (4, y + 32)], fill=255)
    m = np.zeros((H, W), np.float32)
    _paste(m, _f32(ch.resize((48, 160), Image.LANCZOS)) / 255, 1405, 1305)
    return m


@lru_cache(maxsize=1)
def _label():
    """AFFARE FATTO tra due fili sottili."""
    m = np.zeros((H, W), np.float32)
    lm = _text_mask('AFFARE FATTO', SANS, 60, 25)
    lm = lm.crop(lm.getbbox())
    ly = 1926
    _paste(m, _f32(lm) / 255, int(W / 2 - lm.width / 2), ly - lm.height // 2)
    gap = lm.width / 2 + 28
    m[ly - 2:ly + 2, 100:int(W / 2 - gap)] = 1
    m[ly - 2:ly + 2, int(W / 2 + gap):W - 100] = 1
    return m


def _fill_nonzero(mask, pts):
    """Riempie il contorno con la regola nonzero (come i browser per l'SVG): dove il tratto passa sopra
    sé stesso resta pieno. ImageDraw.polygon usa pari/dispari e lì lascia dei buchi."""
    h, w = mask.shape
    a, b = pts, np.roll(pts, -1, 0)
    keep = a[:, 1] != b[:, 1]
    a, b = a[keep], b[keep]
    if not len(a):
        return
    y0 = max(int(np.floor(min(pts[:, 1].min(), h))), 0)
    y1 = min(int(np.ceil(pts[:, 1].max())) + 1, h)
    if y1 <= y0:
        return
    ys = np.arange(y0, y1) + .5
    lo, hi = np.minimum(a[:, 1], b[:, 1]), np.maximum(a[:, 1], b[:, 1])
    hit = (ys[:, None] >= lo) & (ys[:, None] < hi)                      # righe x lati
    t = (ys[:, None] - a[:, 1]) / (b[:, 1] - a[:, 1])
    xs = a[:, 0] + t * (b[:, 0] - a[:, 0])
    dirs = np.sign(b[:, 1] - a[:, 1])
    for r in np.where(hit.any(1))[0]:
        m = hit[r]
        order = np.argsort(xs[r, m])
        x, wnd = xs[r, m][order], np.cumsum(dirs[m][order])
        row = mask[y0 + r]
        for i in np.where(wnd[:-1] != 0)[0]:
            c0, c1 = max(int(np.ceil(x[i] - .5)), 0), min(int(np.floor(x[i + 1] - .5)) + 1, w)
            if c1 > c0:
                row[c0:c1] = True


def _signature(name, surname, style=None):
    """Firma scritta a mano (calligrapher.ai, graphics/firma.py): nome sopra e cognome sotto, piena e
    piatta nell'oro di AFFARE FATTO, appena inclinata in salita, in basso a sinistra. Sempre diversa
    (stile a caso, uguale per nome e cognome). Maschera 0..1; vuota se il sito non risponde."""
    from graphics import firma

    m = np.zeros((H, W), np.float32)
    lines = [name.title(), surname.title()]
    try:
        data = firma.paths(lines, style)
    except Exception as exc:                                 # noqa: BLE001 - senza firma, ma la grafica esce
        try:
            from log import warn
            warn('FIRMA', f'Firma non creata ({exc}): poster senza firma')
        except Exception:                                    # noqa: BLE001
            pass
        return m
    polys = [[p for p in (firma.polygons(d) for d in ds) if len(p) > 2] for ds in data]
    boxes = [np.concatenate([np.array(p) for p in ps]) if ps else None for ps in polys]
    if all(b is None for b in boxes):
        return m
    widths = [np.ptp(b[:, 0]) if b is not None else 0 for b in boxes]
    heights = [np.ptp(b[:, 1]) if b is not None else 0 for b in boxes]
    gap = .1 * max(heights)
    k = min((SIGN_X1 - SIGN_X0) / max(widths), SIGN_MAX_H / (sum(heights) + gap))
    up = 3                                                   # disegnata grande e ridotta: bordi morbidi
    big = np.zeros((H * up, W * up), bool)
    y = SIGN_BOTTOM - (sum(heights) + gap) * k
    for i, (ps, bx) in enumerate(zip(polys, boxes)):
        if bx is None:
            continue
        x0, y0 = bx[:, 0].min(), bx[:, 1].min()
        ox = SIGN_X0 + (SIGN_NAME_IN if i == 0 else 0)
        for p in ps:
            q = [(((px - x0) * k + ox) * up, ((py - y0) * k + y) * up) for px, py in p]
            _fill_nonzero(big, np.array(q, np.float64))
        y += heights[i] * k + gap * k
    cx, cy = (SIGN_X0 + SIGN_X1) / 2 * up, (SIGN_BOTTOM - SIGN_MAX_H / 2) * up
    big = Image.fromarray(np.uint8(big) * 255).rotate(SIGN_TILT, resample=Image.BICUBIC, center=(cx, cy))
    return _f32(big.resize((W, H), Image.LANCZOS)) / 255


@lru_cache(maxsize=1)
def _jr_logo():
    from graphics.photo_jr import _meta
    with Image.open(asset_dir() / 'canva' / _meta()['gold']['overlay']) as im:
        return im.convert('RGBA').resize((W, H), Image.LANCZOS)


# ---------------------------------------------------------------- scritte

def _surname(surname):
    """Cognome Didot stirato in altezza fino a riempire la riga; gli accenti restano bassi,
    appena sopra le maiuscole (allungati finirebbero sul logo)."""
    full, plain = _text_mask(surname, SERIF, 400), _text_mask(_plain(surname), SERIF, 400)
    cb = _text_mask('H', SERIF, 400).getbbox()
    sb = full.getbbox()
    ky = (TITLE_BASE - TITLE_TOP) / (cb[3] - cb[1])
    w = TITLE_X1 - TITLE_X0

    def stretch(m):
        m = m.crop((sb[0], 0, sb[2], m.height)).resize((w, int(m.height * ky)), Image.LANCZOS)
        a = _f32(m) / 255
        for _ in range(2):                                   # aste un filo più piene, solo in orizzontale
            p = np.pad(a, ((0, 0), (1, 1)))                  # senza far rientrare il bordo dall'altro lato
            a = np.maximum(a, np.maximum(p[:, :-2], p[:, 2:]))
        return a

    sa, pa = stretch(full), stretch(plain)
    r0 = int(cb[1] * ky)
    acc = np.clip(sa - pa, 0, 1)
    acc[r0 - 6:] = 0
    rows = np.where(acc.max(1) > .1)[0]
    if len(rows):
        a = acc[rows[0]:rows[-1] + 1]
        ah = min(60, a.shape[0])
        a = _f32(Image.fromarray(np.uint8(a * 255)).resize((a.shape[1], ah), Image.LANCZOS)) / 255
        pa[r0 - 16 - ah:r0 - 16] = np.maximum(pa[r0 - 16 - ah:r0 - 16], a)
    m = np.zeros((H, W), np.float32)
    _paste(m, pa, TITLE_X0, int(TITLE_BASE - cb[3] * ky))
    return m


def _first(name):
    """Nome piccolo e molto spaziato, centrato in alto."""
    m = np.zeros((H, W), np.float32)
    if not name:
        return m
    for tracking in range(64, 4, -6):                     # nomi lunghi: meno spazio tra le lettere
        fm = _text_mask(name, SERIF, FIRST_SIZE, tracking).filter(ImageFilter.MaxFilter(3))
        fm = fm.crop(fm.getbbox())
        if fm.width <= FIRST_MAX_W:
            break
    if fm.width > FIRST_MAX_W:
        fm = fm.resize((FIRST_MAX_W, fm.height), Image.LANCZOS)
    fm = fm.resize((fm.width, int(fm.height * 1.12)), Image.LANCZOS)
    _paste(m, _f32(fm) / 255, int(W / 2 - fm.width / 2), FIRST_Y)
    return m


# ---------------------------------------------------------------- giocatore

def grade(person):
    """Filtro dorato del giocatore (RGBA in, RGB float out): colori verso quelli dell'esempio,
    più calore, appena ammorbidito."""
    base = person.convert('RGB').filter(ImageFilter.GaussianBlur(.6))
    lab = cv2.cvtColor(np.asarray(base), cv2.COLOR_RGB2LAB).astype(np.float32)
    sel = _f32(person.getchannel('A')) > 200
    if sel.sum() < 50:
        sel = _f32(person.getchannel('A')) > 20
    if sel.any():
        mu, sd = lab[sel].mean(0), lab[sel].std(0) + 1e-3
        lab = (lab - mu) / sd * REF_SD + REF_MU
    c = cv2.cvtColor(np.uint8(np.clip(lab, 0, 255)), cv2.COLOR_LAB2RGB).astype(np.float32)
    c = c * FILTER + _f32(base) * (1 - FILTER)
    im = ImageEnhance.Color(Image.fromarray(np.uint8(np.clip(c, 0, 255)))).enhance(1 + .4 * WARM)
    c = _f32(im)
    return c * (1 - WARM) + c * np.array((1.05, .93, .84), np.float32) * WARM


def _player(img, person, frame):
    p = M.trim(person)
    x, y, pw, ph = person_box(p.size, frame, M.centroid(p))
    p = p.resize((pw, ph), Image.LANCZOS)
    pa = np.clip((_f32(p.getchannel('A')) / 255 - .5) * 3 + .5, 0, 1)
    c = grade(p)
    PL, PA = np.zeros((H, W, 3), np.float32), np.zeros((H, W), np.float32)
    x0, y0, x1, y1 = max(x, 0), max(y, 0), min(x + pw, W), min(y + ph, H)
    if x1 <= x0 or y1 <= y0:
        return img
    PL[y0:y1, x0:x1] = c[y0 - y:y1 - y, x0 - x:x1 - x]
    PA[y0:y1, x0:x1] = pa[y0 - y:y1 - y, x0 - x:x1 - x]
    img = _over(img, PL, PA)
    # luce dorata sul bordo della sagoma
    rim = np.clip(np.clip(PA - _blur(PA, 6), 0, 1) * 1.2 * PA, 0, .35)
    screen = 255 - (255 - img) * (255 - np.array((240, 190, 110), np.float32)) / 255
    return _over(img, screen, rim)


def _open(person):
    if isinstance(person, (bytes, bytearray)):
        person = Image.open(io.BytesIO(person))
    return person.convert('RGBA')


# ---------------------------------------------------------------- pagina

def render(*, surname, name='', person=None, frame=None, ghost=False):
    """PNG del poster. person = scontornato (byte o Image); ghost=True: senza giocatore (editor)."""
    surname = M.clean_text(surname, SURNAME_MAX)
    name = M.clean_text(name, NAME_MAX)
    if not surname:
        raise ValueError('Scrivi il cognome.')
    if not ghost and person is None:
        raise ValueError('Carica la foto.')

    gold = _gold()
    img = _over(_background(), gold, _surname(surname))
    img = _over(img, gold, _first(name))
    if not ghost:
        img = _player(img, _open(person), frame)

    yy = np.arange(H, dtype=np.float32)[:, None]
    img = _over(img, FOG, np.broadcast_to(np.clip((yy - 1640) / 330, 0, 1) ** 1.3 * .93, (H, W)))
    rgb, a = _strokes()
    img = _over(img, rgb, a)
    # parte bassa sfumata nel crema (niente sfocatura), così AFFARE FATTO si legge
    img = _over(img, FOG, np.broadcast_to(np.clip((yy - 1560) / 340, 0, 1) ** 1.1 * .97, (H, W)))
    img = _over(img, INK, _label())
    if not ghost:                                            # nell'editor niente firma: è a caso a ogni invio
        img = _over(img, INK, _signature(name, surname))
    img = _over(img, ARROWS, _arrows())

    out = Image.fromarray(np.uint8(np.clip(img, 0, 255))).convert('RGBA')
    out.alpha_composite(_jr_logo())
    g = _f32(out.convert('RGB')) + np.random.default_rng(5).normal(0, 7, (H, W, 1)).astype(np.float32)
    buf = io.BytesIO()
    Image.fromarray(np.uint8(np.clip(g, 0, 255))).save(buf, 'PNG')
    return buf.getvalue()
