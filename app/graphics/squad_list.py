"""SQUAD LIST: sfondo e titolo delle pagine Canva 17 (Serie A), 18 (Coppa Italia), 19 (Europa League).

Champions League e Conference League non sono su Canva: stesso stile, con
sfondo e colori della competizione (vedi tools/canva_templates.py).

I giocatori sono in griglia per numero di maglia: numero grande (Dharma Gothic) solo contornato,
con un velo di colore dentro, che si dissolve verso il cognome sotto. Sul foglio una luce al centro
e i bordi più scuri; grana su tutta l'immagine.
"""
import math
import re

from graphics.common import (
    BASE_CSS, asset_dir, data_uri, esc, font_face, normalize, render_html, team_logo,
)

BACKGROUNDS = {
    'ita.1': 'squad_list_serie_a.png',
    'ita.coppa_italia': 'squad_list_coppa_italia.png',
    'uefa.europa': 'squad_list_europa_league.png',
    'uefa.champions': 'squad_list_champions_league.png',
    'uefa.europa.conf': 'squad_list_conference_league.png',
    'ita.super_cup': 'squad_list_supercoppa_italiana.png',
    'uefa.super_cup': 'squad_list_supercoppa_uefa.png',
    'fifa.cwc': 'squad_list_mondiale_per_club.png',
    'club.friendly': 'squad_list_amichevole.png',
}

# Titolo "squad list" (Allogist Italic, misure Canva), tutto minuscolo: "list" nel colore della competizione.
TITLE_SIZE, TITLE_BASE, TITLE_X = 206.7, 324.75, 540.0
TITLE_LIFT = 26          # titolo un po' più in alto del design Canva
TITLE_ACCENT = {
    'ita.1': '#ffffff', 'ita.coppa_italia': '#ffffff', 'uefa.europa': '#fa6c08',
    'uefa.champions': '#73aabf', 'uefa.europa.conf': '#11b913', 'club.friendly': '#d9dde3',
    'ita.super_cup': '#2ea8ff', 'uefa.super_cup': '#2f9bff', 'fifa.cwc': '#e2bc62',
}
# Numeri: colore della competizione, tranne dove sul foglio si leggerebbero poco (Conference: verde su verde).
NUMBER_COLOR = {**TITLE_ACCENT, 'uefa.europa.conf': '#ffffff'}
NO_LIGATURES = "font-variant-ligatures:none;font-feature-settings:'liga' 0,'clig' 0,'dlig' 0"

# Loghi come su Canva (pixel 1080x1440).
LOGO_Y, LOGO_SIZE = 1210.4, 94.67
OPACITY = 0.85  # testi e loghi su Canva hanno trasparenza 85%
LOGO_X = (453.3, 532.0)
# Foglio dello sfondo (per la luce) e griglia dei giocatori, tra il titolo e i loghi.
SHEET = (62, 126, 956, 1206)
GRID_LEFT, GRID_TOP, GRID_WIDTH, GRID_BOTTOM = 120, 368, 840, 248
CELL_MAX_H = 170

MAX_PLAYERS = 30
# "3 Bremer", "3. Bremer", "Bremer 3", "#3 Bremer"
LINE_RE = re.compile(r'^\s*(?:#?\s*(\d{1,2})(?:[\s.)\-–—:]+))?(.*?)(?:\s+[#(]?(\d{1,2})\)?)?\s*$')


def _known_numbers():
    """{nome normalizzato: numero}: rosa (nome, alias, cognome dell'etichetta) e numeri salvati."""
    try:
        import shirt_numbers
        from graphics.probabili import label_name
        from livescore.graphics import goal
        numbers = shirt_numbers.load()
        players = goal.load_players()
    except Exception:
        return {}
    known = {}
    for player in players:
        number = numbers.get(player.slug)
        if number:
            for name in [player.name, *player.aliases, label_name(player)]:
                known.setdefault(normalize(name), int(number))
    return known


