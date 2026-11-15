"""COMPLEANNO: poster "stampato" su carta crema con il giocatore a retino.

Titolo HAPPY / BIRTHDAY impilato a tutta larghezza, in alto data di nascita ed età, il giocatore
(una delle sue pose degli asset) stampato a retino nero + oro, ritagliato a forbici con un filo di
ombra, e una striscia nera incollata sopra con il nome in crema. Tutto è inchiostro sullo stesso
foglio: copertura irregolare, leggero fuori registro, grana, carta stropicciata e vignettatura.

Le pose arrivano da players/<slug>/ (Goal, o Saved per i portieri) e players_matchday/<slug>/
(pose_01 = Starting, pose_02 = Matchday). Tutte iniziano dalla testa e finiscono tagliate in basso,
quindi basta portarle alla stessa altezza perché la testa cada sempre allo stesso punto.
"""
import base64
import io
import re
import unicodedata
from datetime import date
from functools import lru_cache

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

from graphics.common import asset_dir

W, H = 1500, 2000
M = 80
ANTON = 'Anton-Regular.ttf'
MONO = 'SpecialElite-Regular.ttf'
INK = np.array([0.07, 0.07, 0.075], np.float32)
GOLD = np.array([0.80, 0.63, 0.33], np.float32)
CREAM = (238, 232, 219)
CELL, SMOOTH = 6.0, 0.35         # retino del giocatore: passo dei punti e quota di tono continuo
PLAYER_FOOT, PLAYER_CX = H - 110, W / 2 + 10
ZOOM_MIN, ZOOM_MAX = 0.4, 2.5
# Altezza del giocatore: le pose con le braccia al cielo inquadrano fino ai fianchi (persona più piccola
# nella foto), le altre fino alla vita: più basse, così testa e spalle hanno la stessa misura.
PLAYER_H = {'point_sky': 1560}
PLAYER_H_DEFAULT = 1250
STRIP_Y = H - 205                # centro della striscia del nome (il ritaglio finisce qui)
NAME_SIZE, NAME_MAX_SIZE = 170, 210
TEXT_GAP = 20                    # carta libera tra le scritte nere e il contorno del ritaglio
NAME_MAX_W = W - 2 * 70 - 40     # oltre questa larghezza il nome si rimpicciolisce
NAME_MAX = 28

GROUPS = (('matchday', 'Matchday'), ('starting', 'Starting'), ('goal', 'Goal'), ('saved', 'Saved'))
KITS = (('', 'Home'), ('away_pink', 'Away'), ('third_black', 'Third'),
        ('keeper_blue', 'Home'), ('keeper_green', 'Away'), ('keeper_orange', 'Third'))
_POSE_RE = re.compile(r'^(?P<slug>[a-z0-9_]+?)(?:_(?P<kit>away_pink|third_black|keeper_blue|keeper_green|keeper_orange))?'
                      r'_pose_(?P<num>\d\d)_(?P<pose>[a-z_]+)\.png$')


# ---------------------------------------------------------------- testo e dati
def clean_name(value):
    """Maiuscolo e senza accenti (il font della macchina da scrivere non li ha tutti)."""
    raw = unicodedata.normalize('NFKD', ' '.join(str(value or '').split()).upper())
    return ''.join(c for c in raw if not unicodedata.combining(c) and (c.isalnum() or c in " .'-"))[:NAME_MAX].strip()


def parse_birth(value):
    """'2005-05-04' (campo data) o '04.05.2005' -> date, altrimenti None."""
    text = str(value or '').strip()
    for pattern, order in ((r'^(\d{4})-(\d{1,2})-(\d{1,2})$', 'ymd'), (r'^(\d{1,2})[./-](\d{1,2})[./-](\d{4})$', 'dmy')):
        m = re.match(pattern, text)
        if m:
            a, b, c = (int(x) for x in m.groups())
            y, mo, d = (a, b, c) if order == 'ymd' else (c, b, a)
            try:
                return date(y, mo, d)
            except ValueError:
                return None
    return None


