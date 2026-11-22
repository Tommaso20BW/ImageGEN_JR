"""Strumenti comuni: asset, loghi, font e render HTML -> PNG.

Le misure nei modelli sono in pixel del design Canva (1080x1440):
il render le porta a 1920x2560 come le altre grafiche HD.
"""
import base64
import html
import json
import math
import mimetypes
import os
import unicodedata
from functools import lru_cache
from pathlib import Path

DESIGN_W, DESIGN_H = 1080, 1440
OUT_W, OUT_H = 1920, 2560
# STORIA IG (9:16): pagina larga 1080 come il 3:4 (uscita 1920x3413). Ogni grafica è reimpaginata
# per la storia: titolo sotto la barra di Instagram in alto (STORY_SAFE_TOP), contenuto allargato
# fino sopra la barra della risposta in basso (STORY_SAFE_BOTTOM). Sfondi 9:16 in canva/story/
# (fatti con Meta AI dagli sfondi 3:4); se manca, lo sfondo 3:4 allungato (story_bg).
STORY_H = 1920
STORY_TOP = (STORY_H - DESIGN_H) / 2
STORY_OUT_H = round(OUT_W * 16 / 9)
STORY_SAFE_TOP, STORY_SAFE_BOTTOM = 190, 1650
# Logo JR delle storie: dove sta il timbro delle Storie IG (graphics/ig_story.py, LOGO_Y): centrato,
# in basso, cima a 1696 e alto 140 su 1920. Il contenuto finisce sopra (STORY_SAFE_BOTTOM).
STORY_JR_TOP, STORY_JR_H = 1696, 140
STORY_JR_CUT = 0.86                # nei titoli 3:4 il JR in alto a destra sta oltre questa frazione di larghezza


def asset_dir():
    """Cartella asset privati: IMAGEGEN_ASSETS in locale, motore grafico su GitHub."""
    override = os.environ.get('IMAGEGEN_ASSETS')
    if override:
        return Path(override)
    from livescore.graphics import goal
    return Path(goal.DEFAULT_ASSET_DIR)


def data_uri(path):
    path = Path(path)
    mime = mimetypes.guess_type(path.name)[0] or 'application/octet-stream'
    if path.suffix.lower() == '.otf':
        mime = 'font/otf'
    elif path.suffix.lower() == '.ttf':
        mime = 'font/ttf'
    return f'data:{mime};base64,' + base64.b64encode(path.read_bytes()).decode('ascii')


def font_face(family, filename):
    return (
        f"@font-face{{font-family:'{family}';"
        f"src:url({data_uri(asset_dir() / 'fonts' / filename)});}}"
    )


def esc(value):
    return html.escape(str(value), quote=True)


def normalize(value):
    raw = unicodedata.normalize('NFKD', str(value or '').casefold())
    return ' '.join(''.join(c for c in raw if not unicodedata.combining(c)).split())


@lru_cache(maxsize=2)
def _manifest_rows(assets_text):
    assets = Path(assets_text)
    path = assets / 'team_logos' / 'manifest.json'
    if not path.is_file():
        path = assets / 'team_logos' / 'fclogo_cache' / 'manifest.json'
    return json.loads(path.read_text(encoding='utf-8')).get('teams', [])


def _logo_rows(assets_text):
    """Catalogo FCLogo con le correzioni di Impostazioni › Squadre e loghi
    (alias ESPN in più, nome mostrato, logo caricato a mano, squadre nuove)."""
    rows = _manifest_rows(assets_text)
    try:
        from livescore.core import team_overrides
    except ImportError:          # motore grafico senza correzioni: catalogo com'è
        return rows
    return team_overrides.apply(rows, assets_text)


def team_logo(name, team_id=''):
    """Percorso del logo mono della squadra (stesso file usato su Canva)."""
    assets = asset_dir()
    rows = _logo_rows(str(assets))
    key = normalize(name)
    for row in rows:
        names = [row.get('name'), row.get('display_name'), *(row.get('aliases') or [])]
        if (team_id and str(row.get('espn_id') or '') == str(team_id)) or key in map(normalize, names):
            if row.get('custom_logo') and Path(row['custom_logo']).is_file():
                return Path(row['custom_logo'])
            for file in [row.get('file'), *(row.get('files') or [])]:
                for base in ('team_logos', 'team_logos/fclogo_cache'):
                    path = assets / base / (file or '')
                    if file and path.is_file():
                        return path
    raise FileNotFoundError(f'Logo non trovato per {name!r}')


