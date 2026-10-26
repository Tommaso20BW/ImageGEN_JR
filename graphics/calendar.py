"""CALENDARIO del mese (pagina 24): titolo del mese e da 1 a 9 partite.

Regole (dai post pubblicati):
  - titolo: prima parte nera, seconda oro ("nove|mbre"); più grande se le
    partite sono poche, sempre limitato dalla larghezza della parola;
  - righe (giorno a due cifre, barretta, due loghi, linea dorata): occupano
    tutto lo spazio sotto il titolo, crescono se sono poche e si
    rimpiccioliscono se sono tante;
  - giorni sempre a due cifre ("05"): colonna dei numeri e barretta restano
    nello stesso punto in ogni mese e il gruppo è centrato come su Canva.
"""
import calendar as cal
import json
from functools import lru_cache

from graphics.common import DESIGN_H, DESIGN_W, asset_dir, data_uri, esc, render_html, team_logo

MONTHS = ('gennaio', 'febbraio', 'marzo', 'aprile', 'maggio', 'giugno', 'luglio',
          'agosto', 'settembre', 'ottobre', 'novembre', 'dicembre')
# Parte nera del titolo (il resto è oro): per sillabe, come "nove|mbre" su Canva.
SPLIT = {'gennaio': 'genn', 'febbraio': 'febb', 'marzo': 'mar', 'aprile': 'apr', 'maggio': 'mag',
         'giugno': 'giu', 'luglio': 'lug', 'agosto': 'ago', 'settembre': 'sette', 'ottobre': 'otto',
         'novembre': 'nove', 'dicembre': 'dice'}
MAX_ROWS = 9

# Titolo. Su Canva "novembre" è 236 px con 7 partite e largo ~952 px.
TITLE_SIZE = 236.02
TITLE_MAX_W = 930          # larghezza massima della parola
TITLE_GROW = 0.35          # +35% di grandezza per ogni partita in meno di 7
TITLE_MAX_SIZE = 236.02 * 1.9
TITLE_BASE = 258           # base delle lettere nei post pubblicati
TITLE_LOW = 300            # le lettere che scendono (g) non vanno oltre
TITLE_TOP_MIN = 40         # margine sopra le lettere più alte
TITLE_GAP = 53             # dalla base del titolo all'inizio delle righe (come su Canva)
# Nei post pubblicati le lettere sono quelle normali: le legature del font
# ("tt", "st", "et"... con riccioli e svolazzi) restano spente.
FONT_FEATURES = "font-variant-ligatures:none;font-feature-settings:'liga' 0,'clig' 0,'dlig' 0"

# Righe (misure Canva, scala 1).
DAY_RIGHT = 446.58
LOGO_RIGHT = 771.7
GROUP_X = (319.46 + LOGO_RIGHT) / 2   # centro del gruppo numero (2 cifre) -> logo destro
ROW_UP, ROW_DOWN = 102.64, 39.0       # ingombro sopra / sotto la linea di base
ROWS_BOTTOM = 1354.39 + ROW_DOWN      # fondo della zona righe (ultima linea Canva)
MAX_GROW = 1.45                       # numeri, loghi e barretta crescono al massimo così (da 4 partite)
FEW_GROW = {1: 2.1, 2: 1.9, 3: 1.7}   # con pochissime partite possono crescere di più
FILL = 0.92                           # quota dello spazio occupata dalle righe
MAX_GAP = 1.06                        # passo massimo rispetto all'altezza della riga
LINE_MAX_W = 1040                     # la linea dorata non supera questa larghezza


def _font(size):
    from PIL import ImageFont
    return ImageFont.truetype(str(asset_dir() / 'fonts' / 'AllogistItalic.ttf'), max(1, round(size * 4)))


def _ink(text, size):
    """(larghezza, sopra la base, sotto la base) dell'inchiostro, in pixel design."""
    x0, y0, x1, y1 = _font(size).getbbox(text, anchor='ls')
    return (x1 - x0) / 4, -y0 / 4, y1 / 4


