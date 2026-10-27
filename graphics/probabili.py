"""PROBABILE XI: pagine 3-5 (home), 8-10 (away), 13-15 (third).

Ogni giocatore è una "carta" Canva: lastre sfumate, testa (ritaglio fisso della
foto braccia incrociate degli asset) ed etichetta col cognome. I moduli Canva
sono 4-2-3-1, 3-4-2-1 e 3-4-1-2; gli altri (anche quelli creati da te) stanno in data/probabili_layouts.json.
"""
import json
import unicodedata
from functools import lru_cache
from pathlib import Path

from graphics.common import DESIGN_H, DESIGN_W, asset_dir, data_uri, esc, render_html, team_logo

KITS = ('home', 'away', 'third')
# Foto della testa per maglia: (suffisso giocatori, maglia portiere).
PHOTO_KIT = {'home': ('', 'keeper_blue'), 'away': ('away_pink', 'keeper_green'),
             'third': ('third_black', 'keeper_orange')}
HEAD_CROP = (303, 2, 953, 652)     # stesso ritaglio usato su Canva (foto 1254x1254)
NAME_FONT, NAME_SIZE, NAME_SPACING = 'Poppins', 26.17, 1.26
NAME_MAX_W = 214                   # oltre questa larghezza il nome si stringe

# Griglia di "Modifica" nella Mini App: le card si spostano solo su questi punti
# (centro x, alto dell'etichetta). 19 colonne (le 17 fra le fasce più una per lato,
# a 67,5 e 1012,5), 46 righe: 45 da attacco a portiere più una sotto il portiere,
# tutte alla stessa distanza (quella che prima c'era solo fra il portiere e l'ultima
# riga). Passo dimezzato rispetto alla griglia 19x24: i suoi punti restano tutti
# (una riga su due).
GRID_X = [round(120 + 52.5 * i, 2) for i in range(-1, 18)]
GRID_STEP_Y = (1228.16 - 295.4) / 44
GRID_Y = [round(295.4 + i * GRID_STEP_Y, 2) for i in range(45)]
GRID_Y.append(round(1228.16 + GRID_STEP_Y, 2))   # un passo sotto il portiere

# Parte visibile della card rispetto a (centro x, alto etichetta), a misura piena:
# lastre/etichetta ±117 in larghezza, dalla testa (-175,4) al fondo etichetta (+58,9).
CARD_EXTENT = (-117.0, 117.0, -175.42, 58.9)
CARD_MARGIN = 12          # la card resta sempre dentro la pagina, a questa distanza dal bordo


def fit_card(cx, top, s=1.0):
    """Posizione disegnata: se la card uscirebbe dalla pagina (colonne esterne, card
    grandi) si sposta dentro quanto basta. La posizione salvata resta quella della griglia."""
    left, right, up, down = (v * s for v in CARD_EXTENT)
    cx = min(max(cx, CARD_MARGIN - left), DESIGN_W - CARD_MARGIN - right)
    top = min(max(top, CARD_MARGIN - up), DESIGN_H - CARD_MARGIN - down)
    return cx, top


LABEL_H = 58.9            # altezza della barra col nome (a misura piena)
LABEL_GAP = 12            # spazio minimo fra due barre col nome affiancate (come il bordo pagina)


