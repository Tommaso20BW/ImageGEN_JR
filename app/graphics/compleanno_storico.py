"""COMPLEANNO STORICO: giocatori del passato. L'utente carica una foto, la persona viene
scontornata e messa davanti allo sfondo pronto (stadio scuro con HAPPY BIRTHDAY), con un
filtro nostalgico; sopra il titolo il nome in oro spaziato e il logo JR, nello stesso oro, in alto a destra.
Sfondo: imagegen/compleanno_storico/sfondo.jpg negli asset privati."""
import io
from functools import lru_cache

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

from graphics.common import asset_dir
from graphics.compleanno import ZOOM_MAX, ZOOM_MIN, clean_frame, clean_name  # noqa: F401

W, H = 1500, 2000
BG = ('imagegen', 'compleanno_storico', 'sfondo.jpg')
NAME_FONT = 'DharmaGothicEBold.otf'
NAME_Y = 196                       # centro del nome, appena sopra HAPPY BIRTHDAY
NAME_SIZE, NAME_MAX_W = 92, W - 260
NAME_SQUEEZE = 0.74                # lettere strette e alte come nell'esempio
NAME_MIN_SQUEEZE = 0.4            # nomi lunghi: si schiacciano fino a qui, poi si rimpiccioliscono
GOLD_TOP, GOLD_BOTTOM = (226, 192, 128), (186, 146, 84)
PERSON_H = 1480                    # altezza della persona a zoom 1 (base in fondo alla pagina)
PERSON_MAX_W = 1560
# Storia IG 9:16 (1500x2667): sfondo allungato con Meta AI (canva/story/compleanno_storico.jpg,
# HAPPY / BIRTHDAY su due righe), sceso di STORY_SHIFT perché il nome sopra il titolo resti fuori
# dalla zona alta di Instagram; persona più grande; logo JR in basso come il timbro delle Storie IG.
STORY_H = round(W * 16 / 9)
STORY_SHIFT = 160
STORY_TITLE_TOP = 301 + STORY_SHIFT     # cima di HAPPY nello sfondo della storia (già sceso)
TITLE_TOP = 256                          # cima di HAPPY nello sfondo 3:4
STORY_PERSON = 1.2


@lru_cache(maxsize=1)
def _background():
    with Image.open(asset_dir().joinpath(*BG)) as im:
        if im.size == (W, H):
            return im.convert('RGB')
        bg = im.convert('RGB').resize((W, H), Image.LANCZOS)
    return bg.filter(ImageFilter.UnsharpMask(2, 60, 2))      # sfondo piccolo: un filo di nitidezza


def _name_mask(text):
    # Nomi lunghi: stesso corpo, lettere schiacciate in larghezza quanto basta per stare in NAME_MAX_W.
    size = NAME_SIZE
    while True:
        fnt = ImageFont.truetype(str(asset_dir() / 'fonts' / NAME_FONT), size)
        track = size * 0.56
        widths = [fnt.getlength(c) for c in text]
        total = sum(widths) + track * (len(text) - 1)
        squeeze = min(NAME_SQUEEZE, NAME_MAX_W / max(total, 1))
        if squeeze >= NAME_MIN_SQUEEZE or size <= 40:
            break
        size -= 4
    asc, desc = fnt.getmetrics()
    m = Image.new('L', (int(total) + 40, asc + desc + 40), 0)
    d = ImageDraw.Draw(m)
    x = 20
    for c, w in zip(text, widths):
        d.text((x, 20), c, font=fnt, fill=255)
        x += w + track
    m = m.crop(m.getbbox() or (0, 0, 1, 1))
    return m.resize((max(1, min(NAME_MAX_W, round(m.width * squeeze))), m.height), Image.LANCZOS)


