"""MAN OF THE MATCH: poster chiaro con il cognome enorme vellutato, il nome in firma d'oro (3D leggero
e bagliori), il giocatore davanti con l'ombra a terra sotto gli appoggi e la partita in fondo.
L'utente carica la foto (scontornata dal servizio) e la sposta a mano: la testa non sale sopra
MAN OF THE MATCH e il logo Juventus, i piedi non scendono sotto la riga della partita.
Font negli asset: Anton-Regular, Inter-Medium, Corinthiago (firma)."""
import io
import unicodedata
from functools import lru_cache

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont
from scipy.ndimage import distance_transform_edt, gaussian_filter

from graphics.common import asset_dir

W, H = 1500, 2000
K = W / 1086                      # misure prese sull'esempio 1086x1448
BG = (251, 242, 238)
GOLD_TXT = (178, 138, 52)         # oro dei testi piccoli e delle linee
INK = (14, 14, 14)
SIG_FONT, SANS_FONT, SURN_FONT = 'Corinthiago.ttf', 'Inter-Medium.ttf', 'Anton-Regular.ttf'
JUVE_LOGO = ('team_logos', 'serie-a', 'Juventus-FC-v2017-mono.png')


def _k(*v):
    return tuple(round(x * K) for x in v)


HEAD_Y, HEAD_CAP, HEAD_W = _k(42, 20, 530)
LOGO_Y, LOGO_H = _k(83, 43)
HLINE_Y, = _k(103)
HLINE_L, HLINE_R = _k(305, 500), _k(586, 781)
SURN_X0, SURN_X1, SURN_Y0, SURN_Y1 = _k(124, 963, 163, 490)
SIGN_X0, SIGN_X1, SIGN_Y0, SIGN_Y1 = _k(256, 832, 191, 485)
SIGN_ANGLE = 2
FEET_Y, PLAYER_H = _k(1276, 906)
TEAMS_Y, TEAMS_CAP = _k(1323, 19)
BLINE_Y, = _k(1333)
BLINE_L0, BLINE_R1 = _k(176, 907)
COMP_Y, COMP_CAP, COMP_W = _k(1360, 14, 387)

# Limiti dell'editor (pixel della pagina): testa sotto il logo Juventus, piedi (e ombra) sopra la partita.
TOP_MIN = LOGO_Y + LOGO_H + 14
FOOT_MAX = TEAMS_Y - 34
ZOOM_MIN = 0.4
ZOOM_MAX = round((FOOT_MAX - TOP_MIN) / PLAYER_H, 3)
NAME_MAX, SURNAME_MAX, TEAM_MAX, COMP_MAX = 16, 14, 24, 40


def clean_text(value, limit, upper=True):
    text = ' '.join(str(value or '').split())
    return (text.upper() if upper else text)[:limit].strip()


def clean_name(value):
    """Nome in firma: sempre iniziale maiuscola e resto minuscolo, anche se scritto tutto grande
    (ogni parola: "jean-claude" -> "Jean-Claude")."""
    text = clean_text(value, NAME_MAX, upper=False).lower()
    out, up = [], True
    for ch in text:
        out.append(ch.upper() if up and ch.isalpha() else ch)
        up = not ch.isalpha() and ch != "'"
    return ''.join(out)


def clean_frame(frame):
    """x = spostamento del centro (frazione della larghezza), y = dei piedi (frazione dell'altezza),
    zoom = scala. 0, 0, 1 = posizione automatica. I limiti veri li mette person_box."""
    frame = frame if isinstance(frame, dict) else {}
    out = {}
    for k, lo, hi, d in (('x', -0.6, 0.6, 0.0), ('y', -0.6, 0.6, 0.0), ('zoom', ZOOM_MIN, ZOOM_MAX, 1.0)):
        try:
            v = float(frame.get(k, d))
        except (TypeError, ValueError):
            v = d
        out[k] = round(min(hi, max(lo, v if np.isfinite(v) else d)), 5)
    return out