def age_on_birthday(born, today=None):
    """Anni che compie (o ha compiuto) nel compleanno di quest'anno."""
    today = today or date.today()
    return today.year - born.year


# ---------------------------------------------------------------- foto del giocatore
def player_photos(player):
    """Pose del giocatore per gruppo: [{id, group, kit, pose}] in ordine Matchday, Starting, Goal/Saved.
    id = percorso relativo alla cartella asset (è quello che torna dalla Mini App)."""
    keeper = player.role == 'goalkeeper'
    root = asset_dir()
    kit_order = {k: i for i, (k, _) in enumerate(KITS)}
    kit_label = dict(KITS)
    out = []
    for folder in ('players_matchday', 'players'):
        rows = []
        for path in sorted((root / folder / player.slug).glob('*.png')):
            m = _POSE_RE.match(path.name)
            if not m or m['slug'] != player.slug:
                continue
            if folder == 'players_matchday':
                group = {'01': 'starting', '02': 'matchday'}.get(m['num'])
                if not group:
                    continue
            else:
                group = 'saved' if keeper else 'goal'
            kit = m['kit'] or ''
            rows.append({'id': f'{folder}/{player.slug}/{path.name}', 'group': group,
                         'kit': kit_label.get(kit, 'Home'), 'pose': m['pose'],
                         '_k': ([g for g, _ in GROUPS].index(group), int(m['num']), kit_order.get(kit, 0))})
        out += rows
    out.sort(key=lambda r: r['_k'])
    for r in out:
        del r['_k']
    return out


def photo_path(photo_id, player=None):
    """Percorso del PNG scelto, solo dentro players/ o players_matchday/ (e del giocatore, se dato)."""
    parts = str(photo_id or '').split('/')
    m = _POSE_RE.match(parts[-1]) if len(parts) == 3 else None
    if not m or parts[0] not in ('players', 'players_matchday') or m['slug'] != parts[1]:
        raise ValueError('Foto non valida: sceglila di nuovo.')
    if player is not None and parts[1] != player.slug:
        raise ValueError('La foto non è del giocatore scelto.')
    path = asset_dir() / parts[0] / parts[1] / parts[2]
    if not path.is_file():
        raise ValueError('Foto non trovata negli asset.')
    return path


@lru_cache(maxsize=512)
def thumb(photo_id, size=(420, 560)):
    """Sagoma ritagliata stretta (data URL webp): quadretto della griglia e giocatore dell'editor."""
    with Image.open(photo_path(photo_id)) as im:
        im = im.convert('RGBA')
        im = im.crop(im.getbbox() or (0, 0, im.width, im.height))
        im.thumbnail(size, Image.LANCZOS)
        buf = io.BytesIO()
        im.save(buf, 'WEBP', quality=78)
    return 'data:image/webp;base64,' + base64.b64encode(buf.getvalue()).decode('ascii')


# ---------------------------------------------------------------- texture
def _up(a, size):
    return np.asarray(Image.fromarray(np.float32(a), 'F').resize(size, Image.BICUBIC), np.float32)


def _fbm(size, seed=0, octaves=6, base=4, persist=0.55):
    w, h = size
    rng = np.random.default_rng(seed)
    out = np.zeros((h, w), np.float32)
    amp, tot = 1.0, 0.0
    for o in range(octaves):
        n = base * 2 ** o
        out += _up(rng.random((max(2, int(n * h / w)) + 1, n + 1)).astype(np.float32), size) * amp
        tot += amp
        amp *= persist
    out /= tot
    out -= out.min()
    return out / max(out.max(), 1e-6)


def _fibers(size, seed=0, n=2500):
    w, h = size
    rng = np.random.default_rng(seed)
    im = Image.new('L', size, 128)
    d = ImageDraw.Draw(im)
    for _ in range(n):
        x, y, a = rng.random() * w, rng.random() * h, rng.random() * np.pi
        ln = rng.uniform(6, 30)
        d.line((x, y, x + np.cos(a) * ln, y + np.sin(a) * ln), fill=int(rng.choice([100, 160])), width=1)
    return np.asarray(im.filter(ImageFilter.GaussianBlur(0.6)), np.float32) / 255 - 0.5


