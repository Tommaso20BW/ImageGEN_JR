"""Foto ufficiali dei giocatori della Juventus dal sito della Lega Serie A.

Pagina https://www.legaseriea.it/team/juventus/squad: per ogni giocatore una foto scontornata
(PNG/WebP 1024x1024 con trasparenza, testa e busto, maglia home). Si salvano nel repo degli
asset in players_lega/ così servono a qualunque grafica:

    players_lega/<slug>.webp      slug = cartella del giocatore in players/ se è nella nostra rosa,
                                  altrimenti dal nome ufficiale
    players_lega/manifest.json    {slug: {"name", "official", "url", "in_roster"}}

Uso (in locale, poi commit nel repo degli asset):
    IMAGEGEN_ASSETS=<repo asset> python foto_lega.py
"""
import html
import json
import re
import sys
import unicodedata
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import requests

SQUAD_URL = 'https://www.legaseriea.it/team/juventus/squad'
UA = {'User-Agent': 'ImageGEN-JR/1.0 (anteprima post)'}
DIRNAME = 'players_lega'
PHOTO_RE = re.compile(r'https://media-sdp\.legaseriea\.it/playerImages/[^"\'\s)\\]+?/home/[^"\'\s)\\]+?\.webp')


def _words(text):
    raw = unicodedata.normalize('NFKD', html.unescape(str(text))).encode('ascii', 'ignore').decode().lower()
    return [w for w in re.split(r'[^a-z0-9]+', raw) if w]


def _slug(text):
    return '_'.join(_words(text)) or 'giocatore'


def parse_squad(page):
    """[(nome ufficiale, url foto)] dalla pagina della rosa: ogni foto ha il nome del giocatore
    nell'attributo alt (alcune schede, es. Neto, non hanno il link al profilo)."""
    out, seen = [], set()
    for tag in re.findall(r'<img[^>]*>', page):
        alt = re.search(r'alt="([^"]*)"', tag)
        src = PHOTO_RE.search(tag)
        if not alt or not src or src.group(0) in seen:
            continue
        name = html.unescape(alt.group(1)).replace("'", '').strip()
        if name:
            seen.add(src.group(0))
            out.append((name, src.group(0)))
    return out


def match_roster(official, roster):
    """Giocatore della nostra rosa con lo stesso nome: tutte le parole del nome più corto
    stanno nel più lungo ("Douglas Luiz" / "Douglas Luiz Soares De Paulo", "Bremer" /
    "Gleison Bremer"). Ritorna lo slug della cartella players/ o None."""
    words = set(_words(official))
    hits = []
    for player in roster:
        for name in [player.name, *getattr(player, 'aliases', [])]:
            ours = set(_words(name))
            if ours and (ours <= words or words <= ours):
                hits.append(player.slug)
                break
    return hits[0] if len(set(hits)) == 1 else None


def update(asset_dir, roster):
    folder = Path(asset_dir) / DIRNAME
    folder.mkdir(parents=True, exist_ok=True)
    page = requests.get(SQUAD_URL, headers=UA, timeout=30)
    page.raise_for_status()
    squad = parse_squad(page.text)
    if not squad:
        raise RuntimeError('Nessuna foto trovata nella pagina della Lega Serie A.')

    def get(item):
        official, url = item
        r = requests.get(url, headers=UA, timeout=30)
        return official, url, r.content if r.status_code == 200 else None
    with ThreadPoolExecutor(6) as pool:
        photos = list(pool.map(get, squad))
    skipped = [official for official, _url, content in photos if content is None]
    if skipped:      # foto non pubblicata (il sito mostra quella generica): si salta
        print('Foto non disponibili sul sito:', ', '.join(skipped))
    photos = [p for p in photos if p[2] is not None]
    manifest = {}
    for official, url, content in photos:
        ours = match_roster(official, roster)
        slug = ours or _slug(official)
        (folder / f'{slug}.webp').write_bytes(content)
        manifest[slug] = {'name': next((p.name for p in roster if p.slug == ours), official),
                          'official': official, 'url': url, 'in_roster': bool(ours)}
    (folder / 'manifest.json').write_text(json.dumps(dict(sorted(manifest.items())), ensure_ascii=False, indent=1) + '\n',
                                          encoding='utf-8')
    return manifest


def photo_path(asset_dir, slug):
    """Foto ufficiale di un giocatore della rosa (None se non c'è)."""
    path = Path(asset_dir) / DIRNAME / f'{slug}.webp'
    return path if path.is_file() else None


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    from graphics.common import asset_dir
    from livescore.graphics import goal as g
    roster = g.load_players()
    result = update(asset_dir(), roster)
    inside = [k for k, v in result.items() if v['in_roster']]
    print(f'{len(result)} foto salvate, {len(inside)} di giocatori della nostra rosa')
    missing = [p.name for p in roster if p.slug not in result]
    print('In rosa senza foto ufficiale:', ', '.join(missing) or 'nessuno')
    print('Solo sul sito (Primavera / non in rosa):', ', '.join(v['official'] for v in result.values() if not v['in_roster']))