def parse_squad(text):
    """[[nome, numero]] in ordine di numero di maglia; chi non ha numero va in fondo (alfabetico).
    Vince il numero scritto nella riga ("3 Bremer", come nei convocati di juventus.com); se manca,
    quello salvato per quel giocatore (data/shirt_numbers.json). Niente doppioni."""
    rows = {}
    known = None
    for line in str(text or '').splitlines():
        match = LINE_RE.match(line)
        name = ' '.join(re.sub(r'[\s#.\-–—()]+$|^[\s#.\-–—)]+', '', match.group(2)).split())
        if not name or name.endswith(':') or not re.search(r'[^\W\d_]', name):
            continue
        number = match.group(1) or match.group(3)
        if not number:
            known = _known_numbers() if known is None else known
            number = known.get(normalize(name))
        rows.setdefault(normalize(name), [name, int(number) if number else None])
    if not rows:
        raise ValueError('Elenco vuoto: incolla almeno un giocatore.')
    if len(rows) > MAX_PLAYERS:
        raise ValueError(f'Troppi giocatori ({len(rows)}): massimo {MAX_PLAYERS}.')
    return sorted(rows.values(), key=lambda r: (r[1] is None, r[1] or 0, normalize(r[0])))


def _columns(n):
    return 3 if n <= 12 else 4 if n <= 20 else 5