def _crumple(size, seed=0, strength=1.0, folds=2):
    """Luce di carta stropicciata (1 = neutro): rughe 'ridged' + un paio di pieghe."""
    w, h = size
    rng = np.random.default_rng(seed)
    hgt = np.zeros((h, w), np.float32)
    for i, (b, a) in enumerate([(3, 1.0), (7, 0.5), (16, 0.22), (40, 0.08)]):
        n = _fbm(size, seed + 11 * i, octaves=2, base=b, persist=0.4)
        hgt += (1 - np.abs(n * 2 - 1)) ** 2 * a
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    for _ in range(folds):
        a = rng.uniform(-0.08, 0.08) + rng.choice([0, np.pi / 2])
        c = rng.uniform(0.35, 0.65) * (w * abs(np.cos(a)) + h * abs(np.sin(a)))
        hgt += np.abs(np.tanh((xx * np.cos(a) + yy * np.sin(a) - c) / 6)) * 0.06
    gy, gx = np.gradient(hgt)
    g = gx + gy * 1.3
    return np.clip(1 - g / (np.percentile(np.abs(g), 99) + 1e-6) * 0.07 * strength, 0.8, 1.15)


def _paper(size, color, seed=0):
    w, h = size
    base = np.ones((h, w, 3), np.float32) * np.array(color, np.float32) / 255
    tone = (1 + (_fbm(size, seed + 1, 4, 3) - 0.5) * 0.09 + (_fbm(size, seed + 2, 3, 180) - 0.5) * 0.05
            + _fibers(size, seed + 3) * 0.10)
    base *= tone[..., None]
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    edge = np.clip(np.minimum(np.minimum(xx, w - xx), np.minimum(yy, h - yy)) / (0.22 * min(w, h)), 0, 1)
    base *= (0.90 + 0.10 * edge)[..., None] * np.array([1, 0.985, 0.95], np.float32)[None, None]
    return np.clip(base, 0, 1)