def _number_width(text, size):
    return _font(size).getlength(text) / 4


@lru_cache(maxsize=1)
def _meta():
    return json.loads((asset_dir() / 'canva' / 'calendar.json').read_text(encoding='utf-8'))


def parse_matches(month, year, rows):
    """rows: [{'day': 5, 'opponent': {...}, 'side': 'home'|'away'}] -> ordinate per giorno."""
    if not 1 <= int(month) <= 12:
        raise ValueError('Mese non valido.')
    if not isinstance(rows, list) or not 1 <= len(rows) <= MAX_ROWS:
        raise ValueError(f'Da 1 a {MAX_ROWS} partite.')
    last = cal.monthrange(int(year), int(month))[1]
    out = []
    for row in rows:
        try:
            day = int(row.get('day'))
        except (TypeError, ValueError, AttributeError):
            raise ValueError('Giorno non valido.') from None
        if not 1 <= day <= last:
            raise ValueError(f'Il giorno {day} non esiste in {MONTHS[int(month) - 1]}.')
        if row.get('side') not in ('home', 'away'):
            raise ValueError('Casa/trasferta non valido.')
        out.append({'day': day, 'side': row['side'], 'opponent': row.get('opponent')})
    return sorted(out, key=lambda r: r['day'])


def title_layout(word, n):
    """Grandezza e linea di base del titolo per questo mese e numero di partite."""
    grow = 1 + TITLE_GROW * (7 - n) if n < 7 else 7 / n
    width_at_base, _up, _down = _ink(word, TITLE_SIZE)
    size = min(TITLE_SIZE * grow, TITLE_SIZE * TITLE_MAX_W / width_at_base, TITLE_MAX_SIZE)
    _w, up, down = _ink(word, size)
    base = max(min(TITLE_BASE, TITLE_LOW - max(0, down)), TITLE_TOP_MIN + up)
    return size, base, base + max(0, down)


def layout(n, rows_top):
    """Linea di base e scala di ogni riga nello spazio fra rows_top e il fondo."""
    step = 164.36                                    # passo Canva fra le righe
    room = ROWS_BOTTOM - rows_top
    scale = min(FEW_GROW.get(n, MAX_GROW), FILL * room / (n * step))
    pitch = min(room / n, step * scale * MAX_GAP)
    middle = (rows_top + ROWS_BOTTOM) / 2 + (ROW_UP - ROW_DOWN) / 2 * scale
    return [(middle + (k - (n - 1) / 2) * pitch, scale) for k in range(n)]


def _pattern(pid, file, rect):
    x, y, w, h = rect
    return (f'<pattern id="{pid}" patternUnits="userSpaceOnUse" x="{x}" y="{y}" width="{w}" height="{h}">'
            f'<image href="{data_uri(asset_dir() / "canva" / file)}" width="{w}" height="{h}" '
            f'preserveAspectRatio="none"/></pattern>')


