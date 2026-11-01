"""Sagome fisse per l'editor foto di HALF TIME / END OF 90' / FULL TIME.

Una per fase e per sfondo (home, away, third, ucl, uel, conference), con dati
finti (Juventus - Juventus 0-0): mostrano cornice, scritta, risultato e stemmi
dove saranno, così l'editor le mostra subito invece di aspettare il render.
File: canva/phase_<fase>_<sfondo>_placeholder.png (543x724, trasparente).

Uso: IMAGEGEN_ASSETS=../LiveScore_Assets_JR PYTHONPATH=".;../LiveScore_JR" python tools/phase_placeholders.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from graphics.common import asset_dir  # noqa: E402
from livescore.graphics import phase_layers, portrait  # noqa: E402

PHASES = ('half', 'end_of_90', 'full')
THEMES = {'home': ('home', 'ita.1'), 'away': ('away', 'ita.1'), 'third': ('third', 'ita.1'),
          'ucl': ('home', 'uefa.champions'), 'uel': ('home', 'uefa.europa'),
          'conference': ('home', 'uefa.europa.conf')}


def main():
    assets = asset_dir()
    out = assets / 'canva'
    for kind in PHASES:
        for theme, (kit, competition) in THEMES.items():
            def draw(layers, kind=kind, kit=kit, competition=competition):
                return portrait.phase(kind=kind, home_name='Juventus', away_name='Juventus',
                                      home_id='111', away_id='111', home_goals=0, away_goals=0,
                                      kit=kit, competition=competition, layers=layers, assets=assets)
            png = phase_layers.ghost(draw)
            (out / f'phase_{kind}_{theme}_placeholder.png').write_bytes(png)
            print('OK', kind, theme)


if __name__ == '__main__':
    main()