def _crop_png(png, width, height):
    """PNG tagliato a width x height (in alto a sinistra); invariato se ha già quella misura."""
    import io

    from PIL import Image

    with Image.open(io.BytesIO(png)) as image:
        if image.size == (width, height):
            return png
        out = io.BytesIO()
        image.crop((0, 0, width, height)).save(out, format='PNG')
        return out.getvalue()


class _Renderer:
    """Un solo Chrome sempre acceso, in un thread dedicato (Playwright non si può
    usare da thread diversi): ogni grafica apre solo una pagina nuova.
    Avviare il browser costa ~2-3 s; con il browser già acceso un render ~0,5 s."""

    def __init__(self):
        import queue
        import threading
        self.jobs = queue.Queue()
        self.thread = threading.Thread(target=self._run, name='imagegen-render', daemon=True)
        self.thread.start()

    def _run(self):
        from playwright.sync_api import sync_playwright
        playwright = browser = None
        while True:
            markup, ghost, page, out_w, done = self.jobs.get()
            try:
                if browser is None or not browser.is_connected():
                    if playwright is None:
                        playwright = sync_playwright().start()
                    chrome = os.environ.get('IMAGEGEN_CHROME') or None
                    browser = playwright.chromium.launch(executable_path=chrome)
                page_w, page_h = page
                tab = browser.new_page(
                    viewport={'width': page_w, 'height': math.ceil(page_h) + 1},
                    device_scale_factor=0.5 if ghost else out_w / page_w,
                )
                try:
                    tab.set_content(markup, wait_until='load')
                    # Le grafiche che calcolano il layout con uno script (STORIE IG) mettono in
                    # window.__ready la promessa da aspettare; per le altre è undefined.
                    tab.evaluate('() => document.fonts.ready.then(() => window.__ready)')
                    # Pagine non 3:4 (es. 16:9 = 1080x607,5): si scatta una riga in più e si taglia
                    # alla misura esatta (1920x1080), perché Chrome arrotonda l'altezza per difetto.
                    png = tab.screenshot(type='png', omit_background=ghost,
                                         clip={'x': 0, 'y': 0, 'width': page_w, 'height': math.ceil(page_h) + 1})
                    scale = 0.5 if ghost else out_w / page_w
                    done['png'] = _crop_png(png, round(page_w * scale), round(page_h * scale))
                finally:
                    tab.close()
            except Exception as exc:          # il prossimo render riparte con un browser nuovo
                done['error'] = exc
                try:
                    if browser is not None:
                        browser.close()
                except Exception:
                    pass
                browser = None
            finally:
                done['event'].set()

    def render(self, markup, ghost, page, out_w=OUT_W):
        import threading
        done = {'event': threading.Event()}
        self.jobs.put((markup, ghost, page, out_w, done))
        if not done['event'].wait(120):
            raise TimeoutError('Render della grafica troppo lento.')
        if 'error' in done:
            raise done['error']
        return done['png']


_RENDERER = None


def render_html(markup, ghost=False, page=None, out_w=OUT_W):
    """Render della pagina 1080x1440 in PNG 1920x2560.

    page = (larghezza, altezza) in pixel design per formati diversi dal 3:4: la
    larghezza resta 1080 (uscita 1920 px), l'altezza segue il formato.

    out_w = larghezza dell'uscita in pixel (default 1920); l'altezza segue la pagina.

    ghost=True: versione leggera (540x720) con sfondo trasparente, per l'editor foto.
    """
    global _RENDERER
    if _RENDERER is None:
        _RENDERER = _Renderer()
    return _RENDERER.render(markup, ghost, page or (DESIGN_W, DESIGN_H), out_w)


def warm_up():
    """Accende il browser in anticipo (all'avvio del servizio)."""
    render_html('<!doctype html><html><body></body></html>', ghost=True)


