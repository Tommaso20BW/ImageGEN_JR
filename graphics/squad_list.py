"""SQUAD LIST: pagine 17 (Serie A), 18 (Coppa Italia), 19 (Europa League).

Champions League e Conference League non sono su Canva: stesso stile, con
sfondo e colori della competizione (vedi tools/canva_templates.py).
"""
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
}

# Titolo "squad List" (Allogist Italic, misure Canva): "List" nel colore della competizione.
TITLE_SIZE, TITLE_BASE, TITLE_X = 206.7, 324.75, 540.0
TITLE_ACCENT = {
    'ita.1': '#ffffff', 'ita.coppa_italia': '#ffffff', 'uefa.europa': '#fa6c08',
    'uefa.champions': '#73aabf', 'uefa.europa.conf': '#11b913',
}
NO_LIGATURES = "font-variant-ligatures:none;font-feature-settings:'liga' 0,'clig' 0,'dlig' 0"

# Misure prese dal design Canva (pixel 1080x1440).
LEFT_X, RIGHT_X, COL_W = 214, 541, 323
ROW_H, CENTER_Y = 70, 787
FONT_SIZE, LETTER_SPACING = 61.0211, -2.13574
LOGO_Y, LOGO_SIZE = 1210.4, 94.67
OPACITY = 0.85  # testi e loghi su Canva hanno trasparenza 85%
LOGO_X = (453.3, 532.0)

MAX_PLAYERS = 30
# Area utile della lista, misurata sul render: dal punto piu' basso del titolo (coda della "q",
# baseline + ~24px) all'inizio visibile dei loghi (il file logo ha ~5.5px di margine interno).
# Le maiuscole occupano solo parte della riga: partono a CAP_TOP e sono alte CAP_H (in frazione
# dell'altezza riga), quindi si centra l'inchiostro del testo, non il box delle righe.
TITLE_BOTTOM, LOGOS_TOP = 349.0, 1216.0
CAP_TOP, CAP_H = 0.0786, 0.607
MIN_GAP = 27.0  # spazio minimo sopra/sotto: quello del design a 12 righe


def parse_squad(text):
    """Toglie numeri e simboli, ordina in ordine alfabetico, elimina doppioni."""
    names = {}
    for line in str(text or '').splitlines():
        name = re.sub(r'^[\s\d#.\-–—)]+|[\s\d#.\-–—(]+$', '', line).strip()
        name = ' '.join(name.split())
        if not name or name.endswith(':'):
            continue
        names.setdefault(normalize(name), name)
    if not names:
        raise ValueError('Elenco vuoto: incolla almeno un giocatore.')
    if len(names) > MAX_PLAYERS:
        raise ValueError(f'Troppi giocatori ({len(names)}): massimo {MAX_PLAYERS}.')
    return [names[key] for key in sorted(names)]


def columns(players):
    """Sinistra con un giocatore in più se sono dispari."""
    half = (len(players) + 1) // 2
    return players[:half], players[half:]


def build_html(*, players, competition, home_name, home_id, away_name, away_id, title_word='List', **_):
    if competition not in BACKGROUNDS:
        raise ValueError('Squad List disponibile per Serie A, Coppa Italia, Champions, Europa e Conference League.')
    assets = asset_dir()
    left, right = columns(players)
    n = max(len(left), 1)
    window = LOGOS_TOP - TITLE_BOTTOM
    # Altezza riga: 70 (design) finche' c'e' spazio, poi si restringe per tenere MIN_GAP sopra e sotto.
    row_h = min(ROW_H, (window - 2 * MIN_GAP) / (n - 1 + CAP_H))
    scale = row_h / ROW_H
    font_size = FONT_SIZE * scale
    letter_spacing = LETTER_SPACING * scale
    ink_h = (n - 1 + CAP_H) * row_h
    ink_top = TITLE_BOTTOM + (window - ink_h) / 2  # stesso spazio sopra (q) e sotto (loghi)
    top = ink_top - CAP_TOP * row_h

    def column(names, x, align):
        rows = ''.join(f'<p>{esc(n)}</p>' for n in names)
        return f'<div class="col abs" style="left:{x}px;top:{top}px;text-align:{align}">{rows}</div>'

    logos = ''.join(
        f'<img class="abs white logo" src="{data_uri(team_logo(name, team_id))}" '
        f'style="left:{x}px;top:{LOGO_Y}px;width:{LOGO_SIZE}px;height:{LOGO_SIZE}px">'
        for x, (name, team_id) in zip(LOGO_X, ((home_name, home_id), (away_name, away_id)))
    )

    return f'''<!doctype html><html><head><meta charset="utf-8"><style>
{BASE_CSS}
{font_face('Bebas Neue', 'BebasNeue2014-Regular.ttf')}
.col{{width:{COL_W}px;font-family:'Bebas Neue';font-size:{font_size}px;
letter-spacing:{letter_spacing}px;line-height:{row_h}px;color:#fff;text-transform:uppercase;white-space:nowrap;opacity:{OPACITY}}}
.logo{{opacity:{OPACITY}}}
@font-face{{font-family:'Allogist';font-style:italic;src:url({data_uri(assets / 'fonts' / 'AllogistItalic.ttf')})}}
svg{{position:absolute;left:0;top:0}}
</style></head><body>
<img class="abs" src="{data_uri(assets / 'canva' / BACKGROUNDS[competition])}" style="left:0;top:0;width:1080px;height:1440px">
<svg width="1080" height="1440" viewBox="0 0 1080 1440"><text x="{TITLE_X}" y="{TITLE_BASE}" text-anchor="middle"
 font-family="Allogist" font-style="italic" font-size="{TITLE_SIZE}" style="{NO_LIGATURES}" fill="#fff" opacity="{OPACITY}">squad <tspan
 fill="{TITLE_ACCENT[competition]}">{esc(title_word)}</tspan></text></svg>
{column(left, LEFT_X, 'left')}{column(right, RIGHT_X, 'right')}{logos}
</body></html>'''


def render(**kwargs):
    return render_html(build_html(**kwargs))