def centroid(person):
    """Baricentro orizzontale della persona (0-1 della larghezza): è lui che va al centro."""
    a = np.asarray(person.getchannel('A'), np.float32)
    tot = a.sum()
    return float((a.sum(0) * np.arange(a.shape[1])).sum() / tot / max(a.shape[1], 1)) if tot else 0.5


def base_scale(size):
    w, h = size
    return min(PLAYER_H / h, W * 1.1 / w)


def person_box(size, frame=None, ax=0.5):
    """(x, y, larghezza, altezza) della persona nella pagina, dentro i limiti (stessi conti dell'editor)."""
    f = clean_frame(frame)
    w, h = size
    s0 = base_scale(size)
    zoom = min(f['zoom'], (FOOT_MAX - TOP_MIN) / (h * s0))
    pw, ph = max(1, round(w * s0 * zoom)), max(1, round(h * s0 * zoom))
    foot = FEET_Y + f['y'] * H
    foot = min(FOOT_MAX, max(TOP_MIN + ph, foot))
    cx = W / 2 + f['x'] * W
    return round(cx - pw * ax), round(foot - ph), pw, ph


def page_info(person):
    """Misure per l'editor della Mini App (09b-compleanno.js, bdLayout)."""
    return {'w': W, 'h': H, 'cx': W / 2, 'foot': FEET_Y, 'cut': H, 'top': TOP_MIN, 'bottom': FOOT_MAX,
            'zoom': [ZOOM_MIN, ZOOM_MAX]}


# ---------------------------------------------------------------- testo

def _font(name, size):
    return ImageFont.truetype(str(asset_dir() / 'fonts' / name), max(1, int(size)))


def _arr(im):
    return np.asarray(im, np.float32) / 255


def _ink(text, font, track=0., stroke=0):
    """Maschera del testo con lettere spaziate di `track` pixel, ritagliata al contenuto."""
    ws = [font.getlength(c) for c in text]
    im = Image.new('L', (int(sum(ws) + max(track, 0) * len(text)) + 80, int(font.size * 2) + 40), 0)
    d, x = ImageDraw.Draw(im), 20.
    for c, w in zip(text, ws):
        d.text((x, 20), c, font=font, fill=255, stroke_width=stroke, stroke_fill=255)
        x += w + track
    return im.crop(im.getbbox() or (0, 0, 1, 1))


@lru_cache(maxsize=16)
def _cap_size(name, cap):
    """Corpo del font la cui maiuscola è alta `cap` pixel."""
    s = cap
    for _ in range(4):
        f = _font(name, s)
        top, bot = f.getbbox('H')[1], f.getbbox('H')[3]
        s = max(1, round(s * cap / max(bot - top, 1)))
    return s


def _tracked(text, name, cap, width, min_track=2.):
    """Testo con maiuscola alta `cap` e spaziatura per arrivare a `width`; se è troppo lungo,
    spaziatura minima e corpo più piccolo."""
    f = _font(name, _cap_size(name, cap))
    base = _ink(text, f)
    track = (width - base.width) / max(len(text) - 1, 1)
    if track >= min_track:
        return _ink(text, f, track)
    m = _ink(text, f, min_track)
    if m.width > width:
        m = m.resize((width, max(1, round(m.height * width / m.width))), Image.LANCZOS)
    return m


