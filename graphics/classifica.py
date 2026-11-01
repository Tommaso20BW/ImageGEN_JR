"""CLASSIFICA: Serie A, Champions, Europa e Conference League (dal vecchio bot Classifica_JR).

La pagina è la stessa del vecchio bot (data/classifica/template.html, 900x1200): qui
si incorporano dati, loghi, immagini e font, così il browser non scarica niente
durante lo scatto. Uscita 1920x2560 con la texture sopra, come prima.
"""
import base64
import io
import json
import re
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import requests
from PIL import Image

from graphics.common import render_html

DIR = Path(__file__).resolve().parent.parent / 'data' / 'classifica'
PAGE = (900, 1200)

# Serie A e UCL: texture bianca; UEL e UECL: nera.
TEXTURES = {'SA': 'texture_white.png', 'UCL': 'texture_white.png',
            'UEL': 'texture_black.png', 'UECL': 'texture_black.png'}
IMAGES = ('bg-ucl.png', 'bg-uel.png', 'bg-uecl.png',
          'serie-a-scudetto.png', 'ucl-mark.png', 'uel-mark.png', 'uecl-mark.png')

UA = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
      '(KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36')
LOGO_HEADERS = {'User-Agent': UA,
                'Accept': 'image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8'}

# Loghi personalizzati (Juventus bianco, Roma): copia nel repository, niente download.
CUSTOM_LOGOS = {
    'https://upload.wikimedia.org/wikipedia/commons/9/99/Juventus_FC_2017_squared_icon_%28white%29.png':
        'juventus-custom.png.b64',
    'https://assets.football-logos.cc/logos/italy/512x512/roma.8dfa8968.png': 'roma-custom.png.b64',
}

# Durante una sessione loghi e font restano in memoria: la seconda classifica è più veloce.
_logos = {}
_last = {}      # competizione -> ultima classifica letta (per l'elenco dell'anteprima)
_fonts = {}

# Pronto quando tutte le immagini sono caricate; errore se un logo non si vede.
READY = '''<script>
window.__ready = new Promise(r => setTimeout(r, 0))
  .then(() => Promise.all([...document.images].map(i => i.decode().catch(() => {}))))
  .then(() => {
    const broken = [...document.querySelectorAll('.c-logo img')].filter(i => !i.naturalWidth).length;
    const chips = document.querySelectorAll('.c-logo .c-init').length;
    const rows = document.querySelectorAll('#tableArea .row').length;
    if (broken || chips || !rows) throw new Error(`Classifica incompleta: ${rows} righe, ${broken + chips} loghi mancanti`);
  });
</script>'''


def render(competition):
    """PNG 1920x2560 della classifica aggiornata (SA, UCL, UEL o UECL)."""
    import classifica_data

    data = classifica_data.fetch(competition)
    png = render_data(data)
    _last[data['competition']] = data
    return png


def summary(competition):
    """Elenco leggero dell'ultima classifica letta: lo mostra l'anteprima della Mini App."""
    data = _last.get((competition or '').upper())
    if not data:
        return None
    return {
        'name': data.get('competition_name', ''),
        'giornata': data.get('giornata'),
        'stagione': data.get('stagione', ''),
        'rows': [{'pos': r['pos'], 'team': r['team'], 'pt': r['pt'], 'dr': r['dr'],
                  'p': r.get('p'), 'zone': r.get('zone', '')} for r in data['classifica']],
    }


def render_data(data):
    data = json.loads(json.dumps(data))
    _embed_logos(data)
    try:
        png = render_html(build_html(data), page=PAGE)
    except Exception as exc:  # noqa: BLE001 - errore della pagina -> messaggio leggibile
        if 'Classifica incompleta' in str(exc):
            raise ValueError('Classifica incompleta: alcuni loghi non si vedono. Riprova tra poco.') from exc
        raise
    return _texture(png, TEXTURES.get(data['competition']))