def page_background(kit, photo, graphic=None, story=False):
    """Sfondo della maglia/competizione dietro la foto (scontornata: si vede dove è
    trasparente). Senza foto (versione "fantasma" per l'editor) niente sfondo.
    story=True: allungato a tutta la pagina 9:16."""
    if photo is None:
        return ''
    from graphics.uefa import background
    path = background(kit, graphic)
    if not path.is_file():
        return ''
    smooth = graphic in SMOOTH_BG and kit in SMOOTH_BG_KITS
    if story:
        uri = story_background(f'bg_{kit}', str(path), BG_SMOOTH if smooth else 0.0)
    else:
        uri = _smooth_bg(str(path)) if smooth else data_uri(path)
    return (f'<img src="{uri}" style="position:absolute;left:0;top:0;'
            f'width:{DESIGN_W}px;height:{STORY_H if story else DESIGN_H}px;object-fit:cover">')


def story_file(name):
    """Sfondo 9:16 pronto (canva/story/<nome>.jpg, fatto con Meta AI), se c'è."""
    path = asset_dir() / 'canva' / 'story' / f'{name}.jpg'
    return path if path.is_file() else None


def story_background(name, fallback, smooth=0.0):
    """Data uri dello sfondo storia: canva/story/<name>.jpg se c'è, altrimenti `fallback` 3:4 allungato."""
    ready = story_file(name)
    return story_cover(str(ready), smooth) if ready else story_bg(str(fallback), smooth)


@lru_cache(maxsize=12)
def story_cover(path, smooth=0.0):
    """Sfondo 9:16 portato a 1920x3413 (riempie, centrato) come data uri JPEG."""
    import io

    import cv2
    import numpy as np
    from PIL import Image, ImageOps

    image = ImageOps.fit(Image.open(path).convert('RGB'), (OUT_W, STORY_OUT_H), Image.LANCZOS)
    if smooth:
        a = cv2.GaussianBlur(np.asarray(image).astype(np.float32), (0, 0), smooth)
        image = Image.fromarray(np.clip(a + .5, 0, 255).astype('uint8'))
    buf = io.BytesIO()
    image.save(buf, 'JPEG', quality=95, subsampling=0)
    return 'data:image/jpeg;base64,' + base64.b64encode(buf.getvalue()).decode('ascii')


@lru_cache(maxsize=12)
def story_bg(path, smooth=0.0):
    """Sfondo 3:4 portato a 9:16 (data uri JPEG 1920x3413): l'originale al centro; sopra e sotto
    continua con la riga di bordo (sfocata di lato, così non fa righe) e la stessa grana, sfumando
    nell'originale. smooth = sfocatura dell'originale (come _smooth_bg)."""
    import io

    import cv2
    import numpy as np
    from PIL import Image

    a = np.asarray(Image.open(path).convert('RGB').resize((OUT_W, OUT_H), Image.LANCZOS)).astype(np.float32)
    if smooth:
        a = cv2.GaussianBlur(a, (0, 0), smooth)
    top = (STORY_OUT_H - OUT_H) // 2
    bottom = STORY_OUT_H - OUT_H - top
    out = np.empty((STORY_OUT_H, OUT_W, 3), np.float32)
    out[top:top + OUT_H] = a
    rng = np.random.default_rng(3)
    for rows, band, edge in ((slice(0, top), top, a[:60]), (slice(top + OUT_H, None), bottom, a[-60:])):
        # mediana: un logo o una scritta sul bordo non entra nella fascia
        line = cv2.GaussianBlur(np.median(edge, 0, keepdims=True), (0, 0), sigmaX=40, sigmaY=0.1)
        hp = edge - cv2.GaussianBlur(edge, (0, 0), 3)
        sd = float(1.4826 * np.median(np.abs(hp)))                # quanta grana ha l'originale
        noise = cv2.GaussianBlur(rng.normal(0, 1, (band, OUT_W)).astype(np.float32), (0, 0), 0.8)
        noise *= sd / (noise.std() + 1e-6)
        out[rows] = line + noise[..., None]
    # cucitura: 40 px di passaggio morbido tra banda e originale
    for k in range(40):
        w = k / 40
        out[top - 1 - k] = out[top - 1 - k] * w + out[top] * (1 - w)
        out[top + OUT_H + k] = out[top + OUT_H + k] * w + out[top + OUT_H - 1] * (1 - w)
    buf = io.BytesIO()
    Image.fromarray(np.clip(out + .5, 0, 255).astype('uint8')).save(buf, 'JPEG', quality=95, subsampling=0)
    return 'data:image/jpeg;base64,' + base64.b64encode(buf.getvalue()).decode('ascii')