def nostalgia(person):
    """Filtro "foto d'epoca" su tutta la pagina: colori caldi e un po' spenti, neri sollevati,
    alone sulle luci e grana. Più scuro ai bordi."""
    a = np.asarray(person, np.float32) / 255
    rgb, alpha = a[..., :3], a[..., 3:]
    lum = rgb @ np.array([0.299, 0.587, 0.114], np.float32)
    rgb = rgb * 0.72 + lum[..., None] * 0.28                       # meno saturo
    rgb = rgb * np.array([1.07, 1.0, 0.86], np.float32)             # caldo
    s = np.clip(rgb, 0, 1)
    rgb = s * 0.7 + (s * s * (3 - 2 * s)) * 0.3                     # un filo di contrasto
    rgb = 0.055 + rgb * 0.9                                         # neri slavati
    rgb = rgb + (np.array([0.03, 0.015, -0.01], np.float32) * (1 - lum[..., None]))  # ombre seppia
    glow = Image.fromarray(np.uint8(np.clip((lum - 0.7) * 3, 0, 1) * 255)).filter(
        ImageFilter.GaussianBlur(max(2, person.width / 220)))
    rgb = rgb + (np.asarray(glow, np.float32) / 255)[..., None] * np.array([0.10, 0.07, 0.03], np.float32)
    rng = np.random.default_rng(7)
    grain = rng.normal(0, 0.035, rgb.shape[:2]).astype(np.float32)
    grain = cv2.GaussianBlur(grain, (0, 0), 0.7) * 1.6
    rgb = rgb + grain[..., None]
    h, w = rgb.shape[:2]
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    r = np.hypot((xx - w / 2) / (w / 2), (yy - h / 2) / (h / 2))
    rgb = rgb * (1 - 0.22 * np.clip(r - 0.55, 0, 1) ** 1.5)[..., None]   # vignetta
    out = np.dstack([np.clip(rgb, 0, 1), alpha])
    return Image.fromarray(np.uint8(out * 255 + 0.5), 'RGBA')


def person_box(size, frame=None, story=False):
    """(x, y, larghezza, altezza) della persona ritagliata nella pagina."""
    frame = clean_frame(frame)
    w, h = size
    big = STORY_PERSON if story else 1
    scale = min(PERSON_H * big / h, PERSON_MAX_W * big / w) * frame['zoom']
    pw, ph = max(1, round(w * scale)), max(1, round(h * scale))
    cx = W / 2 + frame['x'] * W
    bottom = (STORY_H if story else H) + frame['y'] * H
    return round(cx - pw / 2), round(bottom - ph), pw, ph


def enhance(person):
    """Stesso ritocco delle foto del Goal e delle fasi (phase_layers.look: nitidezza e chiarezza),
    sulla persona già alla misura finale. Sotto la trasparenza si allungano i colori del bordo,
    così la chiarezza non fa aloni scuri attorno allo scontorno; trasparenza intatta."""
    from livescore.graphics import phase_layers

    person = person.convert('RGBA')
    alpha = person.getchannel('A')
    rgb = np.asarray(person.convert('RGB').filter(ImageFilter.GaussianBlur(12)), np.float32)
    weight = np.asarray(alpha.filter(ImageFilter.GaussianBlur(12)), np.float32)[..., None] / 255
    base = Image.fromarray(np.clip(rgb / np.maximum(weight, 1e-3), 0, 255).astype(np.uint8), 'RGB')
    base.paste(person.convert('RGB'), (0, 0), alpha)
    out = phase_layers.look(base.convert('RGBA'), clarity=True)
    out.putalpha(alpha)
    return out


def trim(person):
    """Persona ritagliata stretta sulla sua trasparenza."""
    person = person.convert('RGBA')
    box = person.getchannel('A').point(lambda v: 255 if v > 12 else 0).getbbox()
    return person.crop(box) if box else person


@lru_cache(maxsize=1)
def _story_background():
    """Sfondo 9:16: quello di Meta AI sceso di STORY_SHIFT (sopra continua specchiato e sfocato).
    Senza il file: lo sfondo 3:4 al centro, sopra e sotto specchiato."""
    from PIL import ImageOps
    from graphics.common import story_file
    path = story_file('compleanno_storico')
    page = Image.new('RGB', (W, STORY_H))
    if path:
        with Image.open(path) as im:
            bg = ImageOps.fit(im.convert('RGB'), (W, STORY_H), Image.LANCZOS)
        top, src = STORY_SHIFT, bg
    else:
        src, top = _background(), (STORY_H - H) // 2
    page.paste(src, (0, top))
    fill = ImageOps.flip(src.crop((0, 0, W, top))).filter(ImageFilter.GaussianBlur(8))
    page.paste(fill, (0, 0))
    below = top + src.height
    if below < STORY_H:
        page.paste(ImageOps.flip(src.crop((0, src.height - (STORY_H - below), W, src.height))), (0, below))
    return page


