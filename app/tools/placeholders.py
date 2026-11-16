"""Sagome fisse per gli editor foto (Starting XI, Matchday, Foto + JR, Titolo JR, Citazioni, Compleanno, MOTM, POTM, Here We Go).

Non contengono i dati inseriti: la grafica vera senza foto con dati finti fissi
(Juve storica, stemmi Juventus, partita qualunque). Servono a posizionare la foto.
Una immagine per grafica e variante (540 px di larghezza): canva/<nome>_<variante>_placeholder.png
L'editor la mostra subito, poi la sostituisce con la sagoma vera fatta dal servizio coi dati inseriti.

Uso: python tools/placeholders.py ../LiveScore_Assets_JR/canva
"""
import json
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


# Competizione scritta nella sagoma Matchday: quella del tema (maglie normali: Serie A).
COMPETITION = {'ucl': 'uefa.champions', 'uel': 'uefa.europa', 'conference': 'uefa.europa.conf',
               'coppa': 'ita.coppa_italia', 'supercoppa': 'ita.super_cup', 'usc': 'uefa.super_cup',
               'cwc': 'fifa.cwc', 'friendly': 'club.friendly'}


def matchday(canva, out):
    """Grafica vera senza foto, con stemmi, stadio, competizione, ora e data finti."""
    info = md.parse_info('ALLIANZ STADIUM', '20:45', '2026-11-01')
    for kit in md.KITS:
        png = md.render(ghost=True, kit=kit, photo=None, frame={}, info=info,
                        competition=COMPETITION.get(kit, 'ita.1'), **FAKE_TEAMS)
        (out / f'matchday_{kit}_placeholder.png').write_bytes(png)
        print('OK matchday', kit)


def jr(canva, out):
    meta = json.loads((canva / 'jr.json').read_text(encoding='utf-8'))
    for color, cm in meta.items():
        img = Image.open(canva / cm['overlay']).convert('RGBA').resize((W, H), Image.LANCZOS)
        img.save(out / f'jr_{color}_placeholder.png', optimize=True)
        print('OK jr', color)


def _small(png, out, name):
    """Salva la sagoma larga W (altezza in proporzione)."""
    import io
    img = Image.open(io.BytesIO(png)).convert('RGBA')
    img = img.resize((W, round(img.height * W / img.width)), Image.LANCZOS)
    img.save(out / f'{name}_placeholder.png', optimize=True)
    print('OK', name, img.size)


def jr_title(canva, out):
    """Titolo JR: grafica vera senza foto con un titolo finto, per ogni colore del logo."""
    from graphics import photo_jr
    for color in json.loads((canva / 'jr.json').read_text(encoding='utf-8')):
        png = photo_jr.render(color=color, style='title', photo=None, frame={}, title='TITOLO',
                              title_color=photo_jr.TITLE_COLOR, ghost=True)
        _small(png, out, f'jrtitle_{color}')


QUOTE_TEXT = 'Il testo del post va qui: due o tre righe, come una citazione qualunque.'


def quotes(canva, out):
    """Citazioni (IG, X, Threads; IG anche storia): grafica vera senza foto con testo e nome finti."""
    from graphics import ig_quote
    for variant, platform, story in (('ig', 'ig', False), ('igstory', 'ig', True),
                                     ('x', 'x', False), ('threads', 'threads', False)):
        png = ig_quote.render(photo=None, text='' if story else QUOTE_TEXT, name='Juventus', handle='juventusfc',
                              verified=True, story=story, platform=platform, frame={}, ghost=True)
        _small(png, out, f'quote_{variant}')


def compleanno(canva, out):
    """Compleanno (Rosa attuale ed Ex giocatore): poster senza giocatore con nome e data finti."""
    from graphics import compleanno as bd, compleanno_storico as bdo
    _small(bd.render(name='NOME GIOCATORE', birth='2000-01-01', age=26, photo='', ghost=True), out, 'compleanno_now')
    _small(bdo.render(name='NOME GIOCATORE', ghost=True), out, 'compleanno_old')


def motm(canva, out):
    """Man of the Match: poster senza giocatore con nome e partita finti."""
    from graphics import motm as mo
    _small(mo.render(surname='COGNOME', name='Nome', home='Juventus', away='Avversario',
                     comp='Serie A - Matchday 1', ghost=True), out, 'motm_std')



def potm(canva, out):
    """Player of the Month: poster senza giocatore con nome e mese finti."""
    from graphics import potm as po
    _small(po.render(surname='COGNOME', name='Nome', month='Mese', ghost=True), out, 'potm_gold')


def af(canva, out):
    """Here We Go: poster AFFARE FATTO senza giocatore con nome e cognome finti."""
    from graphics import affare_fatto
    _small(affare_fatto.render(surname='COGNOME', name='NOME', ghost=True), out, 'af_gold')


def main():
    canva = Path(sys.argv[1] if len(sys.argv) > 1 else '../LiveScore_Assets_JR/canva')
    starting_xi(canva, canva)
    matchday(canva, canva)
    jr(canva, canva)
    jr_title(canva, canva)
    quotes(canva, canva)
    compleanno(canva, canva)
    motm(canva, canva)
    potm(canva, canva)
    af(canva, canva)


if __name__ == '__main__':
    main()