def _grid(players):
    """Griglia: righe bilanciate e centrate, le più lunghe in fondo (21 = 4-4-4-4-5)."""
    rows = [(p, None) if isinstance(p, str) else (p[0], p[1]) for p in players]
    n = len(rows)
    cols = _columns(n)
    lines = math.ceil(n / cols)
    height = 1440 - GRID_TOP - GRID_BOTTOM
    cell_h = min(height / lines, CELL_MAX_H)
    cell_w = GRID_WIDTH / cols
    number_size = min(cell_h, cell_w)                      # mai più largo della cella
    longest = max(len(name) for name, _ in rows)
    name_size = min(cell_h * .22, (cell_w - 14) / (longest * .41))   # cognomi tutti uguali, il più lungo ci sta
    sizes = [n // lines + (1 if i >= lines - n % lines else 0) for i in range(lines)]
    html, at = [], 0
    for k in sizes:
        html.append('<div class="row">' + ''.join(
            f'<div class="c"><b>{num if num else ""}</b><span>{esc(name)}</span></div>' for name, num in rows[at:at + k]) + '</div>')
        at += k
    fade = 'linear-gradient(180deg,#000 8%,rgba(0,0,0,.45) 45%,transparent 74%)'
    css = f'''.g{{position:absolute;left:{GRID_LEFT}px;top:{GRID_TOP}px;width:{GRID_WIDTH}px;height:{height}px;display:flex;flex-direction:column;justify-content:center}}
.row{{display:flex;justify-content:center}}
.c{{position:relative;width:{cell_w}px;height:{cell_h}px;display:flex;flex-direction:column;align-items:center;justify-content:flex-end;padding-bottom:{cell_h * .1}px}}
/* numero: contorno esterno + velo di colore (filtro #num), bagliore, si dissolve verso il cognome */
.c b{{position:absolute;left:0;right:0;bottom:{-cell_h * .04}px;text-align:center;font-family:'Dharma';font-weight:400;font-size:{number_size}px;line-height:1.15;
  color:var(--num);filter:url(#num) drop-shadow(0 0 12px rgba(255,255,255,.28));-webkit-mask:{fade};mask:{fade}}}
/* cognome in grassetto: il Bebas ha un solo peso, si ispessisce con un contorno dello stesso colore */
.c span{{position:relative;font-family:'Bebas Neue';font-size:{name_size}px;letter-spacing:.05em;color:#fff;white-space:nowrap;text-transform:uppercase;
  -webkit-text-stroke:{name_size * .045}px #fff;filter:drop-shadow(0 4px 6px rgba(0,0,0,.6))}}'''
    return ''.join(html), css


def build_html(*, players, competition, home_name, home_id, away_name, away_id, title_word='list', **_):
    # Le altre competizioni (Supercoppe, Mondiale per Club...) usano la grafica delle amichevoli.
    if competition not in BACKGROUNDS:
        competition = 'club.friendly'
    assets = asset_dir()
    grid, grid_css = _grid(players)
    accent = TITLE_ACCENT[competition]
    sx, sy, sw, sh = SHEET
    # Loghi nel colore della competizione (come "list"): sagoma del logo come maschera.
    logos = ''.join(
        f'<div class="abs logo" style="left:{x}px;top:{LOGO_Y}px;width:{LOGO_SIZE}px;height:{LOGO_SIZE}px;'
        f'--m:url({data_uri(team_logo(name, team_id))})"></div>'
        for x, (name, team_id) in zip(LOGO_X, ((home_name, home_id), (away_name, away_id)))
    )

    return f'''<!doctype html><html><head><meta charset="utf-8"><style>
{BASE_CSS}
{font_face('Bebas Neue', 'BebasNeue2014-Regular.ttf')}
@font-face{{font-family:'Dharma';src:url({data_uri(assets / 'fonts' / 'DharmaGothicEBold.otf')})}}
@font-face{{font-family:'Allogist';font-style:italic;src:url({data_uri(assets / 'fonts' / 'AllogistItalic.ttf')})}}
:root{{--num:{NUMBER_COLOR[competition]}}}
svg{{position:absolute;left:0;top:0}}
.logo{{opacity:{OPACITY};background:{accent};-webkit-mask:var(--m) center/100% 100% no-repeat;mask:var(--m) center/100% 100% no-repeat}}
/* luce dall'alto sul foglio e bordi più scuri: profondità */
.light{{position:absolute;left:{sx}px;top:{sy}px;width:{sw}px;height:{sh}px;pointer-events:none;
  background:radial-gradient(ellipse 70% 55% at 50% 40%,rgba(255,255,255,.10),transparent 70%),radial-gradient(ellipse at 50% 50%,transparent 55%,rgba(0,0,0,.35) 100%)}}
.grain{{mix-blend-mode:overlay;opacity:.32;pointer-events:none}}
{grid_css}
</style></head><body>
<svg width="0" height="0"><defs><filter id="num" x="-5%" y="-5%" width="110%" height="110%">
 <feMorphology in="SourceAlpha" operator="dilate" radius="2" result="d"/><feComposite in="d" in2="SourceAlpha" operator="out" result="o"/>
 <feFlood flood-color="{NUMBER_COLOR[competition]}"/><feComposite in2="o" operator="in" result="line"/>
 <feComponentTransfer in="SourceGraphic" result="soft"><feFuncA type="linear" slope=".3"/></feComponentTransfer>
 <feMerge><feMergeNode in="soft"/><feMergeNode in="line"/></feMerge></filter></defs></svg>
<img class="abs" src="{data_uri(assets / 'canva' / BACKGROUNDS[competition])}" style="left:0;top:0;width:1080px;height:1440px">
<div class="light"></div>
<svg width="1080" height="1440" viewBox="0 0 1080 1440"><text x="{TITLE_X}" y="{TITLE_BASE - TITLE_LIFT}" text-anchor="middle"
 font-family="Allogist" font-style="italic" font-size="{TITLE_SIZE}" style="{NO_LIGATURES}" fill="#fff" opacity="{OPACITY}">squad <tspan
 fill="{accent}">{esc(title_word)}</tspan></text></svg>
<div class="g">{grid}</div>{logos}
<svg class="grain" width="1080" height="1440" viewBox="0 0 1080 1440"><filter id="grain"><feTurbulence type="fractalNoise" baseFrequency=".9" numOctaves="2" seed="4" stitchTiles="stitch"/>
 <feColorMatrix type="saturate" values="0"/></filter><rect width="1080" height="1440" filter="url(#grain)"/></svg>
<script>window.__ready = document.fonts.ready.then(() => Promise.all([...document.images].map(i => i.decode().catch(() => {{}}))));</script>
</body></html>'''


def render(**kwargs):
    return render_html(build_html(**kwargs))