def _ink_breakup(size, seed=0, amount=0.35, scale=220):
    n = _fbm(size, seed, octaves=4, base=scale // 40 + 2, persist=0.6)
    speck = _fbm(size, seed + 9, octaves=2, base=scale)
    cov = 1 - np.clip((n - (1 - amount)) * 3.0, 0, 1) * 0.6
    cov *= 1 - np.clip((speck - 0.82) * 6, 0, 1) * 0.8
    return np.clip(cov, 0, 1)


# ---------------------------------------------------------------- maschere
def _mask():
    return np.zeros((H, W), np.float32)


def _blur(m, r):
    return np.asarray(Image.fromarray(np.uint8(np.clip(m, 0, 1) * 255)).filter(ImageFilter.GaussianBlur(r)),
                      np.float32) / 255


def _shift(m, dx, dy):
    return np.roll(np.roll(m, dy, 0), dx, 1)


def _put(dst, m, xy, anchor='mm', angle=0):
    if angle:
        m = m.rotate(angle, Image.BICUBIC, expand=True)
    a = np.asarray(m, np.float32) / 255
    h, w = a.shape
    x = int(round(xy[0] - {'l': 0, 'm': w / 2, 'r': w}[anchor[0]]))
    y = int(round(xy[1] - {'t': 0, 'm': h / 2, 'b': h}[anchor[1]]))
    x0, y0, x1, y1 = max(x, 0), max(y, 0), min(x + w, W), min(y + h, H)
    if x1 > x0 and y1 > y0:
        dst[y0:y1, x0:x1] = np.maximum(dst[y0:y1, x0:x1], a[y0 - y:y1 - y, x0 - x:x1 - x])
    return dst


@lru_cache(maxsize=16)
def _font(name, size):
    return ImageFont.truetype(str(asset_dir() / 'fonts' / name), size)


def _word(text, size, font=ANTON, tracking=0):
    """Maschera L del testo, ritagliata stretta."""
    fnt = _font(font, size)
    widths = [fnt.getlength(c) for c in text]
    asc, desc = fnt.getmetrics()
    m = Image.new('L', (int(sum(widths) + tracking * max(len(text) - 1, 0)) + 40, asc + desc + 40), 0)
    d = ImageDraw.Draw(m)
    x = 20
    for c, w in zip(text, widths):
        d.text((x, 20), c, font=fnt, fill=255)
        x += w + tracking
    return m.crop(m.getbbox() or (0, 0, 1, 1))


def _fit_w(m, width):
    return m.resize((int(width), max(1, int(m.height * width / m.width))), Image.LANCZOS)


def _screen(tone, cell, angle, soft=0.9):
    """Retino AM: tono 0..1 -> copertura a punti."""
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    t = np.deg2rad(angle)
    u = (xx * np.cos(t) + yy * np.sin(t)) / cell
    v = (-xx * np.sin(t) + yy * np.cos(t)) / cell
    d = np.sqrt((u - np.round(u)) ** 2 + (v - np.round(v)) ** 2)
    return np.clip((np.sqrt(np.clip(tone, 0, 1) / np.pi) - d) * cell / soft + 0.5, 0, 1)


def base_height(photo_id):
    """Altezza del giocatore a zoom 1 (px della pagina 1500x2000)."""
    m = _POSE_RE.match(str(photo_id).split('/')[-1])
    return PLAYER_H.get(m['pose'] if m else '', PLAYER_H_DEFAULT)


def clean_frame(frame):
    """Posizione scelta nell'editor: x, y = spostamento (frazione della pagina), zoom = scala.
    0, 0, 1 = posizione automatica (centrato, base in basso)."""
    frame = frame if isinstance(frame, dict) else {}
    out = {}
    for k, lo, hi, d in (('x', -0.6, 0.6, 0.0), ('y', -0.6, 0.6, 0.0), ('zoom', ZOOM_MIN, ZOOM_MAX, 1.0)):
        try:
            v = float(frame.get(k, d))
        except (TypeError, ValueError):
            v = d
        out[k] = round(min(hi, max(lo, v if np.isfinite(v) else d)), 5)
    return out


def _player_layers(path, frame=None):
    """(alpha, luminanza) del giocatore: alto secondo la posa x zoom, centro e base spostati di x, y."""
    frame = clean_frame(frame)
    height = max(50, int(base_height(path.name) * frame['zoom']))
    with Image.open(path) as im:
        p = im.convert('RGBA')
    p = p.crop(p.getbbox())
    p = p.resize((max(1, int(p.width * height / p.height)), height), Image.LANCZOS)
    alpha, lum = _mask(), np.ones((H, W), np.float32)
    a = np.asarray(p.split()[-1], np.float32) / 255
    g = np.clip((np.asarray(p.convert('L'), np.float32) / 255 - 0.5) * 1.5 + 0.55, 0, 1)
    h, w = a.shape
    x = int(PLAYER_CX + frame['x'] * W - w / 2)
    y = int(PLAYER_FOOT + frame['y'] * H - h)
    x0, y0, x1, y1 = max(x, 0), max(y, 0), min(x + w, W), min(y + h, H)
    alpha[y0:y1, x0:x1] = a[y0 - y:y1 - y, x0 - x:x1 - x]
    lum[y0:y1, x0:x1] = g[y0 - y:y1 - y, x0 - x:x1 - x]
    # niente alone semitrasparente del ritaglio (farebbe "fumo" sulle lettere)
    alpha = np.clip((alpha - 0.5) * 3 + 0.5, 0, 1)
    alpha = np.asarray(Image.fromarray(np.uint8(alpha * 255)).filter(ImageFilter.MinFilter(3)), np.float32) / 255
    return alpha, lum


def _scissor_mask(alpha, gap=22, smooth=30, eps=14, jitter=7, seed=4):
    """Ritaglio fatto a mano con le forbici attorno al giocatore: tagli dritti, spigoli irregolari."""
    import cv2
    a = np.uint8(alpha > 0.5) * 255
    k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * smooth + 1, 2 * smooth + 1))
    a = cv2.morphologyEx(a, cv2.MORPH_CLOSE, k)
    a = cv2.dilate(a, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * gap + 1, 2 * gap + 1)))
    cnts, _ = cv2.findContours(a, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    if not cnts:
        return _mask()
    poly = cv2.approxPolyDP(max(cnts, key=cv2.contourArea), eps, True)[:, 0, :].astype(np.float32)
    poly += np.random.default_rng(seed).normal(0, jitter, poly.shape)
    big = np.zeros((H * 2, W * 2), np.uint8)
    cv2.fillPoly(big, [np.int32(poly * 2)], 255, cv2.LINE_AA)
    return np.asarray(Image.fromarray(big).resize((W, H), Image.LANCZOS), np.float32) / 255


def _grow(m, px):
    """Maschera allargata di px pixel (bordo morbido)."""
    import cv2
    k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * px + 1, 2 * px + 1))
    grown = cv2.dilate(np.uint8(np.clip(m, 0, 1) * 255), k)
    return np.asarray(Image.fromarray(grown).filter(ImageFilter.GaussianBlur(1.2)), np.float32) / 255


