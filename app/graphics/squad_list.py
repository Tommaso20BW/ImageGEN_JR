"""SQUAD LIST "rivista": i convocati stampati su una rivista aperta, foto vera (mockup).

Foto: canva/squad_list_rivista.jpg negli asset (rivista aperta con pagine bianche, tavolo e
riviste grigi). Si disegnano due pagine piatte in HTML:
- sinistra: logo della competizione grande, centrato e tagliato dall'inquadratura;
- destra: loghi delle due squadre, nomi su due colonne uguali e simmetriche
  (in ordine alfabetico, grandezza adattiva), competizione e numero di giocatori.
Poi si "stampano" sulle pagine della foto seguendo la curvatura della carta (patch di Coons
dai quattro bordi), con le ombre e la piega della foto sopra; tavolo e riviste prendono il
colore della competizione; grana di carta leggera su tutto.

La geometria (dove finisce ogni pixel delle pagine) non dipende né dalla competizione né dai
nomi: si calcola una volta sola, direttamente a 1920x2560, e resta in memoria.
"""
import base64
import functools
import io
import re

import numpy as np
from PIL import Image

from graphics.common import STORY_OUT_H, asset_dir, data_uri, esc, font_face, normalize, render_html, team_logo

PHOTO = 'squad_list_rivista.jpg'
OUT_W, OUT_H = 1920, 2560
PW, PH = 1080, 1512                      # pagina piatta (design)
# Inquadratura in pixel della foto originale: centro, larghezza del ritaglio 3:4, rotazione
# (3.9 gradi = piega verticale, libro dritto).
VIEW = dict(cx=1150, cy=1210, width=1230, angle=3.9)
# Storia IG: inquadratura più stretta sulla pagina destra (nomi più grandi, riempie l'altezza).
STORY_VIEW = dict(cx=1187, cy=1205, width=1000, angle=3.9)
CURVE = 1.0                              # quanto il disegno segue la curvatura della carta (1 = tutta)
TEXTURE = .045                           # grana della carta
BOTTOM_EDGE = 8                          # px del bordo inferiore delle pagine senza il filo chiaro della foto
LOWER_MAGAZINE = (1120, 1880, 1792, 2400)  # foto originale: rivista sotto, il suo spigolo ha un riflesso bianco
VERTICAL = ''                            # scritta verticale lungo la piega (es. 'THE SQUAD'; '' = nessuna, contenuto centrato)

# pagina (chiaro, base, scuro), colore del tavolo, logo competizione, nome
PALETTES = {
    'ita.1': ('#2c66cf', '#1442a0', '#0a2668', (16, 44, 110), 'serie-a-scudetto.png', 'SERIE A'),
    'ita.coppa_italia': ('#e0313f', '#b5121f', '#6c0711', (120, 10, 22), 'coppa-italia-mark.png', 'COPPA ITALIA'),
    'uefa.champions': ('#30479f', '#18286f', '#0a1240', (16, 26, 80), 'ucl-mark.png', 'CHAMPIONS LEAGUE'),
    'uefa.europa': ('#f08a36', '#d2620f', '#7a3104', (150, 60, 8), 'uel-mark.png', 'EUROPA LEAGUE'),
    'uefa.europa.conf': ('#34b856', '#148333', '#06451a', (12, 90, 34), 'uecl-mark.png', 'CONFERENCE LEAGUE'),
    'ita.super_cup': ('#2f86e8', '#1258b8', '#082c66', (12, 50, 110), 'supercoppa-mark.png', 'SUPERCOPPA ITALIANA'),
    'uefa.super_cup': ('#2f7fe0', '#14479e', '#081f55', (14, 40, 100), 'usc-mark.png', 'SUPERCOPPA UEFA'),
    'fifa.cwc': ('#4a4232', '#2a251b', '#100e0a', (60, 48, 22), 'cwc-mark.png', 'MONDIALE PER CLUB'),
    # amichevoli (e competizioni senza tema): grigio, pagina sinistra senza logo
    'club.friendly': ('#5d6672', '#363c45', '#16191e', (40, 44, 52), None, 'AMICHEVOLE'),
}