class _Canvas:
    def __init__(self):
        rng = np.random.default_rng(1)
        self.a = np.ones((H, W, 3), np.float32) * np.array(BG, np.float32) / 255
        self.a += rng.normal(0, .006, (H, W, 1)).astype(np.float32)

    def put(self, mask, x, y, color):
        m = np.zeros((H, W), np.float32)
        x, y = int(round(x)), int(round(y))
        h, w = mask.height, mask.width
        y0, y1, x0, x1 = max(y, 0), min(y + h, H), max(x, 0), min(x + w, W)
        if y1 > y0 and x1 > x0:
            m[y0:y1, x0:x1] = _arr(mask)[y0 - y:y1 - y, x0 - x:x1 - x]
        c = color if isinstance(color, np.ndarray) else np.array(color, np.float32) / 255
        self.a = self.a * (1 - m[..., None]) + c * m[..., None]

    def line(self, x0, x1, y, toward_right, thick=2.4 * K):
        """Linea sottile che si assottiglia e sfuma verso l'esterno."""
        if x1 - x0 < 8:
            return
        xs = np.arange(int(x0), int(x1))
        t = (xs - x0) / (x1 - x0)
        t = t if toward_right else 1 - t           # 1 = estremo verso il centro
        th = .6 * K + (thick - .6 * K) * t ** .7
        al = np.clip(t * 3, 0, 1) * .95
        ys = np.arange(int(y - 8), int(y + 9))
        m = np.clip(th[None] / 2 + .5 - np.abs(ys[:, None] - y), 0, 1) * al[None]
        c = np.array(GOLD_TXT, np.float32) / 255
        sub = self.a[ys[0]:ys[-1] + 1, xs[0]:xs[-1] + 1]
        self.a[ys[0]:ys[-1] + 1, xs[0]:xs[-1] + 1] = sub * (1 - m[..., None]) + c * m[..., None]

    def layer(self, rgb, alpha, x, y):
        """Incolla rgb (h, w, 3) con alpha (h, w) a x, y."""
        x, y = int(round(x)), int(round(y))
        h, w = alpha.shape
        y0, y1, x0, x1 = max(y, 0), min(y + h, H), max(x, 0), min(x + w, W)
        if y1 <= y0 or x1 <= x0:
            return
        a = alpha[y0 - y:y1 - y, x0 - x:x1 - x, None]
        self.a[y0:y1, x0:x1] = self.a[y0:y1, x0:x1] * (1 - a) + rgb[y0 - y:y1 - y, x0 - x:x1 - x] * a

    def image(self):
        return Image.fromarray(np.uint8(np.clip(self.a, 0, 1) * 255 + .5))


# ---------------------------------------------------------------- cognome e firma

def _suede(h, w, seed=3):
    """Antracite vellutato a chiazze."""
    rng = np.random.default_rng(seed)
    out = np.ones((h, w), np.float32)
    for sigma, amp in ((9 * K, .10), (2.5 * K, .07), (.6 * K, .05)):
        n = gaussian_filter(rng.normal(0, 1, (h, w)).astype(np.float32), sigma)
        out += n / (n.std() + 1e-6) * amp
    return np.clip(np.array([41, 37, 32], np.float32) / 255 * out[..., None], 0, 1)


def _surname_mask(text):
    """Cognome Anton nel riquadro: alto quanto il riquadro, largo al massimo quanto lui
    (cognomi corti: allungati al più del 35%, poi centrati)."""
    m = _ink(text, _font(SURN_FONT, 600), -6)
    bw, bh = SURN_X1 - SURN_X0, SURN_Y1 - SURN_Y0
    w = min(bw, round(m.width * bh / m.height * 1.35))
    return m.resize((w, bh), Image.LANCZOS)


def _signature_mask(name):
    m = _ink(name, _font(SIG_FONT, 400)).filter(ImageFilter.MaxFilter(3))
    m = m.rotate(SIGN_ANGLE, Image.BICUBIC, expand=True)
    m = m.crop(m.getbbox() or (0, 0, 1, 1))
    s = min((SIGN_X1 - SIGN_X0) / m.width, (SIGN_Y1 - SIGN_Y0) / m.height)
    return m.resize((max(1, round(m.width * s)), max(1, round(m.height * s))), Image.LANCZOS)