def name_size(name):
    """Corpo del nome: grande come nella grafica approvata, più piccolo se il nome è lungo."""
    w = _word(name, NAME_SIZE, MONO, 9).width
    return max(60, min(NAME_MAX_SIZE, int(NAME_SIZE * NAME_MAX_W / max(w, 1))))


def _label_strip(text, center, angle=-2.5, pad=(70, 46), seed=9, jitter=6):
    """Striscia di carta nera tagliata a forbici con il nome: (striscia, testo), già ruotati."""
    import cv2
    t = _word(text, name_size(text), MONO, 9)
    w, h = t.width + 2 * pad[0], t.height + 2 * pad[1]
    xs = np.linspace(0, w, 5)
    poly = np.array([(x, 0) for x in xs] + [(x, h) for x in xs[::-1]], np.float32)
    poly += np.random.default_rng(seed).normal(0, jitter, poly.shape)
    big = np.zeros((h * 2 + 80, w * 2 + 80), np.uint8)
    cv2.fillPoly(big, [np.int32((poly + 20) * 2)], 255, cv2.LINE_AA)
    strip = Image.fromarray(big).resize((w + 40, h + 40), Image.LANCZOS)
    tl = Image.new('L', strip.size, 0)
    tl.paste(t, (20 + pad[0], 20 + pad[1]))
    lab, txt = _mask(), _mask()
    _put(lab, strip, center, 'mm', angle)
    _put(txt, tl, center, 'mm', angle)
    return lab, txt


def _print(paper, inks, seed=0, breakup=0.15):
    out = paper.copy()
    for i, (cov, col) in enumerate(inks):
        cov = (cov * _ink_breakup((W, H), seed + 7 * i, breakup))[..., None]
        out = out * (1 - cov * (1 - col[None, None]))
    return out


def _finish(img, light, grain=0.035, seed=1, vignette=0.12):
    img = img + np.random.default_rng(seed).normal(0, grain, (H, W, 1)).astype(np.float32)
    img = img * light[..., None]
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    r = np.sqrt(((xx - W / 2) / (W / 2)) ** 2 + ((yy - H / 2) / (H / 2)) ** 2) / np.sqrt(2)
    return np.clip(img * (1 - vignette * r ** 2)[..., None], 0, 1)


