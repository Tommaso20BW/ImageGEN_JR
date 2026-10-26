"""Sagome fisse per l'editor foto (Starting XI, Matchday, Foto + JR).

Non contengono i dati inseriti: la grafica vera senza foto con dati finti fissi
(Juve storica, stemmi Juventus, partita qualunque). Servono a posizionare la foto.
Una immagine 540x720 per grafica e maglia: canva/<nome>_<maglia>_placeholder.png

Uso: python tools/placeholders.py ../LiveScore_Assets_JR/canva
"""
import sys
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from graphics import matchday as md, starting_xi as sx  # noqa: E402

W, H = 540, 720


# Dati finti (fissi, uguali per tutti): una Juve storica e una partita qualunque.
FAKE_XI = [('1', 'BUFFON'), ('26', 'LICHTSTEINER'), ('15', 'BARZAGLI'), ('19', 'BONUCCI'),
           ('3', 'CHIELLINI'), ('21', 'PIRLO'), ('23', 'VIDAL'), ('8', 'MARCHISIO'),
           ('6', 'POGBA'), ('10', 'TEVEZ'), ('14', 'LLORENTE')]
FAKE_TEAMS = dict(home_name='Juventus', home_id='111', away_name='Juventus', away_id='111')


def starting_xi(canva, out):
    """Grafica vera senza foto, con formazione e stemmi finti (sfondo trasparente, 540x720)."""
    for kit in sx.KITS:
        png = sx.render(ghost=True, kit=kit, lineup=FAKE_XI, photo=None, frame={}, **FAKE_TEAMS)
        (out / f'starting_xi_{kit}_placeholder.png').write_bytes(png)
        print('OK starting_xi', kit)


def matchday(canva, out):
    """Grafica vera senza foto, con stemmi, stadio, competizione, ora e data finti."""
    info = md.parse_info('ALLIANZ STADIUM', '20:45', '2026-11-01')
    for kit in md.KITS:
        png = md.render(ghost=True, kit=kit, photo=None, frame={}, info=info, competition='ita.1', **FAKE_TEAMS)
        (out / f'matchday_{kit}_placeholder.png').write_bytes(png)
        print('OK matchday', kit)


def jr(canva, out):
    meta = json.loads((canva / 'jr.json').read_text(encoding='utf-8'))
    for color, cm in meta.items():
        img = Image.open(canva / cm['overlay']).convert('RGBA').resize((W, H), Image.LANCZOS)
        img.save(out / f'jr_{color}_placeholder.png', optimize=True)
        print('OK jr', color)


def main():
    canva = Path(sys.argv[1] if len(sys.argv) > 1 else '../LiveScore_Assets_JR/canva')
    starting_xi(canva, canva)
    matchday(canva, canva)
    jr(canva, canva)


if __name__ == '__main__':
    main()
