"""MATCHDAY: pagine 2 (home), 7 (away), 12 (third).

Livelli dal basso: foto caricata dall'utente, livello fisso Canva (sfumature,
grana, titolo "matchday", JR), loghi casa/trasferta in alto a sinistra e la
riga info in basso: STADIO | COMPETIZIONE | ORARIO CET | DATA.
"""
import base64
import json
import re
from datetime import date
from functools import lru_cache

from constants import COMPETITIONS
from graphics.common import photo_layer, DESIGN_H, DESIGN_W, asset_dir, data_uri, esc, render_html, team_logo
from graphics.starting_xi import KITS, check_photo, photo_box

# Misure dal PDF Canva (pixel 1080x1440).
LOGO_BOXES = ((7.0, 9.31), (7.0, 143.28))   # casa sopra, trasferta sotto
LOGO_SIZE = 133.97
INFO_BASE, INFO_SIZE = 1415.11, 20
SLOTS = ('stadium', 'competition', 'time', 'date')
SEPARATORS = ('sep1', 'sep2', 'sep3')
CENTERS = {'stadium': 132.87, 'sep1': 270.31, 'competition': 404.18, 'sep2': 542.31,
           'time': 674.18, 'sep3': 816.31, 'date': 948.43}

MONTHS = ('GENNAIO', 'FEBBRAIO', 'MARZO', 'APRILE', 'MAGGIO', 'GIUGNO', 'LUGLIO',
          'AGOSTO', 'SETTEMBRE', 'OTTOBRE', 'NOVEMBRE', 'DICEMBRE')
MAX_STADIUM = 28


@lru_cache(maxsize=1)
def _meta():
    return json.loads((asset_dir() / 'canva' / 'matchday.json').read_text(encoding='utf-8'))


def competition_label(code):
    return dict((v, k) for k, v in COMPETITIONS)[code].upper()


def parse_info(stadium, kickoff, day):
    """Valida stadio, orario (HH:MM) e data (AAAA-MM-GG) dalla Mini App."""
    stadium = ' '.join(str(stadium or '').split()).upper()
    if not stadium:
        raise ValueError('Scrivi lo stadio.')
    if len(stadium) > MAX_STADIUM:
        raise ValueError(f'Nome stadio troppo lungo (max {MAX_STADIUM} caratteri).')
    match = re.fullmatch(r'([01]?\d|2[0-3])[:.]([0-5]\d)', str(kickoff or '').strip())
    if not match:
        raise ValueError('Orario non valido (es. 20:45).')
    try:
        day = date.fromisoformat(str(day or ''))
    except ValueError:
        raise ValueError('Data non valida.') from None
    return {
        'stadium': stadium,
        'time': f'{int(match[1]):02d}:{match[2]} CET',
        'date': f'{day.day} {MONTHS[day.month - 1]} {day.year}',
    }


def _info_text(slot, value, style):
    text = (f'<text x="{CENTERS[slot]}" y="{INFO_BASE}" text-anchor="middle" '
            f'font-family="Matchday Info" font-size="{INFO_SIZE}">{esc(value)}</text>')
    if 'file' in style:
        return (f'<clipPath id="c_{slot}">{text}</clipPath>'
                f'<image href="{data_uri(asset_dir() / "canva" / style["file"])}" x="{style["x"]}" '
                f'y="{style["y"]}" width="{style["w"]}" height="{style["h"]}" '
                f'preserveAspectRatio="none" clip-path="url(#c_{slot})"/>')
    return text.replace('<text ', f'<text fill="{style["color"]}" ', 1)


def build_html(*, kit, photo, frame, info, competition, home_name, home_id, away_name, away_id, **_):
    if kit not in KITS:
        raise ValueError('Maglia non valida.')
    meta = _meta()[kit]
    canva = asset_dir() / 'canva'
    photo_html, page_bg = photo_layer(photo, frame)

    values = {**info, 'competition': competition_label(competition)}
    texts = ''.join(_info_text(slot, values[slot], meta['info'][slot]) for slot in SLOTS)
    texts += ''.join(_info_text(slot, '|', meta['info'][slot]) for slot in SEPARATORS)
    logos = ''.join(
        f'<div class="logo" style="left:{x}px;top:{y}px;background:{meta["logo_color"]};'
        f'--m:url({data_uri(team_logo(name, team_id))})"></div>'
        for (x, y), (name, team_id) in zip(LOGO_BOXES, ((home_name, home_id), (away_name, away_id)))
    )

    return f'''<!doctype html><html><head><meta charset="utf-8"><style>
*{{margin:0;padding:0;box-sizing:border-box}}
html,body{{width:{DESIGN_W}px;height:{DESIGN_H}px;overflow:hidden;background:{page_bg}}}
.abs{{position:absolute}}
.logo{{position:absolute;width:{LOGO_SIZE}px;height:{LOGO_SIZE}px;
-webkit-mask:var(--m) center/100% 100% no-repeat;mask:var(--m) center/100% 100% no-repeat}}
@font-face{{font-family:'Matchday Info';src:url({data_uri(asset_dir() / 'fonts' / 'MatchdayInfo.ttf')})}}
svg{{position:absolute;left:0;top:0}}
</style></head><body>
{photo_html}
<img class="abs" src="{data_uri(canva / meta['overlay'])}" style="left:0;top:0;width:{DESIGN_W}px;height:{DESIGN_H}px">
{logos}
<svg width="{DESIGN_W}" height="{DESIGN_H}" viewBox="0 0 {DESIGN_W} {DESIGN_H}">{texts}</svg>
</body></html>'''


def render(ghost=False, **kwargs):
    if ghost:
        kwargs['photo'] = None
    return render_html(build_html(**kwargs), ghost=ghost)