def story_page(content, background=''):
    """Corpo della pagina storia: `background` a tutta pagina (1080x1920) e la grafica 3:4
    (`content`, posizioni come nella pagina 1080x1440) dentro un riquadro centrato a STORY_TOP."""
    return (f'{background}<div style="position:absolute;left:0;top:{STORY_TOP}px;width:{DESIGN_W}px;'
            f'height:{DESIGN_H}px">{content}</div>')


# Matchday e Starting XI senza grana: sfondi delle maglie lisci (la texture fine di carta
# e gesso sparisce, le nuvole di colore restano). Gli sfondi delle competizioni hanno
# linee e disegni: restano come sono.
SMOOTH_BG = ('matchday', 'starting_xi')
SMOOTH_BG_KITS = ('home', 'away', 'third')
BG_SMOOTH = 5.0


@lru_cache(maxsize=6)
def _smooth_bg(path):
    import io

    import cv2
    import numpy as np
    from PIL import Image

    a = np.asarray(Image.open(path).convert('RGB')).astype(np.float32)
    a = cv2.GaussianBlur(a, (0, 0), BG_SMOOTH)
    out = io.BytesIO()
    Image.fromarray(np.clip(a + .5, 0, 255).astype('uint8')).save(out, 'JPEG', quality=95, subsampling=0)
    return 'data:image/jpeg;base64,' + base64.b64encode(out.getvalue()).decode('ascii')


def _transparent(raw):
    """True se la foto è un PNG con trasparenza vera (persona scontornata)."""
    if raw[:4] != bytes((0x89,)) + b'PNG':
        return False
    import io
    from PIL import Image
    with Image.open(io.BytesIO(raw)) as im:
        return im.mode in ('RGBA', 'LA', 'PA') and im.getchannel('A').getextrema()[0] < 250


def photo_layer(photo, frame, page=None, free=False):
    """(<img> della foto, colore di fondo pagina). Senza foto: niente <img> e fondo
    trasparente, per la versione "fantasma" mostrata sopra la foto nell'editor.
    free=True: se la foto è scontornata (PNG trasparente) si sposta libera (photo_box)."""
    if photo is None:
        return '', 'transparent'
    from graphics.starting_xi import check_photo, photo_box
    left, top, width, height = photo_box(check_photo(photo), frame, page, free and _transparent(photo))
    mime = 'image/png' if photo.startswith(b'\x89PNG') else 'image/jpeg'
    uri = f'data:{mime};base64,' + base64.b64encode(photo).decode('ascii')
    return (f'<img src="{uri}" style="position:absolute;left:{left}px;top:{top}px;'
            f'width:{width}px;height:{height}px">'), '#fff'


# Maglie con le scritte sfumate: il logo prende la stessa texture delle scritte
# (lastra già in canva/, usata dai numeri della Starting XI).
LOGO_TEXTURES = {'third': 'starting_xi_third_number_01.png'}


def logo_fill(meta, kit, texture=None):
    """Riempimento CSS dei loghi sotto la maschera: la sfumatura delle scritte
    (texture indicata, `meta['logo_texture']` o quella della maglia) oppure, per le
    maglie a tinta unita, `logo_color`."""
    file = texture or meta.get('logo_texture') or LOGO_TEXTURES.get(kit)
    if file:
        return f'url({data_uri(asset_dir() / "canva" / file)}) center/100% 100% no-repeat'
    return meta['logo_color']


BASE_CSS = (
    '*{margin:0;padding:0;box-sizing:border-box}'
    f'html,body{{width:{DESIGN_W}px;height:{DESIGN_H}px;overflow:hidden;background:#000}}'
    '.abs{position:absolute}'
    '.white{filter:brightness(0) invert(1)}'
)