def build_html(data):
    html = (DIR / 'template.html').read_text(encoding='utf-8')
    for name in IMAGES:
        html = html.replace(name, _data_uri(DIR / name))
    match = re.search(r'href="(https://fonts\.googleapis\.com/css2[^"]+)"', html)
    html = re.sub(r'<link[^>]+fonts\.(?:googleapis|gstatic)[^>]*>', '', html)
    fonts = _font_css(match.group(1)) if match else ''
    if fonts:
        html = html.replace('<head>', f'<head>\n<style>\n{fonts}\n</style>', 1)
    payload = json.dumps(data, ensure_ascii=False).replace('</', '<\\/')
    html = html.replace('<body>', f'<body>\n<script>window.__CLASSIFICA__ = {payload};</script>', 1)
    return html.replace('</body>', READY + '\n</body>', 1)


def _data_uri(path, mime='image/png'):
    return f'data:{mime};base64,' + base64.b64encode(path.read_bytes()).decode('ascii')


def _logo(url):
    if url.startswith('data:'):
        return url
    if url not in _logos:
        custom = CUSTOM_LOGOS.get(url)
        if custom:
            encoded = (DIR / custom).read_text(encoding='ascii').strip()
            base64.b64decode(encoded, validate=True)
            _logos[url] = f'data:image/png;base64,{encoded}'
        else:
            response = requests.get(url, headers=LOGO_HEADERS, timeout=25)
            response.raise_for_status()
            kind = response.headers.get('Content-Type', '').split(';', 1)[0]
            if not kind.startswith('image/') or not response.content:
                raise ValueError(f'risposta non valida ({kind or "senza tipo"})')
            _logos[url] = f'data:{kind};base64,' + base64.b64encode(response.content).decode('ascii')
    return _logos[url]


def _embed_logos(data):
    """Tutti i loghi dentro la pagina: se uno non si scarica, niente grafica a metà."""
    fields = ('logo', 'logo_light_bg', 'logo_dark_bg')
    rows = data.get('classifica', [])
    urls = sorted({row[f] for row in rows for f in fields if row.get(f)})
    if not urls:
        raise ValueError('Classifica senza loghi.')
    with ThreadPoolExecutor(max_workers=min(8, len(urls))) as pool:
        jobs = {url: pool.submit(_logo, url) for url in urls}
    errors = []
    found = {}
    for url, job in jobs.items():
        try:
            found[url] = job.result()
        except Exception as exc:  # noqa: BLE001 - si riassume sotto
            errors.append(f'{url}: {exc}')
    if errors:
        print('WARN IMAGEGEN: loghi classifica non scaricati:\n' + '\n'.join(errors), flush=True)
        raise ValueError(f'Non riesco a scaricare {len(errors)} loghi della classifica. Riprova tra poco.')
    for row in rows:
        for f in fields:
            if row.get(f):
                row[f] = found[row[f]]


def _font_css(css_url):
    """Font di Google incorporati (stessi del template). Se non si scaricano, font di sistema."""
    if css_url in _fonts:
        return _fonts[css_url]
    try:
        css = requests.get(css_url, headers={'User-Agent': UA}, timeout=20)
        css.raise_for_status()
        text = css.text
        for url in re.findall(r'url\((https://[^)]+)\)', text):
            font = requests.get(url, headers={'User-Agent': UA}, timeout=20)
            font.raise_for_status()
            fmt = 'woff2' if 'woff2' in url else 'woff' if 'woff' in url else 'truetype'
            text = text.replace(url, f'data:font/{fmt};base64,' + base64.b64encode(font.content).decode('ascii'))
        _fonts[css_url] = text
    except Exception as exc:  # noqa: BLE001 - meglio i font di sistema che nessuna grafica
        print(f'WARN IMAGEGEN: font della classifica non scaricati: {exc}', flush=True)
        return ''
    return text


def _texture(png, name):
    base = Image.open(io.BytesIO(png)).convert('RGBA')
    if name:
        texture = Image.open(DIR / name).convert('RGBA')
        if texture.size != base.size:
            texture = texture.resize(base.size, Image.Resampling.LANCZOS)
        base.paste(texture, (0, 0), texture)
    out = io.BytesIO()
    base.convert('RGB').save(out, 'PNG')
    return out.getvalue()