def _jr_logo():
    """Logo JR nero in alto a destra: overlay 3:4 della FOTO + JR, portato a 1500x2000."""
    from graphics.photo_jr import _meta
    with Image.open(asset_dir() / 'canva' / _meta()['black']['overlay']) as im:
        lg = np.asarray(im.convert('RGBA').resize((W, H), Image.LANCZOS), np.float32) / 255
    return lg


# ---------------------------------------------------------------- grafica
def render(*, name, birth, photo, age=None, player=None, frame=None, ghost=False):
    """ghost=True: poster senza giocatore (sfondo dell'editor dove lo si sposta e zooma)."""
    name = clean_name(name)
    born = parse_birth(birth)
    if not name:
        raise ValueError('Scrivi il nome.')
    if not born:
        raise ValueError('Scrivi la data di nascita.')
    age = int(age) if str(age or '').strip().isdigit() else age_on_birthday(born)
    path = None if ghost else photo_path(photo, player)

    paper = _paper((W, H), CREAM, seed=3)
    light = _crumple((W, H), 5, 0.45)
    black, gold = _mask(), _mask()

    # riga alta: data ed età centrate, linea a tutta larghezza
    y = 95
    _put(black, _word(f'{born:%d.%m.%Y}   •   {age} YEARS OLD', 34, MONO, 6), (W / 2, y), 'mm')
    black[y + 32:y + 35, M:W - M] = 1

    # HAPPY / BIRTHDAY impilati alla stessa larghezza
    title = _mask()
    h1 = _fit_w(_word('HAPPY', 600, tracking=4), W - 2 * M)
    h2 = _fit_w(_word('BIRTHDAY', 600, tracking=2), W - 2 * M)
    _put(title, h1, (W / 2, 160), 'mt')
    _put(title, h2, (W / 2, 160 + h1.height + 18), 'mt')

    # giocatore ritagliato a forbici: il ritaglio finisce sotto la striscia del nome
    alpha, lum = _player_layers(path, frame) if path else (_mask(), np.ones((H, W), np.float32))
    cut = _scissor_mask(alpha)
    alpha[STRIP_Y:] = 0
    cut[STRIP_Y:] = 0
    sh = _shift(_blur(cut, 16), 14, 18) * (1 - cut)

    # le scritte nere (titolo, data, linea) non toccano mai il ritaglio: attorno resta un filo di carta
    keep = 1 - _grow(cut, TEXT_GAP)
    black = np.maximum(black, title) * keep
    tone = (1 - lum) ** 0.9
    black = np.maximum(black, (_screen(tone, CELL, 45) * (1 - SMOOTH) + tone * SMOOTH) * alpha)
    gtone = np.clip(0.75 - lum, 0, 1) * 1.1
    gold = np.maximum(gold, (_screen(gtone, CELL, 15) * (1 - SMOOTH) + gtone * 0.6 * SMOOTH) * alpha)
    gold = _shift(gold, 3, -2)          # leggero fuori registro

    # striscia nera incollata sopra, con ombra tutt'intorno (più marcata sotto)
    lab, txt = _label_strip(name, (W / 2, STRIP_Y))
    lb = _blur(lab, 22)
    lsh = np.maximum(_shift(lb, 14, 22) * 1.45, _shift(lb, 0, -12) * 1.5) * (1 - lab)
    black = np.maximum(black * (1 - lab), lab * (1 - txt))
    gold = gold * (1 - lab)

    paper = paper * (1 + 0.035 * cut * (1 - lab))[..., None]      # il ritaglio è carta un filo più chiara
    img = _print(paper, [(gold, GOLD), (black, INK)], seed=11)
    img = img * (1 - 0.42 * np.minimum(np.maximum(sh * (1 - lab), lsh), 1.3))[..., None]
    img = _finish(img, light)
    lg = _jr_logo()
    img = img * (1 - lg[..., 3:4]) + lg[..., :3] * lg[..., 3:4]

    out = Image.fromarray(np.uint8(np.clip(img, 0, 1) * 255 + 0.5))
    buf = io.BytesIO()
    out.save(buf, 'PNG')
    return buf.getvalue()