def build_html(*, month, matches, **_):
    meta = _meta()
    title = meta['title']
    word = MONTHS[int(month) - 1]
    half = len(SPLIT[word])
    canva = asset_dir() / 'canva'
    deco = meta['row']
    deco_uri = data_uri(canva / deco['file'])
    size = meta['logo_size']
    n = len(matches)

    # Titolo: la texture oro segue grandezza e posizione della scritta.
    t_size, t_base, t_bottom = title_layout(word, n)
    k = t_size / title['size']
    x, y, w, h = title['ink_rect']
    cx, b0 = title['center'], title['base']
    ink_rect = (cx + (x - cx) * k, t_base + (y - b0) * k, w * k, h * k)
    defs = [_pattern('gold', title['ink'], ink_rect)]
    body = [f'<text x="{cx}" y="{t_base}" text-anchor="middle" font-family="Allogist" '
            f'font-style="italic" font-size="{t_size}" style="{FONT_FEATURES}"><tspan fill="{title["color"]}">{esc(word[:half])}</tspan>'
            f'<tspan fill="url(#gold)">{esc(word[half:])}</tspan></text>']

    # Righe: giorni a due cifre, gruppo centrato sul numero più largo del mese.
    days = [f'{m["day"]:02d}' for m in matches]
    widest = max(_number_width(d, meta['rows'][0]['size']) for d in days)
    pivot = (DAY_RIGHT - widest + LOGO_RIGHT) / 2
    rows_top = max(t_base, t_bottom - 20) + TITLE_GAP

    logo_ids = {}
    for k_row, ((base, scale), match, day) in enumerate(zip(layout(n, rows_top), matches, days)):
        ref = meta['rows'][k_row % len(meta['rows'])]          # texture e misure della riga Canva
        r0 = ref['base']
        defs.append(_pattern(f'd{k_row}', ref['ink'], ref['ink_rect']))
        juve = ('Juventus', '111')
        opp = (match['opponent']['name'], match['opponent'].get('id', ''))
        pair = (juve, opp) if match['side'] == 'home' else (opp, juve)
        logos = []
        for lx, (name, team_id) in zip(meta['logo_x'], pair):
            if name not in logo_ids:
                logo_ids[name] = f'l{len(logo_ids)}'
                defs.append(f'<mask id="{logo_ids[name]}" mask-type="alpha" maskContentUnits="objectBoundingBox">'
                            f'<image href="{data_uri(team_logo(name, team_id))}" width="1" height="1" '
                            f'preserveAspectRatio="none"/></mask>')
            logos.append(f'<rect x="{lx}" y="{ref["logo_top"]}" width="{size}" height="{size}" '
                         f'fill="{meta["logo_color"]}" mask="url(#{logo_ids[name]})"/>')

        # Barretta in scala con la riga; linea dorata allungata solo fin dove c'è spazio.
        deco_img = (f'<image href="{deco_uri}" x="{deco["x"]}" y="{r0 + deco["dy"]}" width="{deco["w"]}" '
                    f'height="{deco["h"]}" preserveAspectRatio="none"')
        cut = r0 + deco['dy'] + deco['h'] - 10
        line_sx = min(scale, LINE_MAX_W / deco['w'])
        line_x = deco['x'] + deco['w'] / 2
        defs.append(f'<clipPath id="line{k_row}"><rect x="0" y="{cut}" width="{DESIGN_W}" height="20"/></clipPath>'
                    f'<clipPath id="bar{k_row}"><rect x="0" y="0" width="{DESIGN_W}" height="{cut}"/></clipPath>')
        body.append(
            f'<g transform="translate({line_x} {base}) scale({line_sx} {scale}) translate({-line_x} {-r0})">'
            f'{deco_img} clip-path="url(#line{k_row})"/></g>'
            f'<g transform="translate({GROUP_X} {base}) scale({scale}) translate({-pivot} {-r0})">'
            f'{deco_img} clip-path="url(#bar{k_row})"/>'
            f'<text x="{DAY_RIGHT}" y="{r0}" text-anchor="end" font-family="Allogist" font-style="italic" '
            f'style="{FONT_FEATURES}" font-size="{ref["size"]}" fill="url(#d{k_row})">{day}</text>{"".join(logos)}</g>'
        )

    return f'''<!doctype html><html><head><meta charset="utf-8"><style>
*{{margin:0;padding:0}}
html,body{{width:{DESIGN_W}px;height:{DESIGN_H}px;overflow:hidden;background:#fff}}
@font-face{{font-family:'Allogist';font-style:italic;src:url({data_uri(asset_dir() / 'fonts' / 'AllogistItalic.ttf')})}}
svg{{position:absolute;left:0;top:0}}
</style></head><body>
<img src="{data_uri(canva / meta['bg'])}" style="position:absolute;left:0;top:0;width:{DESIGN_W}px;height:{DESIGN_H}px">
<svg width="{DESIGN_W}" height="{DESIGN_H}" viewBox="0 0 {DESIGN_W} {DESIGN_H}"><defs>{''.join(defs)}</defs>{''.join(body)}</svg>
</body></html>'''


def render(**kwargs):
    return render_html(build_html(**kwargs))
