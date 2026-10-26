"""CALENDARIO del mese (pagina 24): titolo del mese e da 1 a 9 partite.

Regole (dai post pubblicati):
  - titolo: prima parte nera, seconda oro ("nove|mbre"); stessa grandezza e
    stessa linea di base in tutti i mesi (quelle di Canva), così ogni mese ha
    lo stesso aspetto e le righe partono sempre dallo stesso punto;
  - righe (giorno a due cifre, barretta, due loghi, linea dorata): occupano
    lo spazio sotto il titolo; da TWO_COLS partite vanno su due colonne
    (prima la sinistra, dall'alto), così non diventano minuscole;
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
MAX_ROWS = 14

# Titolo. Su Canva "novembre" è 236 px con 7 partite e largo ~952 px.
TITLE_SIZE = 236.02
TITLE_BASE = 258           # base delle lettere nei post pubblicati (a grandezza Canva)
TITLE_TOP = TITLE_BASE - 150   # dove arrivano le lettere più alte: fisso per ogni grandezza
TITLE_GAP = 53             # dalla base del titolo all'inizio delle righe (come su Canva)
TITLE_MAX_W = 930          # il titolo non supera questa larghezza
TITLE_K = (0.6, 1.7)       # grandezza del titolo rispetto a Canva: minima e massima
ROWS_VS_TITLE = 0.95       # le righe non diventano più piccole del titolo (in proporzione)
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
BLOCK_UP = 0.38                       # quota dello spazio avanzato messa sopra le righe
TWO_COLS = 11                         # da 11 partite in su: due colonne
COL_CENTERS = (276, 804)              # centro del gruppo numero+loghi nelle due colonne
COL_SCALE = 1.08                      # massima scala in due colonne (larghezza mezza pagina)
COL_LINE_W = 490                      # linea dorata in due colonne
COL_GAP = 1.3                         # in due colonne le righe si allargano di più in altezza


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


@lru_cache(maxsize=1)
def _title_box():
    """(sopra, sotto la base) più grandi fra tutti i mesi, a grandezza Canva."""
    inks = [_ink(word, TITLE_SIZE) for word in MONTHS]
    return max(up for _w, up, _d in inks), max(max(0, down) for _w, _u, down in inks)


def _title_at(k):
    """(grandezza, base, fondo, inizio righe) col titolo a k volte la grandezza Canva."""
    up, down = _title_box()
    base = TITLE_TOP + up * k
    bottom = base + down * k
    return TITLE_SIZE * k, base, bottom, max(base, bottom - 20) + max(36, TITLE_GAP * k)


def title_layout(word, n):
    """Titolo e righe si dividono la pagina, nelle proporzioni di Canva.

    Il titolo è il più grande possibile finché le righe restano grandi almeno
    quanto lui (in proporzione): con poche partite cresce fino a riempire la
    larghezza, con tante si rimpicciolisce insieme alle righe.
    Ritorna (grandezza, base, fondo, inizio righe)."""
    width_at_canva, _u, _d = _ink(word, TITLE_SIZE)
    k_max = min(TITLE_MAX_W / width_at_canva, TITLE_K[1])
    k = k_max
    while k > TITLE_K[0]:
        rows_top = _title_at(k)[3]
        if layout(n, rows_top)[0][2] >= k * ROWS_VS_TITLE:
            break
        k -= 0.01
    return _title_at(max(k, TITLE_K[0]))


def _column(n, rows_top, max_scale, gap=MAX_GAP):
    step = 164.36                                    # passo Canva fra le righe
    room = ROWS_BOTTOM - rows_top
    scale = min(max_scale, FILL * room / (n * step))
    pitch = min(room / n, step * scale * gap)
    # Spazio avanzato: un po' più sotto che sopra, così le righe restano vicine al mese.
    middle = rows_top + (room - pitch * n) * BLOCK_UP + pitch * n / 2 + (ROW_UP - ROW_DOWN) / 2 * scale
    return [middle + (k - (n - 1) / 2) * pitch for k in range(n)], scale


def layout(n, rows_top):
    """[(centro x, linea di base, scala, larghezza max linea)] di ogni riga."""
    if n < TWO_COLS:
        bases, scale = _column(n, rows_top, FEW_GROW.get(n, MAX_GROW))
        return [(GROUP_X, b, scale, LINE_MAX_W) for b in bases]
    left = (n + 1) // 2
    bases, scale = _column(left, rows_top, COL_SCALE, COL_GAP)
    return [(COL_CENTERS[k >= left], bases[k if k < left else k - left], scale, COL_LINE_W)
            for k in range(n)]


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
    t_size, t_base, t_bottom, rows_top = title_layout(word, n)
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

    logo_ids = {}
    for k_row, ((gx, base, scale, line_w), match, day) in enumerate(zip(layout(n, rows_top), matches, days)):
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
        line_sx = min(scale, line_w / deco['w'])
        line_x = deco['x'] + deco['w'] / 2
        shift = gx - GROUP_X                                    # colonna: tutto spostato in orizzontale
        defs.append(f'<clipPath id="line{k_row}"><rect x="0" y="{cut}" width="{DESIGN_W}" height="20"/></clipPath>'
                    f'<clipPath id="bar{k_row}"><rect x="0" y="0" width="{DESIGN_W}" height="{cut}"/></clipPath>')
        body.append(
            f'<g transform="translate({line_x + shift} {base}) scale({line_sx} {scale}) translate({-line_x} {-r0})">'
            f'{deco_img} clip-path="url(#line{k_row})"/></g>'
            f'<g transform="translate({gx} {base}) scale({scale}) translate({-pivot} {-r0})">'
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
