"""Prova automatica di tutte le grafiche (workflow "Prova grafiche", a ogni modifica).

Per ogni grafica costruisce la richiesta come la manda la Mini App, la fa controllare dal
servizio (webapp_payload, come in una sessione vera) e la genera (render.Renderer). Niente
Telegram e niente salvataggi: serve solo a sapere se qualcosa si è rotto prima di una partita.

Uso (da app/):  python tools/smoke_graphics.py [cartella_anteprime]

Esce con codice 1 se una grafica non si genera. Classifica e tabellone leggono Diretta.it:
se il sito non risponde è solo un avviso (non dipende dal nostro codice).
Le anteprime ridotte (JPEG) finiscono nella cartella indicata, per guardarle a occhio.
"""
import io
import os
import sys
import time
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PIL import Image

import webapp_payload as wp
from catalog import Catalog
from render import Renderer
from graphics.common import asset_dir
from livescore.graphics import goal as g

SESSION = 'smoke'
NOW = '2026-01-01T00:00:00Z'
OPP = {'name': 'ACF Fiorentina'}
UEFA_OPP = {'name': 'FC Bayern Munchen'}
ONLINE = {'table'}                 # dipendono da un sito esterno: errore = avviso


def _photo(player='kenan_yildiz'):
    """Foto d'esempio: giocatore già scontornato (PNG trasparente, niente modello di scontorno)."""
    im = Image.open(asset_dir() / 'players_lega' / f'{player}.webp').convert('RGBA').resize((1300, 1300))
    page = Image.new('RGBA', (1080, 1440), (0, 0, 0, 0))
    page.alpha_composite(im, (-110, 160))
    out = io.BytesIO()
    page.save(out, 'PNG')
    return out.getvalue()


