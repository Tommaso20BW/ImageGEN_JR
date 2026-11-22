"""TABELLONE: fase a eliminazione diretta di Coppa Italia, Champions, Europa e Conference League.

Stessa intestazione, colori, font, sfondi e texture della classifica (graphics/classifica.py),
pagina data/classifica/tabellone.html (900x1200, uscita 1920x2560). Coppa Italia usa lo stile
della Serie A.
"""
import json
import re
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from graphics.classifica import (IMAGES, PAGE, STORY_PAD_BOTTOM, STORY_PAD_TOP, STORY_PAGE, TEXTURES, _data_uri,
                                 _font_css, _logo, _texture, images_dir, story_backgrounds, story_html)
from graphics.common import render_html

_last = {}      # competizione -> ultimo tabellone letto (per riconoscere i doppioni)
TEMPLATE = Path(__file__).resolve().parent.parent / 'data' / 'classifica' / 'tabellone.html'
# Storia IG (900x1600): intestazione e pannello fra le zone di Instagram, il tabellone si allunga.
STORY_CSS = f'''html.story,html.story body{{height:{STORY_PAGE[1]}px;}}
html.story{{font-size:17px;}}
html.story .header{{top:{STORY_PAD_TOP}px;}}
html.story #panel{{top:{136 + STORY_PAD_TOP}px;bottom:{STORY_PAD_BOTTOM}px;}}
'''

READY = '''<script>
window.__ready = new Promise(r => setTimeout(r, 0))
  .then(() => window.__align)
  .then(() => Promise.all([...document.images].map(i => i.decode().catch(() => {}))))
  .then(() => {
    const broken = [...document.querySelectorAll('.box img')].filter(i => !i.naturalWidth).length;
    if (broken) throw new Error(`Tabellone incompleto: ${broken} loghi mancanti`);
  });
</script>'''


def render(competition, story=False):
    """PNG 1920x2560 del tabellone aggiornato (CI, UCL, UEL o UECL); story=True: storia IG 1920x3413."""
    import tabellone_data
    data = tabellone_data.fetch(competition)
    png = render_data(data, story)
    _last[data['competition']] = data
    return png


def render_data(data, story=False):
    data = json.loads(json.dumps(data))
    teams = [t for r in data['rounds'] for c in r['cells'] for t in c['teams'] if t and t.get('logo')]
    urls = sorted({t['logo'] for t in teams})
    with ThreadPoolExecutor(max_workers=max(1, min(8, len(urls)))) as pool:
        found = dict(zip(urls, pool.map(_logo, urls)))
    for t in teams:
        t['logo'] = found[t['logo']]
    html = build_html(data)
    if story:
        html = story_html(html, STORY_CSS + story_backgrounds('th-'))
    try:
        png = render_html(html, page=STORY_PAGE if story else PAGE)
    except Exception as exc:  # noqa: BLE001 - errore della pagina -> messaggio leggibile
        if 'Tabellone incompleto' in str(exc):
            raise ValueError('Tabellone incompleto: alcuni loghi non si vedono. Riprova tra poco.') from exc
        raise
    theme = data.get('theme') or data['competition']
    return _texture(png, 'texture_white.png' if theme == 'CI' else TEXTURES.get(theme), story)


def build_html(data):
    html = TEMPLATE.read_text(encoding='utf-8')
    for name in IMAGES + ('coppa-italia-mark.png',):
        if name in html:
            html = html.replace(name, _data_uri(images_dir() / name))
    match = re.search(r'href="(https://fonts\.googleapis\.com/css2[^"]+)"', html)
    html = re.sub(r'<link[^>]+fonts\.(?:googleapis|gstatic)[^>]*>', '', html)
    fonts = _font_css(match.group(1)) if match else ''
    if fonts:
        html = html.replace('<head>', f'<head>\n<style>\n{fonts}\n</style>', 1)
    payload = json.dumps(data, ensure_ascii=False).replace('</', '<\\/')
    html = html.replace('<body>', f'<body>\n<script>window.__TABELLONE__ = {payload};</script>', 1)
    return html.replace('</body>', READY + '\n</body>', 1)