def overlay_preview(name, kit, width=540, full=False):
    """Sagoma per l'editor foto (full=True: livello originale a piena risoluzione): canva/<nome>_<maglia>_placeholder.png (fatta da
    tools/placeholders.py, già 540x720); se manca, il livello fisso Canva ridotto."""
    import io

    from PIL import Image

    if not name.replace('_', '').isalnum() or not kit.isalnum():
        raise ValueError('Modello non valido.')
    from graphics import uefa
    # Sagoma pronta (Matchday, Starting XI e fasi, per ogni maglia e competizione): subito.
    ready = asset_dir() / 'canva' / f'{name}_{kit}_placeholder.png'
    if not full and ready.is_file():
        return ready.read_bytes()
    if uefa.is_theme(kit):
        if name not in ('matchday', 'starting_xi'):
            raise ValueError('Modello non valido.')
        ready = uefa.placeholder_file(name, kit)
        if not full and ready is not None:
            return ready.read_bytes()
        with Image.open(uefa.overlay_file(name, kit)) as image:
            if full:
                out = io.BytesIO()
                image.save(out, format='PNG')
                return out.getvalue()
            small = image.resize((width, round(width * DESIGN_H / DESIGN_W)), Image.LANCZOS)
            out = io.BytesIO()
            small.save(out, format='PNG', optimize=True)
            return out.getvalue()
    ready = asset_dir() / 'canva' / f'{name}_{kit}_placeholder.png'
    if not full and ready.is_file():
        return ready.read_bytes()

    meta = json.loads((asset_dir() / 'canva' / f'{name}.json').read_text(encoding='utf-8'))
    if full:      # piena qualità: il livello Canva originale, senza ridurlo
        return (asset_dir() / 'canva' / meta[kit]['overlay']).read_bytes()
    with Image.open(asset_dir() / 'canva' / meta[kit]['overlay']) as image:
        small = image.resize((width, round(width * DESIGN_H / DESIGN_W)), Image.LANCZOS)
        out = io.BytesIO()
        small.save(out, format='PNG', optimize=True)
        return out.getvalue()


# Colore dello sfondo delle foto home (crema): la sfumatura chiara Canva lo prende.
HOME_FX_COLOR = (237, 231, 221)


def canva_layers(meta, photo, frame):
    """Livelli Canva sopra la foto: sfumature + titolo e JR.

    - senza foto (anteprima nell'editor): sfumature, titolo e JR su fondo trasparente;
    - sfumatura chiara (home): ricolorata nel crema dello sfondo delle foto home,
      così non si vede lo stacco col bianco freddo di Canva;
    - la grana di Canva nelle sfumature viene tolta (_fx).
    """
    canva = asset_dir() / 'canva'
    full = f'style="position:absolute;left:0;top:0;width:{DESIGN_W}px;height:{DESIGN_H}px"'
    text = f'<img src="{data_uri(canva / meta["text_overlay"])}" {full}>'
    fx = _fx(str(canva / meta['fx']), bool(meta.get('fx_light')))
    return f'<img src="{fx}" {full}>' + text


def story_canva_layers(meta, top):
    """canva_layers per la storia 9:16: (sfumature a tutta pagina, titolo 3:4 spostato in giù di
    `top` pixel + logo JR in basso come il timbro delle Storie IG). Le sfumature seguono il titolo e continuano sopra e sotto con le righe di bordo."""
    canva = asset_dir() / 'canva'
    fx = _story_fx(str(canva / meta['fx']), bool(meta.get('fx_light')), round(top * OUT_W / DESIGN_W))
    return (f'<img src="{fx}" style="position:absolute;left:0;top:0;width:{DESIGN_W}px;height:{STORY_H}px">',
            f'<img src="{data_uri(canva / meta["text_overlay"])}" style="position:absolute;left:0;top:{top}px;'
            f'width:{DESIGN_W}px;height:{DESIGN_H}px;clip-path:inset(0 {100 - STORY_JR_CUT * 100:.0f}% 0 0)">'
            + story_jr_html(overlay_jr_color(str(canva / meta["text_overlay"]))))


@lru_cache(maxsize=1)
def story_jr_alpha():
    """Forma del logo JR (canale alpha ritagliato), dall'overlay nero della FOTO + JR."""
    from PIL import Image
    from graphics.photo_jr import _meta
    with Image.open(asset_dir() / 'canva' / _meta()['black']['overlay']) as im:
        a = im.convert('RGBA').getchannel('A')
        return a.crop(a.getbbox())