def _cases(roster):
    outfield = [p.name for p in roster if p.role == 'outfield']
    keeper = next(p.name for p in roster if p.role == 'goalkeeper')
    eleven = [keeper] + outfield[:10]
    lineup = [{'number': str(n), 'name': name} for n, name in zip(range(1, 12), eleven)]
    match = {'competition': 'ita.1', 'kit': 'home', 'side': 'home', 'opponent': OPP}
    ita = {'team': 'italy', 'competition': 'uefa.nations', 'kit': 'ita_home', 'side': 'home',
           'opponent': {'name': 'Francia'}}
    stats = {'moment': 'FT', 'rows': [{'label': 'POSSESSO', 'home': '58', 'away': '42'},
                                      {'label': 'TIRI', 'home': '14', 'away': '7'},
                                      {'label': 'xG', 'home': '1.8', 'away': '0.6'}]}
    photo = {'photo_id': 'a' * 16, 'frame': {'x': 0, 'y': 0, 'zoom': 1}}
    yield 'Gol', {'kind': 'goal', **match, 'pose': 'arms_crossed', 'player': outfield[0], 'minute': '56', 'score': [1, 0]}
    yield 'Gol (rigore)', {'kind': 'goal', **match, 'goal_type': 'penalty', 'pose': 'pointing', 'player': outfield[0], 'minute': '90+2', 'score': [2, 1]}
    yield 'Gol (autogol)', {'kind': 'goal', **match, 'goal_type': 'own', 'player': 'Rossi', 'minute': '12', 'score': [1, 0]}
    yield 'Gol (senza foto)', {'kind': 'goal', **match, 'goal_type': 'nophoto', 'player': 'Mario Bianchi', 'minute': '30'}
    yield 'Parata', {'kind': 'saved', **match, 'pose': 'arms_crossed', 'player': keeper, 'minute': '77'}
    yield 'Gol (esultanza urlo)', {'kind': 'goal', **match, 'kit': 'away', 'pose': 'scream', 'player': outfield[0], 'minute': '61', 'score': [2, 0]}
    yield 'Parata (esultanza urlo)', {'kind': 'saved', **match, 'pose': 'scream', 'player': keeper, 'minute': '80'}
    yield 'Kick Off', {'kind': 'kick', **match}
    yield '2nd Half', {'kind': 'second', **match, 'score': [1, 1]}
    yield 'Half Time', {'kind': 'half', **match, 'score': [1, 0], **photo}
    yield "End Of 90'", {'kind': 'end_of_90', **match, 'score': [2, 2], **photo}
    yield 'Full Time (rigori)', {'kind': 'full', **match, 'kit': 'away', 'score': [1, 1], 'extra_time': True,
                                 'shootout': [5, 4], **photo}
    yield 'Statistiche', {'kind': 'stats', **match, **stats}
    yield 'Matchday', {'kind': 'md', **match, **photo, 'stadium': 'Allianz Stadium', 'time': '20:45', 'date': '2026-11-22'}
    yield 'Matchday (Champions)', {'kind': 'md', **match, 'competition': 'uefa.champions', 'kit': 'ucl',
                                   'opponent': UEFA_OPP, **photo, 'stadium': 'Allianz Stadium', 'time': '21:00', 'date': '2026-08-15'}
    yield 'Starting XI', {'kind': 'xi', **match, 'kit': 'third', 'lineup': lineup, **photo}
    yield 'Probabile XI', {'kind': 'pxi', **match, 'module': '4-3-3', 'players': eleven}
    yield 'Probabile XI (Champions)', {'kind': 'pxi', **match, 'competition': 'uefa.champions', 'kit': 'ucl',
                                       'opponent': UEFA_OPP, 'shirt': 'home', 'module': '3-5-2', 'players': eleven}
    yield 'Probabile XI (amichevole)', {'kind': 'pxi', **match, 'competition': 'club.friendly', 'kit': 'friendly', 'module': '4-3-3',
                                        'players': ['Uno', 'Due', 'Tre', 'Quattro', 'Cinque', 'Sei', 'Sette', 'Otto', 'Nove', 'Dieci', 'Undici']}
    squad = '\n'.join(p.name for p in roster[:23])
    yield 'Squad List', {'kind': 'squad', **match, 'squad': squad}
    yield 'Squad List (amichevole)', {'kind': 'squad', **match, 'competition': 'club.friendly', 'squad': squad}
    yield 'Calendario', {'kind': 'cal', 'month': 11, 'year': 2026, 'matches': [
        {'day': 1, 'opponent': OPP, 'side': 'home'}, {'day': 8, 'opponent': {'name': 'Torino FC'}, 'side': 'away'},
        {'day': 22, 'opponent': {'name': 'AC Milan'}, 'side': 'home'}]}
    yield 'Classifica Serie A', {'kind': 'table', 'competition': 'SA'}
    yield 'Tabellone Coppa Italia', {'kind': 'table', 'competition': 'CI'}
    yield 'Convocati', {'kind': 'conv', 'footer': 'Pausa nazionali', 'players': [
        {'name': outfield[0], 'shown': outfield[0], 'nation': 'Italia'},
        {'name': outfield[1], 'shown': outfield[1], 'nation': 'Francia Under 21'},
        {'name': keeper, 'shown': keeper, 'nation': 'it'}]}
    yield 'Post (classica)', {'kind': 'jr', 'style': 'classic', 'color': 'white', 'ratio': '4:5', **photo}
    yield 'Post (titolo)', {'kind': 'jr', 'style': 'title', 'color': 'white', 'title': 'Infortunio', 'title_color': '#e7e4df', **photo}
    yield 'Post (sfocata)', {'kind': 'jr', 'style': 'blur', 'color': 'gold', 'background_id': 'a' * 16,
                             'cards': [{'photo_id': 'a' * 16, 'x': .5, 'y': .5, 'w': .7}]}
    yield 'Post (collage)', {'kind': 'jr', 'style': 'collage', 'color': 'black', 'cells': [
        {'photo_id': 'a' * 16, 'x': 0, 'y': 0, 'w': .5, 'h': 1}, {'photo_id': 'b' * 16, 'x': .5, 'y': 0, 'w': .5, 'h': 1}]}
    yield 'Rinnovo', {'kind': 'rin', 'name': 'N.GONZALEZ', 'year': '2030'}
    yield 'Storia Instagram', {'kind': 'igbn', 'text': 'Breaking news: prova automatica delle grafiche.', **photo}
    quote = {'text': 'Testo di prova della citazione, abbastanza lungo da andare a capo.', 'name': 'Juventus Reborn',
             'handle': 'juventus_reborn', **photo}
    yield 'Citazione Instagram', {'kind': 'igq', **quote}
    yield 'Citazione X', {'kind': 'xq', **quote, 'verified': True}
    yield 'Citazione Threads', {'kind': 'thq', **quote}
    yield 'Italia · Kick Off', {'kind': 'kick', **ita}
    yield 'Italia · Gol', {'kind': 'goal', **ita, 'player': 'Retegui', 'minute': '33', 'score': [1, 0]}
    yield 'Italia · Full Time', {'kind': 'full', **ita, 'kit': 'ita_away', 'score': [2, 1]}
    yield 'Italia · Statistiche', {'kind': 'stats', **ita, **stats}
    yield 'Italia · Starting XI', {'kind': 'xi', **ita, 'formation': '4-3-3',
                                   'players': ['Donnarumma', 'Di Lorenzo', 'Bastoni', 'Calafiori', 'Dimarco', 'Barella',
                                               'Tonali', 'Frattesi', 'Chiesa', 'Retegui', 'Raspadori']}


