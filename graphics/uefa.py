"""Temi UEFA (UCL / UEL / Conference) per Matchday, Starting XI e Probabile XI.

Stesso design delle maglie, con i colori della competizione: i livelli Canva di una
maglia di partenza vengono ricolorati pixel per pixel (anche sfumature e grana).

- UCL: parte dalla Third (fondi scuri + scritte oro) -> fondi blu notte, scritte e
  loghi in celeste sfumato;
- UEL / Conference: parte dalla Home (fondi chiari + scritte nere, dettagli oro) ->
  sfumature arancioni / verdi come lo sfondo, scritte e loghi tutti neri.

Ogni colore si scompone in "neutro" (grigi: fondi, sfumature, scritte nere) e
"dettaglio" (l'oro, saturo): il neutro va da `dark` a `light` secondo la luminosità,
il dettaglio segue la scala `accent`. I file ricolorati stanno in una cartella
temporanea e si rifanno solo se cambiano i colori qui sotto.

Sfondi di pagina (tutte le maglie e competizioni): canva/bg_<tema>.jpg, messi dietro
la foto scontornata. Per le competizioni, sotto JR, stemmi e scritte le linee sfumano
nel colore di fondo (themed_background); un file canva/bg_<tema>_<grafica>.jpg, se
c'è, si usa così com'è.
"""
import copy
import hashlib
import json
import tempfile
from functools import lru_cache
from pathlib import Path

import numpy as np
from PIL import Image

from graphics.common import asset_dir

KITS = ('home', 'away', 'third')
THEMES = ('ucl', 'uel', 'conference')
ALL = KITS + THEMES
LABELS = {'ucl': 'Champions League', 'uel': 'Europa League', 'conference': 'Conference League'}

PALETTES = {
    'ucl': {
        'base': 'third',
        'dark': (2, 8, 70),          # blu notte (fondo dello sfondo UCL, più scuro)
        'light': (190, 225, 255),
        'accent': ((40, 215, 200), (110, 200, 255)),                    # turchese -> celeste
        'flat_fx': True,             # sfumatura scura in tinta unita (la grana diventava puntini)
    },
    'uel': {
        'base': 'home',
        'dark': (0, 0, 0),
        'light': (252, 109, 6),      # arancione dello sfondo UEL
        'accent': ((0, 0, 0), (20, 20, 20), (46, 46, 46)),             # nero (con un filo di texture)
    },
    'conference': {
        'base': 'home',
        'dark': (0, 0, 0),
        'light': (21, 180, 24),      # verde dello sfondo Conference
        'accent': ((0, 0, 0), (20, 20, 20), (46, 46, 46)),
    },
}


def is_theme(kit):
    return kit in THEMES


def base_kit(kit):
    """Maglia da cui prende il design (foto delle teste, misure...)."""
    return PALETTES[kit]['base'] if kit in THEMES else kit


def theme_for(competition):
    """Tema UEFA della competizione (codice ESPN), '' se non è una coppa UEFA a tema."""
    value = str(competition or '').lower()
    if 'conf' in value:
        return 'conference'
    if 'champions' in value:
        return 'ucl'
    if value == 'uefa.europa':
        return 'uel'
    return ''


def background(kit, graphic=None):
    """Sfondo di pagina 3:4 della maglia o della competizione.

    Competizioni con la grafica indicata: sfondo riempito e senza linee sotto JR e
    stemmi dei club (themed_background)."""
    if kit in THEMES and graphic in CLEAR:
        # Sfondo fatto per quella grafica (tools/uefa_backgrounds.py o a mano su Canva), se c'è.
        ready = asset_dir() / 'canva' / f'bg_{kit}_{graphic}.jpg'
        if ready.is_file():
            return ready
        return themed_background(kit, graphic)
    return asset_dir() / 'canva' / f'bg_{kit}.jpg'


# Zone senza linee (pixel design 1080x1440): JR in alto a destra e stemmi dei club.
_JR = (970, 0, 1080, 100)
# Zone dove le linee sfumano nel colore di fondo (pixel design 1080x1440): JR, stemmi
# e scritte (titolo, nomi, riga info).
CLEAR = {
    'matchday': [_JR, (0, 0, 160, 292), (55, 1147, 969, 1380), (0, 1375, 1080, 1440)],
    'starting_xi': [_JR, (38, 54, 597, 394), (20, 415, 700, 1372)],
    'probabili': [_JR, (217, 8, 874, 174), (436, 1318, 644, 1440)],
}
# Sfondi da riempire con la stessa trama ruotata: nessuno (gli sfondi sono già completi).
FILL = set()