MAX_PLAYERS = 30
# "3 Bremer", "3. Bremer", "Bremer 3", "#3 Bremer"
LINE_RE = re.compile(r'^\s*(?:#?\s*(\d{1,2})(?:[\s.)\-–—:]+))?(.*?)(?:\s+[#(]?(\d{1,2})\)?)?\s*$')


def parse_squad(text):
    """[[nome, numero]] in ordine alfabetico. Il numero scritto nella riga ("3 Bremer", come nei
    convocati di juventus.com) si tiene ma la grafica mostra solo i nomi. Niente doppioni."""
    rows = {}
    for line in str(text or '').splitlines():
        match = LINE_RE.match(line)
        name = ' '.join(re.sub(r'[\s#.\-–—()]+$|^[\s#.\-–—)]+', '', match.group(2)).split())
        if not name or name.endswith(':') or not re.search(r'[^\W\d_]', name):
            continue
        number = match.group(1) or match.group(3)
        rows.setdefault(normalize(name), [name, int(number) if number else None])
    if not rows:
        raise ValueError('Elenco vuoto: incolla almeno un giocatore.')
    if len(rows) > MAX_PLAYERS:
        raise ValueError(f'Troppi giocatori ({len(rows)}): massimo {MAX_PLAYERS}.')
    return sorted(rows.values(), key=lambda r: normalize(r[0]))


# ---------------- pagine piatte (HTML) ----------------

def _fonts():
    a = asset_dir() / 'fonts'
    return (f"@font-face{{font-family:'Dharma';src:url({data_uri(a / 'DharmaGothicEBold.otf')})}}"
            f"@font-face{{font-family:'Poppins';font-weight:500;src:url({data_uri(a / 'Poppins-Medium.ttf')})}}")


def _page_css(light, base, dark):
    return (f'*{{margin:0;padding:0;box-sizing:border-box}}html,body{{width:{PW}px;height:{PH}px;overflow:hidden}}'
            f'body{{position:relative;color:#fff;background:radial-gradient(ellipse 70% 55% at 60% 32%,{light},transparent 72%),'
            f'radial-gradient(ellipse 120% 100% at 50% 45%,{base} 45%,{dark} 100%)}}{_fonts()}')


READY = ('<script>window.__ready=document.fonts.ready.then(()=>Promise.all([...document.images]'
         '.map(i=>i.decode().catch(()=>{}))));</script>')