def main(out_dir=None):
    out = Path(out_dir) if out_dir else None
    if out:
        out.mkdir(parents=True, exist_ok=True)
    renderer = Renderer()
    renderer.photos['a' * 16] = _photo()
    renderer.photos['b' * 16] = _photo('weston_mckennie')
    catalog = Catalog()
    results = []
    for n, (name, incoming) in enumerate(_cases(g.load_players()), 1):
        started = time.time()
        try:
            state = wp.parse_webapp_request({'v': 1, 'action': 'render', 'session': SESSION, 'data': incoming},
                                            catalog, NOW, SESSION)
            png = renderer.render(state['data'])
            with Image.open(io.BytesIO(png)) as image:
                size = image.size
                if min(size) < 500:
                    raise ValueError(f'immagine troppo piccola: {size}')
                if out:
                    image.convert('RGB').resize((size[0] // 4, size[1] // 4)).save(out / f'{n:02d}_{incoming["kind"]}.jpg', quality=80)
            results.append((name, 'ok', f'{size[0]}x{size[1]} · {time.time() - started:.1f} s'))
        except Exception as exc:  # noqa: BLE001 - si raccolgono tutti gli errori, poi il riepilogo
            level = 'avviso' if incoming['kind'] in ONLINE else 'ERRORE'
            results.append((name, level, f'{type(exc).__name__}: {exc}'))
            traceback.print_exc()
        print(f'{results[-1][1]:7s} {name} | {results[-1][2]}', flush=True)

    broken = [r for r in results if r[1] == 'ERRORE']
    warned = [r for r in results if r[1] == 'avviso']
    summary = os.environ.get('GITHUB_STEP_SUMMARY')
    if summary:
        lines = ['## Prova grafiche', '',
                 f'{len(results) - len(broken) - len(warned)} riuscite · {len(broken)} rotte · {len(warned)} avvisi', '',
                 '| | Grafica | Dettaglio |', '|---|---|---|']
        icon = {'ok': '✅', 'ERRORE': '❌', 'avviso': '⚠️'}
        lines += [f'| {icon[s]} | {n} | {d.replace("|", "/")} |' for n, s, d in results]
        Path(summary).write_text('\n'.join(lines) + '\n', encoding='utf-8')
    print(f'\n{len(results) - len(broken) - len(warned)} riuscite, {len(broken)} rotte, {len(warned)} avvisi')
    return 1 if broken else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else None))