def _gold(mask, ss=3):
    """Oro 3D leggero: smusso solo sul bordo e faccia piatta, chiaro in alto a sinistra, ambra sotto."""
    big = mask.resize((mask.width * ss, mask.height * ss), Image.LANCZOS)
    a = _arr(big)
    d = distance_transform_edt(a > .5)
    R = max(float(np.percentile(d[d > 0], 95)), 2.) if (d > 0).any() else 2.
    bev = np.clip(d / (R * .45), 0, 1)
    h = gaussian_filter(np.sin(bev * np.pi / 2), R * .12) * R * .9
    gy, gx = np.gradient(h)
    nz = 1 / np.sqrt(gx ** 2 + gy ** 2 + 1)
    nx, ny = -gx * nz, -gy * nz
    yy = np.linspace(1, -1, a.shape[0])[:, None]
    t = np.clip(-(ny + nx * .45) * 1.5 + yy * .15 + .1, -1, 1)
    stops = [(-1., (112, 74, 22)), (-.55, (168, 124, 52)), (-.15, (222, 190, 124)), (.2, (242, 218, 162)),
             (.55, (252, 236, 192)), (1., (255, 252, 236))]
    xs = np.array([v for v, _ in stops])
    col = np.stack([np.interp(t, xs, [c[i] for _, c in stops]) for i in range(3)], -1) / 255
    L = np.array([-.35, -.6, .72]); L /= np.linalg.norm(L)
    spec = np.clip(nx * L[0] + ny * L[1] + nz * L[2], 0, 1) ** 30 * .8
    col = np.clip(col + spec[..., None], 0, 1)
    return _arr(Image.fromarray(np.uint8(col * 255 + .5)).resize(mask.size, Image.BOX))


def _sparkles(c, mask, x0, y0, seed=7, n=4):
    """Bagliori: lampi sottili verticali (e uno orizzontale corto) su punti alti della firma."""
    a = _arr(mask)
    rng = np.random.default_rng(seed)
    ys, xs = np.where(a[:-1] - a[1:] > .5)                  # bordi superiori dei tratti
    keep = xs > mask.width * .25
    ys, xs = ys[keep], xs[keep]
    if not len(xs):
        return
    picks = []
    for _ in range(200):
        if len(picks) == n:
            break
        i = rng.integers(len(xs))
        px, py = xs[i] + x0, ys[i] + y0
        if all(abs(px - q[0]) > 110 * K for q in picks):
            picks.append((px, py))
    for px, py in picks:
        L = rng.uniform(70, 120) * K
        r = int(L) + 4
        bx0, by0 = max(int(px) - r, 0), max(int(py) - r, 0)
        bx1, by1 = min(int(px) + r, W), min(int(py) + r, H)
        yy, xx = np.mgrid[by0:by1, bx0:bx1].astype(np.float32)
        dx, dy = np.abs(xx - px), yy - py
        vert = np.exp(-(dx / (.9 * K)) ** 2) * np.clip(1 - np.abs(dy) / L, 0, 1) ** 2.2
        hor = np.exp(-(dy / K) ** 2) * np.clip(1 - dx / (L * .3), 0, 1) ** 2.2
        core = np.exp(-((dx ** 2 + dy ** 2) / (18 * K * K)))
        g = np.clip(np.maximum(vert * .8, hor * .7) + core * .7, 0, 1)[..., None]
        sub = c.a[by0:by1, bx0:bx1]
        c.a[by0:by1, bx0:bx1] = sub * (1 - g) + np.array([1., .98, .9], np.float32) * g


# ---------------------------------------------------------------- giocatore

def trim(person):
    person = person.convert('RGBA')
    box = person.getchannel('A').point(lambda v: 255 if v > 12 else 0).getbbox()
    return person.crop(box) if box else person


GRAIN = .03          # grana del giocatore (0 = niente)
BACK_SHADOW = (16, .09, 8, 10)   # ombra dietro il giocatore: sfocatura, forza, spostamento x, y


GROUND_SHADOW = (.5, .2)   # forza: contatto (stretta, sotto i punti d'appoggio), alone (larga e chiara)