@lru_cache(maxsize=1)
def story_jr_stamp_alpha():
    """Logo JR a timbro come nelle Storie IG normali (ig_story._logo_stamp): bordo morbido,
    inchiostro sbiadito (78%) e consumato a chiazze. Misura del logo su una storia 1080x1920."""
    import numpy as np
    from PIL import Image, ImageFilter
    from graphics import compleanno as cp
    a = story_jr_alpha()
    h = STORY_JR_H
    w = round(a.width * h / a.height)
    m = np.asarray(a.resize((w, h), Image.LANCZOS).filter(ImageFilter.GaussianBlur(.6)), np.float32) / 255
    x, y = (1080 - w) // 2, STORY_JR_TOP
    m *= cp._ink_breakup((1080, STORY_H), 11, .55)[y:y + h, x:x + w] * .78
    return Image.fromarray(np.uint8(np.clip(m, 0, 1) * 255 + .5))


@lru_cache(maxsize=1)
def _story_jr_mask_uri():
    import io
    from PIL import Image
    a = story_jr_stamp_alpha()
    img = Image.new('RGBA', a.size, (255, 255, 255, 255))
    img.putalpha(a)
    buf = io.BytesIO()
    img.save(buf, 'PNG')
    return 'data:image/png;base64,' + base64.b64encode(buf.getvalue()).decode('ascii')


def story_jr_html(color, page_w=DESIGN_W, page_h=STORY_H):
    """Logo JR della storia (HTML) nel colore dato, nella posizione del timbro delle Storie IG."""
    a = story_jr_alpha()
    h = STORY_JR_H * page_h / STORY_H
    w = a.width * h / a.height
    return (f'<div style="position:absolute;left:{(page_w - w) / 2}px;top:{STORY_JR_TOP * page_h / STORY_H}px;'
            f'width:{w}px;height:{h}px;background:{color};z-index:9;'
            f'-webkit-mask:url({_story_jr_mask_uri()}) center/100% 100% no-repeat;'
            f'mask:url({_story_jr_mask_uri()}) center/100% 100% no-repeat"></div>')