@functools.lru_cache(maxsize=16)
def _mark(file):
    """Logo della competizione bianco, senza margini e con bordo liscio (i loghi piccoli si
    ingrandiscono molto): (data uri, larghezza/altezza)."""
    import cv2
    if file:
        im = Image.open(asset_dir() / 'canva' / 'classifica' / file).convert('RGBA')
    else:
        im = Image.open(asset_dir() / 'canva' / 'jr_white_overlay.png').convert('RGBA')
    im = im.crop(im.getchannel('A').point(lambda v: 255 if v > 30 else 0).getbbox())
    pad = max(4, im.height // 40)                 # la punta del logo non tocca il bordo dell'immagine
    padded = Image.new('RGBA', (im.width + 2 * pad, im.height + 2 * pad), (255, 255, 255, 0))
    padded.paste(im, (pad, pad))
    k = max(1, 2400 // padded.height)
    alpha = np.asarray(padded.getchannel('A').resize((padded.width * k, padded.height * k), Image.Resampling.LANCZOS))
    alpha = cv2.GaussianBlur(alpha.astype(np.float32) / 255, (0, 0), 1.6 * k)
    alpha = np.clip((alpha - .5) * 3.2 + .5, 0, 1)
    out = Image.new('RGBA', (alpha.shape[1], alpha.shape[0]), (255, 255, 255, 0))
    out.putalpha(Image.fromarray((alpha * 255).astype(np.uint8)))
    buf = io.BytesIO()
    out.save(buf, 'PNG')
    return 'data:image/png;base64,' + base64.b64encode(buf.getvalue()).decode(), out.width / out.height


# Logo sulla pagina sinistra: dell'inquadratura si vede solo la metà verso la piega
# (da circa 575 px a 1080). Stessa regola per tutti: bordo destro a LOGO_RIGHT (non entra
# nella piega), altezza al massimo LOGO_MAX_H (margine sopra e sotto), larghezza al massimo
# LOGO_MAX_W: così ogni logo è tagliato a sinistra più o meno della stessa parte.
LOGO_RIGHT, LOGO_MAX_W, LOGO_MAX_H, LOGO_CY = 1040, 850, 1050, 756
STORY_LOGO_RIGHT, STORY_LOGO_MAX_W = 1072, 620   # storia: si vede solo la parte vicino alla piega, logo grande ma attaccato alla piega


def left_page(competition, story=False):
    """Logo grande della competizione, tagliato a sinistra dall'inquadratura in modo uguale
    per tutti (LOGO_*). Amichevoli: pagina senza logo."""
    light, base, dark, _table, mark, _name = PALETTES[competition]
    logo = ''
    if mark:
        uri, ratio = _mark(mark)
        h = min(LOGO_MAX_H, (STORY_LOGO_MAX_W if story else LOGO_MAX_W) / ratio)
        w = h * ratio
        right = STORY_LOGO_RIGHT if story else LOGO_RIGHT
        logo = (f'<img src="{uri}" style="position:absolute;left:{right - w}px;top:{LOGO_CY - h / 2}px;'
                f'width:{w}px;height:{h}px;opacity:.94">')
    return (f'<!doctype html><html><head><meta charset="utf-8"><style>{_page_css(light, base, dark)}</style></head>'
            f'<body>{logo}{READY}</body></html>')


def right_page(competition, names, home, away):
    """Pagina destra impaginata su due colonne uguali, simmetriche rispetto al centro: loghi delle
    squadre, nomi e riga finale stanno ognuno al centro della sua colonna. La lista è grande quanto
    può e, con pochi nomi, le righe si allargano: il blocco resta centrato in verticale."""
    light, base, dark, _table, _mark_file, comp_name = PALETTES[competition]
    half = (len(names) + 1) // 2
    col = lambda rows: ''.join(f'<p>{esc(n)}</p>' for n in rows)
    logos = ''.join(f'<div><img src="{data_uri(team_logo(name, team_id))}"></div>' for name, team_id in (home, away))
    left, right = (372, 40) if VERTICAL else (90, 90)
    vertical = f'<div class="vt"><span>{esc(VERTICAL)}</span></div>' if VERTICAL else ''
    return f"""<!doctype html><html><head><meta charset="utf-8"><style>{_page_css(light, base, dark)}
.vt{{position:absolute;left:24px;top:0;width:300px;height:{PH}px;display:flex;align-items:center;justify-content:center}}
.vt span{{transform:rotate(-90deg);font-family:'Dharma';font-size:420px;line-height:1;white-space:nowrap}}
.c{{position:absolute;left:{left}px;right:{right}px;top:110px;bottom:104px;display:flex;flex-direction:column;justify-content:center}}
.two{{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1fr);column-gap:80px;text-align:center}}
.head{{display:flex;justify-content:center;align-items:center;gap:56px}}
.head img{{display:block;width:150px;height:150px;object-fit:contain;filter:brightness(0) invert(1)}}
.lab{{margin:38px 0 26px;text-align:center;font-family:'Poppins';font-weight:500;font-size:26px;letter-spacing:.38em;text-indent:.38em;opacity:.85}}
.list{{font-size:100px}}
p{{line-height:1.42;font-family:'Poppins';font-weight:500;text-transform:uppercase;white-space:nowrap}}
.foot{{margin-top:56px;font-family:'Poppins';font-weight:500}}
.foot small{{display:block;font-size:22px;letter-spacing:.32em;text-indent:.32em;opacity:.8}}
.foot strong{{display:block;margin-top:8px;font-size:40px;white-space:nowrap;-webkit-text-stroke:1.6px #fff}}
</style></head><body>{vertical}
<div class="c"><div class="head">{logos}</div>
<div class="lab">CONVOCATI</div>
<div class="two list" id="list"><div>{col(names[:half])}</div><div>{col(names[half:])}</div></div>
<div class="two foot"><div><small>COMPETIZIONE</small><strong id="comp">{comp_name}</strong></div><div><small>GIOCATORI</small><strong>{len(names)}</strong></div></div></div>
<script>
const box = document.querySelector('.c'), list = document.getElementById('list');
const fits = () => [...list.querySelectorAll('p')].every(p => p.scrollWidth <= p.parentElement.clientWidth) && box.scrollHeight <= box.clientHeight;
window.__ready = document.fonts.ready.then(() => {{
  // nome della competizione lungo: più piccolo finché sta nella sua colonna
  const comp = document.getElementById('comp');
  let c = parseFloat(getComputedStyle(comp).fontSize);
  while (comp.scrollWidth > comp.parentElement.clientWidth && c > 16) {{ c -= 1; comp.style.fontSize = c + 'px'; }}
  // lista: la più grande che sta in larghezza (colonna) e in altezza
  let s = parseFloat(getComputedStyle(list).fontSize);
  while (s > 10 && !fits()) {{ s -= 1; list.style.fontSize = s + 'px'; }}
  // pochi nomi: righe più larghe fino a riempire, con un massimo
  // spazio libero vero: il blocco è centrato, scrollHeight non lo vede
  const used = () => box.lastElementChild.offsetTop + box.lastElementChild.offsetHeight - box.firstElementChild.offsetTop;
  const lines = Math.max(...[...list.children].map(c => c.children.length));
  let free = box.clientHeight - used();
  const lh = Math.min(1.9, 1.42 + Math.max(0, free * .7) / (lines * s));
  list.querySelectorAll('p').forEach(p => p.style.lineHeight = lh);
  // il resto allarga gli stacchi tra loghi, CONVOCATI, nomi e riga finale
  free = Math.max(0, box.clientHeight - used() - 10);
  const lab = box.querySelector('.lab'), foot = box.querySelector('.foot');
  const add = Math.min(free / 3, 70);
  lab.style.marginTop = (38 + add) + 'px'; lab.style.marginBottom = (26 + add / 2) + 'px';
  foot.style.marginTop = (56 + add * 1.5) + 'px';
  return Promise.all([...document.images].map(i => i.decode().catch(() => {{}})));
}});
</script></body></html>"""


# ---------------- geometria della foto (una volta sola) ----------------

def _pages_mask(gray):
    """Le due pagine: le due aree chiare più grandi, da sinistra a destra."""
    import cv2
    m = (gray > 125).astype(np.uint8)
    m = cv2.morphologyEx(m, cv2.MORPH_OPEN, np.ones((5, 5), np.uint8))
    n, lab, st, _ = cv2.connectedComponentsWithStats(m, 8)
    big = sorted(range(1, n), key=lambda k: -st[k, cv2.CC_STAT_AREA])[:2]
    big.sort(key=lambda k: st[k, cv2.CC_STAT_LEFT])
    return [cv2.morphologyEx((lab == k).astype(np.uint8), cv2.MORPH_CLOSE, np.ones((9, 9), np.uint8)).astype(bool) for k in big]


def _fit(t, vals, deg):
    med = np.array([np.median(vals[max(0, i - 25):i + 26]) for i in range(len(vals))])
    keep = np.abs(vals - med) < 5
    return np.poly1d(np.polyfit(t[keep], vals[keep], deg))


def _surface(mask):
    """P(u, v) -> punto della foto per un punto della pagina piatta (u, v in 0..1): patch di
    Coons dai quattro bordi curvi della pagina, mescolata con la prospettiva piatta (CURVE)."""
    import cv2
    ys, xs = np.nonzero(mask)
    pick = lambda i: np.array([xs[i], ys[i]], float)
    tl, br = pick(np.argmin(xs + ys)), pick(np.argmax(xs + ys))
    tr, bl = pick(np.argmax(xs - ys)), pick(np.argmax(ys - xs))
    m = 12

    def cols(a, b, first):
        xx = np.arange(int(a) + m, int(b) - m)
        yy = np.array([(np.nonzero(mask[:, x])[0].min() if first else np.nonzero(mask[:, x])[0].max()) for x in xx], float)
        return _fit(xx.astype(float), yy, 3)

    def rows(a, b, first):
        yy = np.arange(int(a) + m, int(b) - m)
        xx = np.array([(np.nonzero(mask[y])[0].min() if first else np.nonzero(mask[y])[0].max()) for y in yy], float)
        return _fit(yy.astype(float), xx, 2)
    top, bot = cols(tl[0], tr[0], True), cols(bl[0], br[0], False)
    lft, rgt = rows(tl[1], bl[1], True), rows(tr[1], br[1], False)
    T = lambda u: np.stack([tl[0] + u * (tr[0] - tl[0]), top(tl[0] + u * (tr[0] - tl[0]))], -1)
    B = lambda u: np.stack([bl[0] + u * (br[0] - bl[0]), bot(bl[0] + u * (br[0] - bl[0]))], -1)
    c00, c10, c01, c11 = T(np.array(0.)), T(np.array(1.)), B(np.array(0.)), B(np.array(1.))

    def side(fit, p0, p1):
        r0, r1 = np.array([fit(p0[1]), p0[1]]), np.array([fit(p1[1]), p1[1]])

        def f(v):
            y = p0[1] + v * (p1[1] - p0[1])
            return np.stack([fit(y), y], -1) + (1 - v)[..., None] * (p0 - r0) + v[..., None] * (p1 - r1)
        return f
    L, R = side(lft, c00, c01), side(rgt, c10, c11)
    corners = np.float32([c00, c10, c01, c11])
    Hp = cv2.getPerspectiveTransform(np.float32([[0, 0], [1, 0], [0, 1], [1, 1]]), corners)

    def P(u, v):
        uu, vv = u[..., None], v[..., None]
        curved = ((1 - vv) * T(u) + vv * B(u) + (1 - uu) * L(v) + uu * R(v)
                  - ((1 - uu) * (1 - vv) * c00 + uu * (1 - vv) * c10 + (1 - uu) * vv * c01 + uu * vv * c11))
        w = Hp[2, 0] * u + Hp[2, 1] * v + Hp[2, 2]
        flat = np.stack([(Hp[0, 0] * u + Hp[0, 1] * v + Hp[0, 2]) / w, (Hp[1, 0] * u + Hp[1, 1] * v + Hp[1, 2]) / w], -1)
        return CURVE * curved + (1 - CURVE) * flat
    return P, corners


def _invert(P, corners, pts):
    """(u, v) per ogni punto della foto (Newton, partendo dalla prospettiva dei quattro angoli)."""
    import cv2
    H = cv2.getPerspectiveTransform(corners, np.float32([[0, 0], [1, 0], [0, 1], [1, 1]]))
    uv = cv2.perspectiveTransform(pts[None].astype(np.float32), H)[0].astype(float)
    u, v = uv[:, 0], uv[:, 1]
    e = 1e-3
    for _ in range(6):
        p = P(u, v)
        du, dv = (P(u + e, v) - p) / e, (P(u, v + e) - p) / e
        r = pts - p
        det = du[:, 0] * dv[:, 1] - du[:, 1] * dv[:, 0]
        u = u + (r[:, 0] * dv[:, 1] - r[:, 1] * dv[:, 0]) / det
        v = v + (du[:, 0] * r[:, 1] - du[:, 1] * r[:, 0]) / det
    return np.clip(u, 0, 1), np.clip(v, 0, 1)


def _no_magazine_glint(photo):
    """Toglie il riflesso bianco dallo spigolo della rivista sotto: non supera il grigio della carta vicina."""
    import cv2
    x0, y0, x1, y1 = LOWER_MAGAZINE
    clean = photo.copy()
    area = clean[y0:y1, x0:x1]
    usual = cv2.medianBlur(area, 21)
    glint = cv2.dilate(((area.astype(np.int16) - usual) > 10).astype(np.uint8), np.ones((3, 3), np.uint8)).astype(bool)
    paper = cv2.dilate(usual, np.ones((9, 9), np.uint8))      # il grigio della rivista lì accanto: lo spigolo resta vivo
    area[glint] = np.minimum(area, paper)[glint]
    return clean


def _no_bottom_glow(gray, solid):
    """Il bordo inferiore delle pagine nella foto è più chiaro: lì la luce non supera quella della carta sopra."""
    import cv2
    page = solid.astype(np.uint8)
    above = np.roll(page, -BOTTOM_EDGE, axis=0)
    above[-BOTTOM_EDGE:] = 0
    edge = cv2.dilate(page & (1 - above), np.ones((5, 1), np.uint8)).astype(bool)
    weight = cv2.GaussianBlur(page.astype(np.float32), (0, 0), 10) + 1e-3
    around = cv2.GaussianBlur(gray * page, (0, 0), 10) / weight
    return np.where(edge, np.minimum(gray, around), gray)


@functools.lru_cache(maxsize=2)
def _geometry(path_key, out_h=OUT_H):
    """Per ogni pixel dell'immagine finale (1920x2560, o 1920x3413 per la storia: STORY_VIEW,
    più stretta sulla pagina dei nomi): grigio della foto (luce e ombre), quanto è pagina sinistra/destra e il punto (u, v)
    della pagina piatta da mostrare."""
    import cv2
    photo = np.asarray(Image.open(path_key).convert('L'))
    left, right = _pages_mask(photo)
    # pixel finale -> pixel della foto: inquadratura ruotata e ritagliata (3:4)
    view = STORY_VIEW if out_h != OUT_H else VIEW
    s = view['width'] / OUT_W
    a = np.deg2rad(view['angle'])
    X, Y = np.meshgrid(np.arange(OUT_W, dtype=np.float32), np.arange(out_h, dtype=np.float32))
    dx, dy = (X - OUT_W / 2) * s, (Y - out_h / 2) * s
    # rotazione inversa di quella usata per inquadrare (cv2: angolo positivo = antiorario)
    px = (view['cx'] + np.cos(a) * dx - np.sin(a) * dy).astype(np.float32)
    py = (view['cy'] + np.sin(a) * dx + np.cos(a) * dy).astype(np.float32)
    gray = cv2.remap(_no_magazine_glint(photo).astype(np.float32), px, py, cv2.INTER_CUBIC, borderMode=cv2.BORDER_REFLECT)
    gray = np.clip(gray, 0, 255)                     # il bicubico può uscire di poco da 0..255
    white = np.percentile(photo[right], 97)
    pages = []
    solid = np.zeros((out_h, OUT_W), bool)
    for mask in (left, right):
        alpha = cv2.remap(mask.astype(np.float32), px, py, cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT, borderValue=0)
        alpha = cv2.GaussianBlur(alpha, (0, 0), 1.5)
        inside = alpha > .002
        solid |= alpha > .5
        P, corners = _surface(mask)
        pts = np.stack([px[inside], py[inside]], -1).astype(float)
        u, v = _invert(P, corners, pts)
        uu = np.full((out_h, OUT_W), -1, np.float32); vv = np.full((out_h, OUT_W), -1, np.float32)
        uu[inside], vv[inside] = u, v
        pages.append((alpha.astype(np.float32), uu, vv))
    gray = _no_bottom_glow(gray, solid)
    return gray.astype(np.float32), float(white), pages


def _photo_path():
    return str(asset_dir() / 'canva' / PHOTO)


def warm_up():
    """Calcola la geometria della foto in anticipo (all'avvio del servizio): 3:4 e storia."""
    _geometry(_photo_path(), OUT_H)         # stessa chiave della cache usata da render()
    _geometry(_photo_path(), STORY_OUT_H)


def _texture(h, w, seed=7):
    import cv2
    rng = np.random.default_rng(seed)
    fine = cv2.GaussianBlur(rng.standard_normal((h, w)).astype(np.float32), (0, 0), sigmaX=1.6, sigmaY=.7)
    fine /= fine.std() + 1e-6
    blot = cv2.GaussianBlur(rng.standard_normal((h // 8, w // 8)).astype(np.float32), (0, 0), 6)
    blot = cv2.resize(blot / (blot.std() + 1e-6), (w, h), interpolation=cv2.INTER_CUBIC)
    return 1 + TEXTURE * (.65 * fine + .35 * blot)


_TEXTURE = {}


def _render_page(html):
    png = render_html(html, page=(PW, PH))
    return np.asarray(Image.open(io.BytesIO(png)).convert('RGB')).astype(np.float32)


def build_pages(*, players, competition, home_name, home_id, away_name, away_id, story=False, **_):
    if competition not in PALETTES:
        competition = 'club.friendly'
    names = sorted((p if isinstance(p, str) else p[0] for p in players), key=normalize)
    return (left_page(competition, story),
            right_page(competition, names, (home_name, home_id), (away_name, away_id)), competition)


def render(**kwargs):
    """PNG 1920x2560; story=True: storia IG 1920x3413 (inquadratura stretta sulla pagina dei nomi)."""
    import cv2
    story = bool(kwargs.get('story'))
    out_h = STORY_OUT_H if story else OUT_H
    left_html, right_html, competition = build_pages(**kwargs)
    gray, white, pages = _geometry(_photo_path(), out_h)
    # tavolo e riviste: chiari e scuri della foto nel colore della competizione
    tint = np.array(PALETTES[competition][3], np.float32)
    out = np.clip(tint * 1.6 * (gray[..., None] / 150.0) ** 1.5, 0, 255)
    shade = np.clip(gray / white, 0, 1.08)[..., None]           # luce della carta: ombre, piega, curvatura
    for (alpha, uu, vv), html in zip(pages, (left_html, right_html)):
        design = _render_page(html)
        dh, dw = design.shape[:2]
        page = cv2.remap(design, uu * (dw - 1), vv * (dh - 1), cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)
        a = alpha[..., None]
        out = out * (1 - a) + np.clip(page * shade, 0, 255) * a
    if out_h not in _TEXTURE:
        _TEXTURE[out_h] = _texture(out_h, OUT_W)
    out = np.clip(out * _TEXTURE[out_h][..., None], 0, 255).astype(np.uint8)
    img = Image.fromarray(out).convert('RGBA')
    if story:                # logo JR in basso, dove sta il timbro delle Storie IG
        from graphics.common import story_jr_paste
        story_jr_paste(img, (255, 255, 255))
    else:
        jr = Image.open(asset_dir() / 'canva' / 'jr_white_overlay.png').convert('RGBA').resize((OUT_W, OUT_H))
        img.alpha_composite(jr, (0, 0))
    buf = io.BytesIO()
    img.convert('RGB').save(buf, 'PNG')
    return buf.getvalue()