def _ground_shadow(c, a, x, y):
    ph, pw = a.shape
    solid = a > .35
    has = solid.any(0)
    if not has.any():
        return
    low = ph - 1 - np.argmax(solid[::-1], 0)          # punto più basso di ogni colonna
    ground = low[has].max()
    near = np.where(has, np.exp(-((ground - low) / (12 * K)) ** 2), 0).astype(np.float32)
    m = int(140 * K)                                  # margine: l'ombra arriva a zero prima del bordo
    near = np.pad(near, m)
    core_x = gaussian_filter(near, 7 * K)
    halo_x = gaussian_filter(near, 34 * K)
    halo_x /= max(halo_x.max(), 1e-6)
    gy = y + ground
    rows = np.arange(gy - int(40 * K), gy + int(60 * K), dtype=np.float32)
    d = rows - gy
    core = np.exp(-.5 * ((d - 2.5 * K) / (4 * K)) ** 2)[:, None] * core_x[None] * GROUND_SHADOW[0]
    halo = np.exp(-.5 * ((d - 5 * K) / (14 * K)) ** 2)[:, None] * halo_x[None] * GROUND_SHADOW[1]
    sh = 1 - (1 - core) * (1 - halo)
    x0, y0 = x - m, int(rows[0])
    cx0, cy0 = max(x0, 0), max(y0, 0)
    cx1, cy1 = min(x0 + sh.shape[1], W), min(y0 + sh.shape[0], H)
    if cx1 > cx0 and cy1 > cy0:
        c.a[cy0:cy1, cx0:cx1] *= 1 - sh[cy0 - y0:cy1 - y0, cx0 - x0:cx1 - x0, None]


def _place_player(c, person, frame):
    from graphics.compleanno_storico import enhance
    p = trim(person)
    x, y, pw, ph = person_box(p.size, frame, centroid(p))
    p = enhance(p.resize((pw, ph), Image.LANCZOS))
    a = _arr(p.getchannel('A'))
    # foto tagliata in basso (mezzo busto): il taglio sfuma invece dell'ombra delle scarpe
    cut = (a[-1] > .5).mean() > .3
    if cut:
        fade = np.clip(np.arange(ph)[::-1] / (90 * K), 0, 1)[:, None]
        a = a * fade
    else:
        # ombra a terra: solo dove il giocatore tocca (o quasi) il pavimento, più scura dove appoggia
        # e più chiara dove resta sollevato; sfuma da sola ai lati, mai tagliata
        _ground_shadow(c, a, x, y)
    # ombra leggera dietro il giocatore: sagoma sfocata, spostata un po' in basso a destra
    pad = int(60 * K)
    big = np.pad(a, pad)
    soft = gaussian_filter(big, BACK_SHADOW[0] * K) * BACK_SHADOW[1]
    dx, dy = int(BACK_SHADOW[2] * K), int(BACK_SHADOW[3] * K)
    bx0, by0 = x - pad + dx, y - pad + dy
    cx0, cy0 = max(bx0, 0), max(by0, 0)
    cx1, cy1 = min(bx0 + soft.shape[1], W), min(by0 + soft.shape[0], H)
    if cx1 > cx0 and cy1 > cy0:
        c.a[cy0:cy1, cx0:cx1] *= 1 - soft[cy0 - by0:cy1 - by0, cx0 - bx0:cx1 - bx0, None]
    # grana leggera sul giocatore (fissa, uguale a ogni render)
    g = gaussian_filter(np.random.default_rng(9).normal(0, 1, a.shape).astype(np.float32), .6 * K)
    c.layer(np.clip(_arr(p.convert('RGB')) + g[..., None] * GRAIN, 0, 1), a, x, y)


# ---------------------------------------------------------------- pagina

@lru_cache(maxsize=1)
def _juve_logo():
    with Image.open(asset_dir().joinpath(*JUVE_LOGO)) as im:
        a = im.convert('RGBA').getchannel('A')
    a = a.crop(a.getbbox())
    return a.resize((round(a.width * LOGO_H / a.height), LOGO_H), Image.LANCZOS)


@lru_cache(maxsize=1)
def _jr_logo():
    """Logo JR nero in alto a destra (stesso overlay 3:4 delle altre grafiche)."""
    from graphics.photo_jr import _meta
    with Image.open(asset_dir() / 'canva' / _meta()['black']['overlay']) as im:
        return _arr(im.convert('RGBA').resize((W, H), Image.LANCZOS))


def _plain(text):
    """Senza accenti per il nome sul font firma (che non li ha tutti)."""
    raw = unicodedata.normalize('NFKD', text)
    return ''.join(ch for ch in raw if not unicodedata.combining(ch))