def story_jr_paste(img, color):
    """Logo JR della storia su un'immagine PIL 9:16 (qualsiasi misura), colore (r, g, b)."""
    from PIL import Image
    a = story_jr_stamp_alpha()
    h = round(STORY_JR_H * img.height / STORY_H)
    w = round(a.width * h / a.height)
    mask = a.resize((w, h), Image.LANCZOS)
    img.paste(Image.new(img.mode, (w, h), tuple(color) + ((255,) if img.mode == 'RGBA' else ())),
              ((img.width - w) // 2, round(STORY_JR_TOP * img.height / STORY_H)), mask)
    return img


@lru_cache(maxsize=16)
def overlay_jr_color(path):
    """Colore del JR in alto a destra di un overlay 3:4 (titolo e JR), come '#rrggbb'."""
    import numpy as np
    from PIL import Image
    with Image.open(path) as im:
        a = np.asarray(im.convert('RGBA'), np.float32)
    corner = a[: a.shape[0] // 8, int(a.shape[1] * STORY_JR_CUT):]
    solid = corner[corner[..., 3] > 200]
    if not len(solid):
        return '#121212'
    r, g, b = np.median(solid[:, :3], 0)
    return f'#{int(r):02x}{int(g):02x}{int(b):02x}'


@lru_cache(maxsize=8)
def _story_fx(path, light, top):
    import io

    import numpy as np
    from PIL import Image

    raw = base64.b64decode(_fx(path, light).split(',', 1)[1])
    a = np.asarray(Image.open(io.BytesIO(raw)).convert('RGBA').resize((OUT_W, OUT_H), Image.LANCZOS))
    a = np.pad(a, ((top, STORY_OUT_H - OUT_H - top), (0, 0), (0, 0)), mode='edge')
    out = io.BytesIO()
    Image.fromarray(a).save(out, 'PNG')
    return 'data:image/png;base64,' + base64.b64encode(out.getvalue()).decode('ascii')


FX_SMOOTH = 6.0      # sfocatura (pixel a 1920) che porta via la grana
FX_GRAIN = 12.0      # differenze dalla versione sfocata sotto questa soglia (0-255) sono grana;
                     # sopra (ombre delle scritte, bordi) restano nitide


@lru_cache(maxsize=16)
def _fx(path, light):
    """Sfumatura Canva senza grana: versione sfocata + solo i dettagli forti
    dell'originale (contorni), così le ombre delle scritte restano nitide. Colore
    pre-moltiplicato per la trasparenza: i bordi non si scuriscono.
    light=True: anche ricolorata nel crema delle foto home."""
    import io

    import cv2
    import numpy as np
    from PIL import Image

    a = np.asarray(Image.open(path).convert('RGBA')).astype(np.float32)
    if light:
        solid = a[..., 3] > 240
        base = np.median(a[solid][:, :3], axis=0)               # bianco Canva della sfumatura
        a[..., :3] = np.clip(a[..., :3] * (np.array(HOME_FX_COLOR) / base), 0, 255)
    pre = np.dstack([a[..., :3] * a[..., 3:] / 255, a[..., 3:]])
    smooth = cv2.GaussianBlur(pre, (0, 0), FX_SMOOTH)
    detail = pre - smooth
    strength = np.abs(detail).max(2, keepdims=True)
    keep = np.clip((strength - FX_GRAIN) / FX_GRAIN, 0, 1)
    pre = smooth + detail * keep
    alpha = np.clip(pre[..., 3:], 0, 255)
    a[..., :3] = np.where(alpha > .3, pre[..., :3] * 255 / np.maximum(alpha, .3), 0)
    a[..., 3:] = alpha
    out = io.BytesIO()
    Image.fromarray(np.clip(a + .5, 0, 255).astype('uint8'), 'RGBA').save(out, format='PNG')
    return 'data:image/png;base64,' + base64.b64encode(out.getvalue()).decode('ascii')


# Matchday e Starting XI: posa 3:4 del giocatore già scontornata (players_matchday/ negli asset),
# con la maglia della partita. Le grafiche UEFA prendono la maglia su cui sono disegnate.
MATCHDAY_POSES = {'arms_crossed': 'pose_01_arms_crossed', 'pointing': 'pose_02_pointing'}


def matchday_pose(player, kit, pose):
    from graphics.probabili import PHOTO_KIT
    from graphics.uefa import ALL, base_kit
    if pose not in MATCHDAY_POSES:
        raise ValueError('Posa non valida.')
    if kit not in ALL:
        raise ValueError('Maglia non valida.')
    shirt = kit if kit in PHOTO_KIT else base_kit(kit)
    suffix, keeper = PHOTO_KIT.get(shirt, PHOTO_KIT['home'])
    tag = keeper if player.role == 'goalkeeper' else suffix
    folder = asset_dir() / 'players_matchday' / player.slug
    name = f'{player.slug}{"_" + tag if tag else ""}_{MATCHDAY_POSES[pose]}.png'
    path = folder / name
    if not path.is_file():
        raise ValueError(f'Manca la posa di {player.name} con questa maglia.')
    return path


@lru_cache(maxsize=4)
def _story_paper_light(w, h, seed):
    """Luce di carta stropicciata + vignettatura delle storie IG normali (ig_story), già pronta da moltiplicare."""
    import numpy as np
    from graphics import compleanno as cp
    light = cp._crumple((w, h), seed, 0.7, folds=3)
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    r = np.sqrt(((xx - w / 2) / (w / 2)) ** 2 + ((yy - h / 2) / (h / 2)) ** 2) / np.sqrt(2)
    return (light * (1 - .18 * r ** 2)).astype(np.float32)


def story_paper(data, seed=7):
    """Effetto carta delle storie IG normali sopra una storia 9:16 già pronta (bytes PNG/JPEG -> stessi bytes)."""
    import io
    import numpy as np
    from PIL import Image
    with Image.open(io.BytesIO(data)) as im:
        fmt = (im.format or 'PNG').upper()
        rgb = im.convert('RGB')
    w, h = rgb.size
    a = np.asarray(rgb, np.float32) / 255
    a = a + np.random.default_rng(seed).normal(0, .035, (h, w, 1)).astype(np.float32)
    a = np.clip(a * _story_paper_light(w, h, seed)[..., None], 0, 1)
    out = io.BytesIO()
    img = Image.fromarray(np.uint8(a * 255 + .5))
    if fmt == 'JPEG':
        img.save(out, 'JPEG', quality=95, subsampling=0)
    else:
        img.save(out, 'PNG')
    return out.getvalue()
