"""PROBABILE XI: pagine 3-5 (home), 8-10 (away), 13-15 (third).

Ogni giocatore è una "carta" Canva: lastre sfumate, testa (ritaglio fisso della
foto braccia incrociate degli asset) ed etichetta col cognome. I moduli Canva
sono 4-2-3-1, 3-4-2-1 e 3-4-1-2; gli altri usano le stesse righe del campo.
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

# Carta = [centro x, alto del box etichetta] in pixel design, ordine:
# portiere, difesa (sx -> dx), centrocampo, attacco.
B4 = [[124.26, 956.16], [401.5, 991.04], [678.75, 991.04], [955.74, 956.16]]
B3 = [[225.0, 982.4], [540.0, 982.4], [851.77, 982.4]]
GK = [[540.0, 1228.16]]
WB = ([123.53, 695.04], [956.47, 695.04])
MODULES = {
    '4-2-3-1': GK + B4 + [[284.38, 712.32], [795.62, 712.32], [225.0, 468.16], [540.0, 547.2],
                          [855.0, 468.16], [540.0, 307.52]],
    '4-3-3': GK + B4 + [[284.38, 712.32], [540.0, 600.0], [795.62, 712.32], [225.0, 468.16],
                        [540.0, 307.52], [855.0, 468.16]],
    '4-4-2': GK + B4 + [[123.53, 660.0], [384.53, 708.16], [695.47, 708.16], [956.47, 660.0],
                        [306.01, 341.12], [773.99, 341.12]],
    '4-1-2-1-2': GK + B4 + [[540.0, 700.0], [225.0, 630.0], [855.0, 630.0], [540.0, 400.0],
                            [290.0, 341.12], [790.0, 341.12]],
    '3-4-2-1': GK + B3 + [WB[0], [384.53, 708.16], [695.47, 708.16], WB[1], [225.0, 424.64],
                          [855.0, 424.64], [540.0, 320.32]],
    '3-4-1-2': GK + B3 + [WB[0], [384.53, 717.76], [695.47, 717.76], WB[1], [540.0, 480.64],
                          [306.01, 341.12], [773.99, 341.12]],
    # Calcolati con tools/probabili_modules.py (nessuna carta sovrapposta).
    '4-3-1-2': GK + B4 + [[225.0, 716.0], [540.0, 716.0], [855.0, 716.0], [540.0, 476.0],
                          [306.01, 307.52], [773.99, 307.52]],
    '4-2-2-2': GK + B4 + [[384.53, 746.0], [695.47, 746.0], [123.53, 586.0], [956.47, 586.0],
                          [384.53, 307.52], [695.47, 307.52]],
    '4-3-2-1': GK + B4 + [[225.0, 716.0], [540.0, 716.0], [855.0, 716.0], [300.0, 476.0],
                          [780.0, 476.0], [540.0, 307.52]],
    '3-4-3': GK + B3 + [WB[0], [384.53, 708.16], [695.47, 708.16], WB[1],
                        [200.0, 380.0], [540.0, 380.0], [880.0, 380.0]],
    '3-5-2': GK + B3 + [WB[0], [330.0, 600.0], [540.0, 760.0], [750.0, 600.0], WB[1],
                        [306.01, 341.12], [773.99, 341.12]],
    '5-4-1': GK + [[110.0, 930.0], [325.0, 982.4], [540.0, 982.4], [755.0, 982.4], [970.0, 930.0],
                   [123.53, 660.0], [384.53, 708.16], [695.47, 708.16], [956.47, 660.0], [540.0, 341.12]],
}
# Carte rimpicciolite solo dove i giocatori non entrano a misura piena.
MODULE_SCALE = {'3-5-2': 0.9, '5-4-1': 0.9}

ROLES = {
    '4-2-3-1': ['POR', 'TS', 'DC', 'DC', 'TD', 'CDC', 'CDC', 'AS', 'COC', 'AD', 'ATT'],
    '4-3-3': ['POR', 'TS', 'DC', 'DC', 'TD', 'CC', 'CC', 'CC', 'AS', 'ATT', 'AD'],
    '4-4-2': ['POR', 'TS', 'DC', 'DC', 'TD', 'ES', 'CC', 'CC', 'ED', 'ATT', 'ATT'],
    '4-1-2-1-2': ['POR', 'TS', 'DC', 'DC', 'TD', 'CDC', 'CC', 'CC', 'COC', 'ATT', 'ATT'],
    '3-4-2-1': ['POR', 'DC', 'DC', 'DC', 'ES', 'CC', 'CC', 'ED', 'TRQ', 'TRQ', 'ATT'],
    '3-4-1-2': ['POR', 'DC', 'DC', 'DC', 'ES', 'CC', 'CC', 'ED', 'TRQ', 'ATT', 'ATT'],
    '4-3-1-2': ['POR', 'TS', 'DC', 'DC', 'TD', 'CC', 'CC', 'CC', 'TRQ', 'ATT', 'ATT'],
    '4-2-2-2': ['POR', 'TS', 'DC', 'DC', 'TD', 'CDC', 'CDC', 'AS', 'AD', 'ATT', 'ATT'],
    '4-3-2-1': ['POR', 'TS', 'DC', 'DC', 'TD', 'CC', 'CC', 'CC', 'TRQ', 'TRQ', 'ATT'],
    '3-4-3': ['POR', 'DC', 'DC', 'DC', 'ES', 'CC', 'CC', 'ED', 'AS', 'ATT', 'AD'],
    '3-5-2': ['POR', 'DC', 'DC', 'DC', 'ES', 'CC', 'CDC', 'CC', 'ED', 'ATT', 'ATT'],
    '5-4-1': ['POR', 'TS', 'DC', 'DC', 'DC', 'TD', 'ES', 'CC', 'CC', 'ED', 'ATT'],
}
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
    s = MODULE_SCALE.get(module, 1.0)
    for cx, top in MODULES[module]:
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


def build_html(*, kit, module, players, home_name, home_id, away_name, away_id, **_):
    if kit not in KITS:
        raise ValueError('Maglia non valida.')
    if module not in MODULES:
        raise ValueError('Modulo non valido.')
    if len(players) != 11:
        raise ValueError('Servono 11 giocatori.')
    meta = _meta()[kit]
    canva = asset_dir() / 'canva'
    plates = data_uri(canva / meta['plates'])
    label = data_uri(canva / meta['label'])
    text = meta['text']
    s = MODULE_SCALE.get(module, 1.0)
    k = meta['head_rect'][2] * s / (HEAD_CROP[2] - HEAD_CROP[0])

    cards, names = [], []
    for i, ((cx, top), player) in enumerate(zip(MODULES[module], players)):
        px, py, pw, ph = _rect((cx, top), meta['plates_rect'], s)
        hx, hy, hw, hh = _rect((cx, top), meta['head_rect'], s)
        lx, ly, lw, lh = _rect((cx, top), meta['label_rect'], s)
        cards.append(
            f'<img class="abs" src="{plates}" style="left:{px}px;top:{py}px;width:{pw}px;height:{ph}px">'
            f'<div class="head" style="left:{hx}px;top:{hy}px;width:{hw}px;height:{hh}px">'
            f'<img src="{data_uri(head_photo(player, kit))}" style="left:{-HEAD_CROP[0] * k}px;'
            f'top:{-HEAD_CROP[1] * k}px;width:{1254 * k}px;height:{1254 * k}px"></div>'
            f'<img class="abs" src="{label}" style="left:{lx}px;top:{ly}px;width:{lw}px;height:{lh}px">'
        )
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
        f'<div class="logo" style="left:{x}px;top:{y}px;width:{s}px;height:{s}px;background:{meta["logo_color"]};'
        f'--m:url({data_uri(team_logo(name, team_id))})"></div>'
        for (x, y, s), (name, team_id) in zip(meta['logos'], ((home_name, home_id), (away_name, away_id)))
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
{''.join(cards)}{logos}
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