def _gold(mask):
    """Maschera L -> RGBA nell'oro del nome, sfumato dall'alto verso il basso."""
    grad = np.linspace(0, 1, mask.height, dtype=np.float32)[:, None, None]
    col = np.array(GOLD_TOP, np.float32) * (1 - grad) + np.array(GOLD_BOTTOM, np.float32) * grad
    rgba = np.dstack([np.broadcast_to(col, (mask.height, mask.width, 3)), np.asarray(mask, np.float32)])
    return Image.fromarray(np.uint8(rgba), 'RGBA')


@lru_cache(maxsize=1)
def _logo():
    """Logo JR in alto a destra (sagoma del logo bianco) colorato nello stesso oro del nome."""
    from graphics.photo_jr import _meta
    with Image.open(asset_dir() / 'canva' / _meta()['white']['overlay']) as im:
        alpha = im.convert('RGBA').resize((W, H), Image.LANCZOS).getchannel('A')
    box = alpha.getbbox() or (0, 0, 1, 1)
    return _gold(alpha.crop(box)), box[:2]


def render(*, name, person=None, frame=None, ghost=False, vintage=True, story=False):
    """PNG della grafica. person = PNG scontornato (byte o Image). ghost=True: pagina senza persona (editor).
    vintage=False: senza il filtro d'epoca (colori della foto). story=True: storia IG 1500x2667."""
    name = clean_name(name)
    if not name:
        raise ValueError('Scrivi il nome.')
    page = (_story_background() if story else _background()).convert('RGBA')
    page_h = page.height

    # nome in oro spaziato (stessa distanza dal titolo) e logo JR nello stesso oro
    m = _name_mask(name)
    name_y = NAME_Y + (STORY_TITLE_TOP - TITLE_TOP if story else 0)
    page.alpha_composite(_gold(m), (round(W / 2 - m.width / 2), round(name_y - m.height / 2)))
    if not story:
        logo, at = _logo()
        page.alpha_composite(logo, at)

    if not ghost:
        if person is None:
            raise ValueError('Carica la foto.')
        if isinstance(person, (bytes, bytearray)):
            person = Image.open(io.BytesIO(person))
        p = trim(person)
        x, y, pw, ph = person_box(p.size, frame, story)
        p = enhance(p.resize((pw, ph), Image.LANCZOS))     # nitida come le foto del Goal
        from graphics.common import rotate_person
        p, x, y = rotate_person(p, x, y, frame)
        layer = Image.new('RGBA', (W, page_h), (0, 0, 0, 0))
        layer.paste(p, (x, y), p)
        if story:           # la persona sfuma prima del logo JR in basso: il logo resta sullo sfondo
            from graphics.common import STORY_JR_TOP
            end = round(STORY_JR_TOP * page_h / 1920) - 20
            fade = np.clip((end - np.arange(page_h, dtype=np.float32)) / 260, 0, 1)
            alpha = np.asarray(layer.getchannel('A'), np.float32) * fade[:, None]
            layer.putalpha(Image.fromarray(np.uint8(alpha + .5)))
        # ombra morbida dietro la persona, per staccarla dal titolo
        sh = layer.getchannel('A').filter(ImageFilter.GaussianBlur(28)).point(lambda v: int(v * 0.55))
        shadow = Image.new('RGBA', (W, page_h), (0, 0, 0, 0))
        shadow.putalpha(sh)
        page = Image.alpha_composite(Image.alpha_composite(page, shadow), layer)

    if story:               # logo JR in oro, in basso al centro come il timbro delle Storie IG
        from graphics.common import STORY_JR_H, STORY_JR_TOP, story_jr_alpha
        a = story_jr_alpha()
        lh = round(STORY_JR_H * page_h / 1920)
        a = a.resize((round(a.width * lh / a.height), lh), Image.LANCZOS)
        page.alpha_composite(_gold(a), ((W - a.width) // 2, round(STORY_JR_TOP * page_h / 1920)))

    # filtro d'epoca su tutta l'immagine (sfondo, nome, logo e persona insieme)
    if vintage:
        page = nostalgia(page)
    out = io.BytesIO()
    page.convert('RGB').save(out, 'PNG')
    return out.getvalue()