@lru_cache(maxsize=16)
def themed_background(theme, graphic):
    """Sfondo competizione per la grafica: sotto JR, stemmi e scritte (CLEAR) le linee
    sfumano nel colore di fondo (arancione/verde per UEL/Conference, blu per l'UCL)."""
    from PIL import ImageFilter
    key = hashlib.sha1(json.dumps([CLEAR[graphic], theme in FILL, 'v4']).encode()).hexdigest()[:8]
    out = _cache_dir(theme) / f'bg_{graphic}_{key}.jpg'
    if out.is_file():
        return out
    with Image.open(asset_dir() / 'canva' / f'bg_{theme}.jpg') as image:
        src = image.convert('RGB').resize((1920, 2560), Image.LANCZOS)
    a = np.asarray(src).astype(np.float32)
    # Fondo senza linee. UEL / Conference (linee nere su colore): il colore vero del fondo
    # sotto le linee si ricostruisce (inpaint a bassa risoluzione) e si toglie solo la linea,
    # pixel per pixel: dove non c'è linea resta lo sfondo originale con la sua grana.
    # UCL (linee chiare su blu): filtro min a bassa risoluzione.
    if theme in ('uel', 'conference'):
        import cv2
        small = cv2.resize(a, (480, 640), interpolation=cv2.INTER_AREA)
        bright = cv2.dilate(small, np.ones((15, 15), np.uint8))          # fondo senza linee (stima)
        lines_small = (small.mean(-1) < bright.mean(-1) * 0.8).astype(np.uint8)
        lines_small = cv2.dilate(lines_small, np.ones((5, 5), np.uint8))
        filled = cv2.inpaint(np.clip(small, 0, 255).astype(np.uint8), lines_small * 255, 9, cv2.INPAINT_TELEA)
        flat = cv2.GaussianBlur(cv2.resize(filled.astype(np.float32), (1920, 2560),
                                           interpolation=cv2.INTER_CUBIC), (0, 0), 6)
        alpha = np.clip((flat.mean(-1) - a.mean(-1)) / np.maximum(flat.mean(-1) * 0.45, 1), 0, 1)
        alpha = cv2.GaussianBlur(cv2.dilate(alpha, np.ones((5, 5), np.uint8)), (0, 0), 1.5)  # anche i bordi
        # Grana dello sfondo (presa dove non ci sono linee) sotto le linee tolte.
        y0, x0, s = 900, 760, 400
        patch = a[y0:y0 + s, x0:x0 + s] - cv2.GaussianBlur(a[y0:y0 + s, x0:x0 + s], (0, 0), 20)
        grain = np.tile(patch, (2560 // s + 1, 1920 // s + 1, 1))[:2560, :1920]
        flat = a * (1 - alpha[..., None]) + (flat + grain) * alpha[..., None]
    else:
        small = src.resize((240, 320), Image.BILINEAR).filter(ImageFilter.MinFilter(9))
        flat_img = small.filter(ImageFilter.GaussianBlur(12)).resize((1920, 2560), Image.BICUBIC)
        flat = np.asarray(flat_img).astype(np.float32)
    # Zone pulite, con bordo morbido.
    k = 1920 / 1080
    zone = Image.new('L', (1920, 2560), 0)
    from PIL import ImageDraw
    draw = ImageDraw.Draw(zone)
    for x0, y0, x1, y1 in CLEAR[graphic]:
        draw.rounded_rectangle((x0 * k - 60, y0 * k - 60, x1 * k + 60, y1 * k + 60), radius=60, fill=255)
    m = np.asarray(zone.filter(ImageFilter.GaussianBlur(90))).astype(np.float32)[..., None] / 255
    a = a * (1 - m) + flat * m
    Image.fromarray(np.clip(a, 0, 255).astype('uint8'), 'RGB').save(out, format='JPEG', quality=92)
    return out


# ---------- ricolorazione ----------

def _stops(value, stops):
    """Scala di colori (2 o 3 tappe) su value 0..1."""
    stops = np.array(stops, dtype=float)
    pos = np.linspace(0, 1, len(stops))
    return np.stack([np.interp(value, pos, stops[:, c]) for c in range(3)], axis=-1)


def recolor_array(rgb, theme, accent_range=None):
    """rgb: array (..., 3) 0..255 -> stesso array con i colori del tema.
    accent_range = (lum min, lum max) dell'oro nel file: la sfumatura usa tutta la scala."""
    p = PALETTES[theme]
    rgb = rgb.astype(float)
    hi, lo = rgb.max(-1), rgb.min(-1)
    sat = np.where(hi > 0, (hi - lo) / np.maximum(hi, 1), 0)
    lum = (0.2126 * rgb[..., 0] + 0.7152 * rgb[..., 1] + 0.0722 * rgb[..., 2]) / 255
    neutral = _stops(lum, (p['dark'], p['light']))
    # Oro: luminosità ristretta a 0..1 sulla sua gamma (l'oro va da ~0,35 a ~0,85).
    lo_a, hi_a = accent_range or (0.3, 0.85)
    accent = _stops(np.clip((lum - lo_a) / max(hi_a - lo_a, 0.05), 0, 1), p['accent'])
    # Oro = saturo E abbastanza luminoso: i quasi-neri con rumore di colore restano neutri.
    weight = (np.clip((sat - 0.18) / 0.2, 0, 1) * np.clip((hi - 30) / 30, 0, 1))[..., None]
    return neutral * (1 - weight) + accent * weight


def recolor_hex(color, theme):
    color = color.lstrip('#')
    rgb = np.array([[int(color[i:i + 2], 16) for i in (0, 2, 4)]])
    r, g, b = (int(round(v)) for v in recolor_array(rgb, theme)[0])
    return f'#{r:02x}{g:02x}{b:02x}'


def _cache_dir(theme):
    key = hashlib.sha1(json.dumps(PALETTES[theme], sort_keys=True).encode()).hexdigest()[:10]
    path = Path(tempfile.gettempdir()) / 'imagegen_uefa' / f'{theme}_{key}'
    path.mkdir(parents=True, exist_ok=True)
    return path


def _accent_range(a):
    """Gamma di luminosità dell'oro (pixel saturi e visibili) del livello, se ce n'è."""
    rgb = a[..., :3].astype(float)
    hi, lo = rgb.max(-1), rgb.min(-1)
    sat = (hi - lo) / np.maximum(hi, 1)
    gold = (sat > 0.3) & (hi > 60) & (a[..., 3] > 128)
    if gold.sum() < 50:
        return None
    lum = (0.2126 * rgb[..., 0] + 0.7152 * rgb[..., 1] + 0.0722 * rgb[..., 2])[gold] / 255
    return float(np.percentile(lum, 3)), float(np.percentile(lum, 97))


@lru_cache(maxsize=256)
def recolor_file(name, theme, flat=False):
    """canva/<name> ricolorato: percorso del PNG pronto (in cache).
    flat=True: tutto nel colore scuro del tema (resta solo la trasparenza)."""
    out = _cache_dir(theme) / (Path(name).stem + ('_flat' if flat else '') + '.png')
    if not out.is_file():
        with Image.open(asset_dir() / 'canva' / name) as image:
            image = image.convert('RGBA')
            a = np.asarray(image)
            if flat:
                rgb = np.broadcast_to(np.array(PALETTES[theme]['dark'], float), a[..., :3].shape)
            else:
                rgb = recolor_array(a[..., :3], theme, _accent_range(a))
            done = np.dstack([np.clip(rgb, 0, 255), a[..., 3]]).astype('uint8')
        tmp = out.with_suffix('.tmp')
        Image.fromarray(done, 'RGBA').save(tmp, format='PNG')
        tmp.replace(out)
    return out


@lru_cache(maxsize=8)
def overlay_file(graphic, theme):
    """Livello fisso completo (sfumature + titolo/JR) ricolorato, per l'editor foto."""
    out = _cache_dir(theme) / f'{graphic}_overlay.png'
    if not out.is_file():
        meta = theme_meta(graphic, theme)
        with Image.open(meta['fx']) as fx, Image.open(meta['text_overlay']) as text:
            layer = fx.convert('RGBA')
            layer.alpha_composite(text.convert('RGBA').resize(layer.size))
        layer.save(out, format='PNG')
    return out


def _walk(value, theme, key=''):
    if isinstance(value, dict):
        return {k: _walk(v, theme, k) for k, v in value.items()}
    if isinstance(value, list):
        return [_walk(v, theme, key) for v in value]
    if isinstance(value, str):
        if value.endswith('.png') and key != 'bg':
            flat = key == 'fx' and PALETTES[theme].get('flat_fx', False)
            return str(recolor_file(value, theme, flat))
        if value.startswith('#') and len(value) == 7:
            return recolor_hex(value, theme)
    return value


# Texture dei loghi della Third (come common.LOGO_TEXTURES): ricolorata per l'UCL.
_LOGO_TEXTURE = {'third': 'starting_xi_third_number_01.png'}


@lru_cache(maxsize=16)
def _theme_meta(graphic, theme):
    meta = json.loads((asset_dir() / 'canva' / f'{graphic}.json').read_text(encoding='utf-8'))
    base = PALETTES[theme]['base']
    out = _walk(copy.deepcopy(meta[base]), theme)
    out['fx_light'] = False                     # sfumatura già nel colore del tema
    if 'logo_texture' not in out and base in _LOGO_TEXTURE:
        out['logo_texture'] = str(recolor_file(_LOGO_TEXTURE[base], theme))
    if graphic in ('matchday', 'starting_xi'):
        out['overlay'] = None                   # si fa su richiesta (overlay_file)
    return out


def theme_meta(graphic, theme):
    """Metadati Canva della grafica per il tema: come quelli della maglia di partenza,
    con i file sostituiti dai percorsi assoluti dei file ricolorati."""
    return copy.deepcopy(_theme_meta(graphic, theme))


def meta_for(graphic, kit, meta_all):
    """Metadati per maglia o tema (meta_all = json della grafica già letto)."""
    if kit in THEMES:
        return theme_meta(graphic, kit)
    return meta_all[kit]


# ---------- Probabile XI: campo sopra lo sfondo della competizione ----------

@lru_cache(maxsize=1)
def _pitch_mask():
    """Maschera 0..1 (1920x2560) di campo, titolo e JR, presa dallo sfondo Home.

    Campo: riga per riga si parte dalla linea nera più esterna e si va verso fuori
    finché il grigio del campo diventa il bianco del fondo; sotto, fino al bordo in
    rilievo del campo. Titolo e JR: i pixel scuri o oro nella fascia in alto."""
    from PIL import ImageFilter
    with Image.open(asset_dir() / 'canva' / 'probabili_home_bg.png') as image:
        rgb = np.asarray(image.convert('RGB').resize((1920, 2560), Image.LANCZOS)).astype(float)
    gray = rgb.mean(-1)
    hi, lo = rgb.max(-1), rgb.min(-1)
    sat = (hi - lo) / np.maximum(hi, 1)
    top, cream = 330, 237

    def edge(row, x, step):
        while 0 < x < 1919 and row[x] <= cream:
            x += step
        return x

    left = np.full(2560, np.nan)
    right = np.full(2560, np.nan)
    for y in range(top, 2560):
        dark = np.flatnonzero(gray[y] < 110)
        if len(dark) and dark.max() - dark.min() > 600:
            left[y], right[y] = edge(gray[y], dark.min(), -1), edge(gray[y], dark.max(), 1)
    rows = np.flatnonzero(~np.isnan(left))
    mask = np.zeros((2560, 1920), dtype=bool)
    if len(rows):
        y0 = rows.min()
        y1 = rows.max()
        while y1 < 2559 and gray[y1 + 1, 960] <= cream - 10:     # bordo in rilievo sotto il campo
            y1 += 1
        ys = np.arange(y0, y1 + 1)
        lft = np.interp(ys, rows, left[rows])
        rgt = np.interp(ys, rows, right[rows])

        def smooth(v, n=31):
            pad = np.pad(v, n // 2, mode='edge')
            return np.median(np.lib.stride_tricks.sliding_window_view(pad, n), axis=-1)

        # Il campo è simmetrico (centro 960): a destra il fondo crema è più caldo e
        # confonde il bordo, quindi vale il bordo sinistro specchiato.
        lft = smooth(lft)
        rgt = 1919 - lft
        xs = np.arange(1920)
        mask[y0:y1 + 1] = (xs[None, :] >= lft[:, None]) & (xs[None, :] <= rgt[:, None])
    mask[:top] = (gray[:top] < 150) | (sat[:top] > 0.3)
    img = Image.fromarray((mask * 255).astype('uint8'))
    return img.filter(ImageFilter.MaxFilter(3)).filter(ImageFilter.GaussianBlur(1.2))


@lru_cache(maxsize=4)
def probabili_bg(theme):
    """Sfondo Probabile XI per il tema: sfondo competizione + campo/titolo ricolorati."""
    out = _cache_dir(theme) / 'probabili_bg.png'
    if not out.is_file():
        base = PALETTES[theme]['base']
        with Image.open(asset_dir() / 'canva' / f'probabili_{base}_bg.png') as image:
            src = np.asarray(image.convert('RGB').resize((1920, 2560), Image.LANCZOS))
        # Le parti scure (bordo in rilievo del campo) hanno grana: ricolorata diventerebbe
        # puntini chiari, quindi lì si liscia prima (filtro mediano).
        import cv2
        smooth = cv2.medianBlur(src, 7)
        dark = (src.mean(-1) < 60)[..., None]
        src = np.where(dark, smooth, src)
        pitch = Image.fromarray(np.clip(recolor_array(src, theme), 0, 255).astype('uint8'), 'RGB')
        with Image.open(background(theme, 'probabili')) as bg:
            page = bg.convert('RGB').resize((1920, 2560), Image.LANCZOS)
        page.paste(pitch, (0, 0), _pitch_mask())
        page.save(out, format='PNG')
    return out


def placeholder_file(graphic, theme):
    """Sagoma pronta per l'editor (tools/placeholders.py), se c'è: canva/<grafica>_<tema>_placeholder.png."""
    path = asset_dir() / 'canva' / f'{graphic}_{theme}_placeholder.png'
    return path if path.is_file() else None
