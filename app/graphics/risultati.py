"""RISULTATI DELLA GIORNATA: Serie A, Champions, Europa e Conference League.

Stessa pagina della classifica (intestazione, colori, sfondi, font e logo JR di ogni
competizione): al posto della tabella ci sono le partite dell'ultima giornata
(data/classifica/risultati.html). 3:4 1920x2560 o storia IG 1920x3413.
"""
import json
import re
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import log
from graphics import classifica as cl
from graphics.common import render_html

_last = {}      # competizione -> ultimi risultati letti (per la didascalia e i doppioni)
FRAGMENT = Path(__file__).resolve().parent.parent / 'data' / 'classifica' / 'risultati.html'

READY = '''<script>
window.__ready = new Promise(r => setTimeout(r, 0))
  .then(() => Promise.all([...document.images].map(i => i.decode().catch(() => {}))))
  .then(() => {
    const broken = [...document.querySelectorAll('.t-logo img')].filter(i => !i.naturalWidth).length;
    const rows = document.querySelectorAll('#tableArea .m, #tableArea .card').length;
    if (broken || !rows) throw new Error(`Risultati incompleti: ${rows} partite, ${broken} loghi mancanti`);
  });
</script>'''

# Storia: righe più alte e testo più grande, come la classifica.
STORY_CSS = cl.STORY_CSS + '''
html.story .m .t-logo img{width:52px;height:52px;}
html.story .card .t-logo img{width:34px;height:34px;}
'''


def render(competition, story=False):
    """PNG dei risultati dell'ultima giornata (SA, UCL, UEL o UECL)."""
    import risultati_data
    data = risultati_data.fetch(competition)
    png = render_data(data, story)
    _last[data['competition']] = data
    return png


def render_data(data, story=False):
    data = json.loads(json.dumps(data))
    _embed_logos(data)
    html = build_html(data)
    if story:
        html = cl.story_html(html, STORY_CSS + cl.story_backgrounds('comp-'))
    try:
        png = render_html(html, page=cl.STORY_PAGE if story else cl.PAGE)
    except Exception as exc:  # noqa: BLE001 - errore della pagina -> messaggio leggibile
        if 'Risultati incompleti' in str(exc):
            raise ValueError('Risultati incompleti: alcuni loghi non si vedono. Riprova tra poco.') from exc
        raise
    return cl._texture(png, cl.TEXTURES.get(data['competition']), story)


def build_html(data):
    html = cl.TEMPLATE.read_text(encoding='utf-8')
    # Via lo script della classifica (l'ultimo <script> della pagina): lo sostituisce quello dei risultati.
    i = html.rindex('<script>')
    j = html.index('</script>', i) + len('</script>')
    fragment = FRAGMENT.read_text(encoding='utf-8')
    style = re.search(r'<style>.*?</style>', fragment, re.S).group(0)
    script = re.search(r'<script>.*?</script>', fragment, re.S).group(0)
    payload = json.dumps(data, ensure_ascii=False).replace('</', '<\\/')
    html = html[:i] + f'<script>window.__RISULTATI__ = {payload};</script>\n' + script + html[j:]
    html = html.replace('</head>', style + '\n</head>', 1)
    for name in cl.IMAGES:
        html = html.replace(name, cl._data_uri(cl.images_dir() / name))
    match = re.search(r'href="(https://fonts\.googleapis\.com/css2[^"]+)"', html)
    html = re.sub(r'<link[^>]+fonts\.(?:googleapis|gstatic)[^>]*>', '', html)
    fonts = cl._font_css(match.group(1)) if match else ''
    if fonts:
        html = html.replace('<head>', f'<head>\n<style>\n{fonts}\n</style>', 1)
    return html.replace('</body>', READY + '\n</body>', 1)


def _embed_logos(data):
    """Tutti gli stemmi dentro la pagina: se uno non si scarica, niente grafica a metà."""
    partite = data.get('partite', [])
    if not partite:
        raise ValueError('Nessuna partita in questa giornata.')
    urls = sorted({p[f] for p in partite for f in ('home_logo', 'away_logo') if p.get(f)})
    with ThreadPoolExecutor(max_workers=min(8, len(urls) or 1)) as pool:
        jobs = {url: pool.submit(cl._logo, url) for url in urls}
    found, errors = {}, []
    for url, job in jobs.items():
        try:
            found[url] = job.result()
        except Exception as exc:  # noqa: BLE001 - si riassume sotto
            errors.append(f'{url}: {exc}')
    if errors:
        log.warn('DATI', 'Loghi risultati non scaricati:\n' + '\n'.join(errors))
        raise ValueError(f'Non riesco a scaricare {len(errors)} stemmi. Riprova tra poco.')
    for p in partite:
        for f in ('home_logo', 'away_logo'):
            if p.get(f):
                p[f] = found[p[f]]