def place_cards(cards, s=1.0):
    """Posizioni disegnate di tutte le card: dentro la pagina e con le barre del nome
    ad almeno LABEL_GAP l'una dall'altra.

    Due barre alla stessa altezza troppo vicine si allontanano in orizzontale, ognuna
    dalla sua parte, solo quanto basta. La spinta passa anche alle card vicine
    dall'altra parte (gli spazi fra card a contatto restano uguali) e, se una card è
    già al bordo, si sposta di più l'altra. Le foto sopra possono sovrapporsi un po'
    (lì c'è spazio libero). La posizione salvata non cambia.
    """
    width = (CARD_EXTENT[1] - CARD_EXTENT[0]) * s
    height = LABEL_H * s
    pos = [list(fit_card(x, top, s)) for x, top in cards]
    for _ in range(200):
        moved = False
        for i in range(len(pos)):
            for j in range(i + 1, len(pos)):
                (xi, ti), (xj, tj) = pos[i], pos[j]
                if abs(ti - tj) >= height + LABEL_GAP:
                    continue                                   # barre ad altezze diverse
                need = width + LABEL_GAP - abs(xi - xj)
                if need <= 0.01:
                    continue
                side = 1 if (xj, j) > (xi, i) else -1          # j a destra di i (a parità, l'ordine)
                pos[i][0] -= side * need / 2
                pos[j][0] += side * need / 2
                moved = True
        pos = [list(fit_card(x, top, s)) for x, top in pos]    # dentro la pagina: spinge l'altra
        if not moved:
            break
    # File impossibili (troppe card per la larghezza, es. 5 difensori grandi): a spazi
    # uguali fra i due bordi, il massimo spazio possibile.
    lo = CARD_MARGIN - CARD_EXTENT[0] * s
    hi = DESIGN_W - CARD_MARGIN - CARD_EXTENT[1] * s
    parent = list(range(len(pos)))

    def root(a):
        while parent[a] != a:
            a = parent[a]
        return a

    for i in range(len(pos)):
        for j in range(i + 1, len(pos)):
            if (abs(pos[i][1] - pos[j][1]) < height + LABEL_GAP
                    and abs(pos[i][0] - pos[j][0]) < width + LABEL_GAP - 0.5):
                parent[root(j)] = root(i)
    rows = {}
    for i in range(len(pos)):
        rows.setdefault(root(i), []).append(i)
    for row in rows.values():
        if len(row) > 1 and (width + LABEL_GAP) * (len(row) - 1) > hi - lo:
            row.sort(key=lambda i: (pos[i][0], i))
            for k, i in enumerate(row):
                pos[i][0] = lo + k * (hi - lo) / (len(row) - 1)
    return [tuple(p) for p in pos]


SHORT_NAMES = {'nicolas_gonzalez': 'Nico Gonzalez', 'douglas_luiz': 'Douglas Luiz',
               'randal_kolo_muani': 'Kolo Muani', 'khephren_thuram_ulien': 'Thuram',
               'neto_murara': 'Neto', 'lloyd_casius_kelly': 'Kelly', 'pape_matar_sarr': 'Sarr',
               'juan_david_cabal': 'Cabal'}


@lru_cache(maxsize=1)
def _meta():
    return json.loads((asset_dir() / 'canva' / 'probabili.json').read_text(encoding='utf-8'))


def plain(text):
    return ''.join(c for c in unicodedata.normalize('NFKD', text) if not unicodedata.combining(c))


def label_name(player):
    """Nome sull'etichetta: cognome come su Canva, senza accenti."""
    if player.slug in SHORT_NAMES:
        return SHORT_NAMES[player.slug].upper()
    singles = [a for a in player.aliases if '.' not in a and ' ' not in a.strip()]
    return plain(singles[-1] if singles else player.name.split()[-1]).upper()


def head_photo(player, kit):
    suffix, keeper = PHOTO_KIT[kit]
    folder = asset_dir() / 'players' / player.slug
    tag = keeper if player.role == 'goalkeeper' else suffix
    name = f'{player.slug}_{tag}_pose_01_arms_crossed.png' if tag else f'{player.slug}_pose_01_arms_crossed.png'
    path = folder / name
    if not path.is_file():
        path = folder / f'{player.slug}_pose_01_arms_crossed.png'
    if not path.is_file():
        raise ValueError(f'Foto mancante per {player.name}.')
    return path


def _rect(base, rel, s=1.0):
    """Riquadro relativo alla carta; s = scala della carta (1 = misura Canva)."""
    return base[0] + rel[0] * s, base[1] + rel[1] * s, rel[2] * s, rel[3] * s


def check_layout(module):
    """Nessuna etichetta deve coprire un'altra carta (testa o etichetta)."""
    meta = _meta()['home']
    boxes = []
    import layouts
    layout = layouts.get(module)
    s = layout['scale']
    for cx, top in layout['cards']:
        boxes.append((_rect((cx, top), meta['box'], s), _rect((cx, top), meta['head_rect'], s)))
    clashes = []
    for i, (label_i, _h) in enumerate(boxes):
        for j, (label_j, head_j) in enumerate(boxes):
            if i == j:
                continue
            for other in ((label_j, head_j) if i < j else (head_j,)):
                x, y, w, h = label_i
                ox, oy, ow, oh = other
                if x < ox + ow and ox < x + w and y < oy + oh and oy < y + h:
                    clashes.append((i, j))
    return clashes