def render(*, surname, name='', home='', away='', comp='', person=None, frame=None, ghost=False):
    """PNG del poster. person = PNG scontornato (byte o Image); ghost=True: senza giocatore (editor)."""
    surname = clean_text(surname, SURNAME_MAX)
    name = clean_name(name)
    home, away = clean_text(home, TEAM_MAX), clean_text(away, TEAM_MAX)
    comp = clean_text(comp, COMP_MAX)
    if not surname:
        raise ValueError('Scrivi il cognome.')
    if not home or not away:
        raise ValueError('Scrivi le squadre.')
    c = _Canvas()

    # intestazione: MAN OF THE MATCH, logo Juventus tra due linee, JR nero in alto a destra
    t = _tracked('MAN OF THE MATCH', SANS_FONT, HEAD_CAP, HEAD_W)
    c.put(t, W / 2 - t.width / 2, HEAD_Y, GOLD_TXT)
    j = _juve_logo()
    c.put(j, W / 2 - j.width / 2, LOGO_Y, GOLD_TXT)
    c.line(*HLINE_L, HLINE_Y, True)
    c.line(*HLINE_R, HLINE_Y, False)
    jr = _jr_logo()
    c.a = c.a * (1 - jr[..., 3:]) + jr[..., :3] * jr[..., 3:]

    # cognome vellutato
    sm = _surname_mask(surname)
    sx = round(W / 2 - sm.width / 2)
    c.layer(_suede(sm.height, sm.width), _arr(sm), sx, SURN_Y0)

    # nome in firma: ombra morbida dietro, oro 3D leggero, bagliori
    if name:
        fm = _signature_mask(_plain(name))
        fx, fy = round(W / 2 - fm.width / 2), round((SURN_Y0 + SURN_Y1) / 2 - fm.height / 2)   # al centro esatto del cognome
        sh = Image.new('L', (fm.width + 120, fm.height + 120), 0)
        sh.paste(fm, (60, 60))
        sh = _arr(sh.filter(ImageFilter.GaussianBlur(7 * K))) * .45
        c.layer(np.zeros(sh.shape + (3,), np.float32), sh, fx - 60 + 4 * K, fy - 60 + 8 * K)
        c.layer(_gold(fm), _arr(fm), fx, fy)
        _sparkles(c, fm, fx, fy)

    # giocatore davanti
    if not ghost:
        if person is None:
            raise ValueError('Carica la foto.')
        if isinstance(person, (bytes, bytearray)):
            person = Image.open(io.BytesIO(person))
        _place_player(c, person, frame)

    # partita: CASA vs TRASFERTA tra due linee, sotto il campionato
    size2 = _cap_size(SANS_FONT, TEAMS_CAP) * 2          # a doppia grandezza: tratto più pieno
    half = lambda m: m.resize((max(1, m.width // 2), max(1, m.height // 2)), Image.LANCZOS)
    gap = 14 * K
    for _ in range(8):
        f2 = _font(SANS_FONT, size2)
        a1, a2 = half(_ink(home, f2, 6.4 * K, 1)), half(_ink(away, f2, 6.4 * K, 1))
        vs = half(_ink('vs', _font(SANS_FONT, size2 * .78), 3 * K, 1))
        tot = a1.width + vs.width + a2.width + 2 * gap
        if tot <= W - 2 * BLINE_L0 or size2 < 20:
            break
        size2 = int(size2 * .9)
    x = W / 2 - tot / 2
    c.put(a1, x, TEAMS_Y + max(0, a2.height - a1.height), INK)
    c.put(vs, x + a1.width + gap, TEAMS_Y + max(a1.height, a2.height) - vs.height, GOLD_TXT)
    c.put(a2, x + a1.width + vs.width + 2 * gap, TEAMS_Y + max(0, a1.height - a2.height), INK)
    c.line(BLINE_L0, x - 26 * K, BLINE_Y, True)
    c.line(x + tot + 26 * K, BLINE_R1, BLINE_Y, False)
    if comp:
        t = _tracked(comp, SANS_FONT, COMP_CAP, COMP_W)
        c.put(t, W / 2 - t.width / 2, COMP_Y, GOLD_TXT)

    out = io.BytesIO()
    c.image().save(out, 'PNG')
    return out.getvalue()
