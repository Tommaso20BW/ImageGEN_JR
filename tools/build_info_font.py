"""Font della riga info (stadio | competizione | orario | data) di MATCHDAY.

Canva usa Nimbus Sans Novus (font a pagamento) e nel PDF ci sono solo le
lettere usate. Questo script crea un font unico:
  - lettere originali di Canva dove esistono (estratte dal PDF);
  - lettere mancanti da Nimbus Sans (URW, libero), ristrette alla larghezza
    media di Novus e alla stessa altezza delle maiuscole;
  - crenatura misurata sulle posizioni reali del PDF.

Uso:
    python tools/build_info_font.py _canva_ref/design.pdf ../LiveScore_Assets_JR/fonts/MatchdayInfo.ttf
Scarica da solo Nimbus Sans (urw-base35-fonts) se manca in _canva_ref/fonts.
"""
import argparse
import io
import urllib.request
from pathlib import Path

import pymupdf
from fontTools.fontBuilder import FontBuilder
from fontTools.pens.cu2quPen import Cu2QuPen
from fontTools.pens.transformPen import TransformPen
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.ttLib import TTFont, newTable
from fontTools.ttLib.tables._k_e_r_n import KernTable_format_0

NIMBUS_URL = ('https://raw.githubusercontent.com/ArtifexSoftware/urw-base35-fonts/'
              'master/fonts/NimbusSans-Regular.otf')
FONT_KEY = 'NimbusSansNovus'
PAGES = (2, 7, 12)
CHARS = (
    ' !"#&\'()*+,-./0123456789:;?@ABCDEFGHIJKLMNOPQRSTUVWXYZ|'
    'ÀÁÂÄÇÈÉÊËÌÍÎÏÑÒÓÔÖÙÚÛÜ’–—·'
)


def _subsets(pdf):
    """Font Novus estratti dalle pagine Matchday + coppie di crenatura osservate."""
    fonts, kerns = [], {}
    for n in PAGES:
        page = pdf[n - 1]
        for f in page.get_fonts(full=True):
            if FONT_KEY in f[3]:
                fonts.append(TTFont(io.BytesIO(pdf.extract_font(f[0])[3])))
        font = fonts[-1]
        cmap, hmtx = font.getBestCmap(), font['hmtx']
        for block in page.get_text('rawdict')['blocks']:
            for line in block.get('lines', []):
                for span in line['spans']:
                    if FONT_KEY not in span['font']:
                        continue
                    size, chars = span['size'], span['chars']
                    for a, b in zip(chars, chars[1:]):
                        if ord(a['c']) not in cmap:
                            continue
                        real = (b['origin'][0] - a['origin'][0]) * 1000 / size
                        kern = round(real - hmtx[cmap[ord(a['c'])]][0])
                        if kern and a['c'] != ' ' and b['c'] != ' ':
                            kerns[(a['c'], b['c'])] = kern
    return fonts, kerns


def build(pdf_path, out_path, nimbus_path):
    if not nimbus_path.is_file():
        nimbus_path.parent.mkdir(parents=True, exist_ok=True)
        urllib.request.urlretrieve(NIMBUS_URL, nimbus_path)
    with pymupdf.open(pdf_path) as pdf:
        novus_fonts, kerns = _subsets(pdf)
    nimbus = TTFont(nimbus_path)
    nimbus_cmap, nimbus_set, nimbus_hmtx = nimbus.getBestCmap(), nimbus.getGlyphSet(), nimbus['hmtx']

    # Fonte di ogni carattere: prima Novus (originale), poi Nimbus.
    source = {}
    for font in novus_fonts:
        for code, gname in font.getBestCmap().items():
            source.setdefault(chr(code), (font, gname))

    # Proporzioni Novus / Nimbus sulle lettere in comune.
    ratios = [source[c][0]['hmtx'][source[c][1]][0] / nimbus_hmtx[nimbus_cmap[ord(c)]][0]
              for c in source if c.isalnum() and ord(c) in nimbus_cmap]
    sx = sum(ratios) / len(ratios)
    cap =source['E'][0]['glyf'][source['E'][1]]
    cap.recalcBounds(source['E'][0]['glyf'])
    sy = cap.yMax / nimbus['OS/2'].sCapHeight
    print(f'Nimbus adattata: larghezza x{sx:.3f}, altezza x{sy:.3f}; '
          f'originali {len(source)} caratteri; crenature {len(kerns)}')

    order, cmap, glyphs, metrics = ['.notdef'], {}, {'.notdef': TTGlyphPen(None).glyph()}, {'.notdef': (500, 0)}
    for i, ch in enumerate(dict.fromkeys(CHARS)):
        name = 'space' if ch == ' ' else f'g{i:03d}'
        pen = TTGlyphPen(None)
        if ch in source:
            font, gname = source[ch]
            font.getGlyphSet()[gname].draw(pen)
            width = font['hmtx'][gname][0]
        elif ord(ch) in nimbus_cmap:
            gname = nimbus_cmap[ord(ch)]
            nimbus_set[gname].draw(TransformPen(Cu2QuPen(pen, 1.0, reverse_direction=True), (sx, 0, 0, sy, 0, 0)))
            width = round(nimbus_hmtx[gname][0] * sx)
        else:
            continue
        glyph = pen.glyph()
        order.append(name)
        cmap[ord(ch)] = name
        glyphs[name] = glyph
        metrics[name] = (width, 0)

    fb = FontBuilder(1000, isTTF=True)
    fb.setupGlyphOrder(order)
    fb.setupCharacterMap(cmap)
    fb.setupGlyf(glyphs)
    glyf = fb.font['glyf']
    fb.setupHorizontalMetrics({n: (w, getattr(glyf[n], 'xMin', 0)) for n, (w, _) in metrics.items()})
    fb.setupHorizontalHeader(ascent=889, descent=-200)
    fb.setupNameTable({'familyName': 'Matchday Info', 'styleName': 'Regular'})
    fb.setupOS2(sTypoAscender=889, sTypoDescender=-200, usWinAscent=889, usWinDescent=200)
    fb.setupPost()

    kern = newTable('kern')
    kern.version = 0
    table = KernTable_format_0()
    table.version, table.coverage, table.format = 0, 1, 0
    table.kernTable = {(cmap[ord(a)], cmap[ord(b)]): v for (a, b), v in kerns.items()
                       if ord(a) in cmap and ord(b) in cmap}
    kern.kernTables = [table]
    fb.font['kern'] = kern

    out_path.parent.mkdir(parents=True, exist_ok=True)
    fb.save(str(out_path))
    print('OK', out_path)


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('pdf', type=Path)
    parser.add_argument('out', type=Path)
    parser.add_argument('--nimbus', type=Path, default=Path('_canva_ref/fonts/NimbusSans-Regular.otf'))
    args = parser.parse_args()
    build(args.pdf, args.out, args.nimbus)


if __name__ == '__main__':
    main()