def build_html(*, kit, module, players, home_name, home_id, away_name, away_id, layout=None, **_):
    if kit not in KITS:
        raise ValueError('Maglia non valida.')
    import layouts
    if layouts.sizes(module) is None:
        raise ValueError('Modulo non valido.')
    if len(players) != 11:
        raise ValueError('Servono 11 giocatori.')
    meta = _meta()[kit]
    canva = asset_dir() / 'canva'
    plates = data_uri(canva / meta['plates'])
    label = data_uri(canva / meta['label'])
    text = meta['text']
    # Posizioni e grandezza: quelle passate (Modifica), altrimenti salvate o Canva.
    if layout is None:
        import layouts
        layout = layouts.get(module)
    s = layout['scale']
    k = meta['head_rect'][2] * s / (HEAD_CROP[2] - HEAD_CROP[0])

    cards, labels, names = [], [], []   # lastre+teste sotto, blocchi coi nomi sempre sopra
    for i, ((cx, top), player) in enumerate(zip(place_cards(layout['cards'], s), players)):
        px, py, pw, ph = _rect((cx, top), meta['plates_rect'], s)
        hx, hy, hw, hh = _rect((cx, top), meta['head_rect'], s)
        lx, ly, lw, lh = _rect((cx, top), meta['label_rect'], s)
        cards.append(
            f'<img class="abs" src="{plates}" style="left:{px}px;top:{py}px;width:{pw}px;height:{ph}px">'
            f'<div class="head" style="left:{hx}px;top:{hy}px;width:{hw}px;height:{hh}px">'
            f'<img src="{data_uri(head_photo(player, kit))}" style="left:{-HEAD_CROP[0] * k}px;'
            f'top:{-HEAD_CROP[1] * k}px;width:{1254 * k}px;height:{1254 * k}px"></div>'
        )
        labels.append(f'<img class="abs" src="{label}" style="left:{lx}px;top:{ly}px;width:{lw}px;height:{lh}px">')
        x, base = cx + text['cx'] * s, top + text['base'] * s
        t = (f'<text x="{x}" y="{base}" text-anchor="middle" font-family="{NAME_FONT}" font-weight="500" '
             f'font-size="{NAME_SIZE * s}" letter-spacing="{NAME_SPACING * s}" data-fit="{NAME_MAX_W * s}">'
             f'{esc(label_name(player))}</text>')
        if 'texture' in text:
            bx, by, bw, bh = _rect((cx, top), meta['box'], s)
            names.append(f'<clipPath id="n{i}">{t}</clipPath><image href="{data_uri(canva / text["texture"])}" '
                         f'x="{bx}" y="{by}" width="{bw}" height="{bh}" preserveAspectRatio="none" '
                         f'clip-path="url(#n{i})"/>')
        else:
            names.append(t.replace('<text ', f'<text fill="{text["color"]}" ', 1))

    logos = ''.join(
        f'<div class="logo" style="left:{x}px;top:{y}px;width:{size}px;height:{size}px;background:{meta["logo_color"]};'
        f'--m:url({data_uri(team_logo(name, team_id))})"></div>'
        for (x, y, size), (name, team_id) in zip(meta['logos'], ((home_name, home_id), (away_name, away_id)))
    )
    poppins = data_uri(asset_dir() / 'fonts' / 'Poppins-Medium.ttf')

    return f'''<!doctype html><html><head><meta charset="utf-8"><style>
*{{margin:0;padding:0;box-sizing:border-box}}
html,body{{width:{DESIGN_W}px;height:{DESIGN_H}px;overflow:hidden;background:#fff}}
.abs{{position:absolute}}
.head{{position:absolute;overflow:hidden}} .head img{{position:absolute}}
.logo{{position:absolute;-webkit-mask:var(--m) center/100% 100% no-repeat;mask:var(--m) center/100% 100% no-repeat}}
@font-face{{font-family:'Poppins';font-weight:500;src:url({poppins})}}
svg{{position:absolute;left:0;top:0}}
</style></head><body>
<img class="abs" src="{data_uri(canva / meta['bg'])}" style="left:0;top:0;width:{DESIGN_W}px;height:{DESIGN_H}px">
{''.join(cards)}{''.join(labels)}{logos}
<svg width="{DESIGN_W}" height="{DESIGN_H}" viewBox="0 0 {DESIGN_W} {DESIGN_H}">{''.join(names)}</svg>
<script>
// Nomi lunghi: si stringono per restare dentro l'etichetta.
document.fonts.ready.then(() => document.querySelectorAll('text[data-fit]').forEach(t => {{
  const max = Number(t.dataset.fit), w = t.getComputedTextLength();
  if (w > max) {{ t.setAttribute('textLength', max); t.setAttribute('lengthAdjust', 'spacingAndGlyphs'); }}
}}));
</script>
</body></html>'''


def render(**kwargs):
    return render_html(build_html(**kwargs))
