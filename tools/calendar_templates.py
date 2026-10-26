"""Pezzi fissi del CALENDARIO (pagina 24) dal PDF Canva.

  calendar_bg.png          sfondo con le 7 righe (barretta + linea), JR, grana
  calendar_title_ink.png   texture oro della seconda metà del mese
  calendar_day_<k>.png     texture oro del numero della riga k
  calendar.json            misure e colori

Uso:
    python tools/calendar_templates.py _canva_ref/design.pdf ../LiveScore_Assets_JR/canva
"""
import argparse
import io
import json
import re
import sys
from collections import Counter
from pathlib import Path

import pymupdf
from PIL import Image

sys.path.insert(0, str(Path(__file__).parent))
from canva_templates import OUT_W, _no_background, _pattern_sections, _single_page  # noqa: E402
from canva_templates import _png as _pix  # noqa: E402


def _png(page, alpha):
    return Image.open(io.BytesIO(_pix(page, alpha).tobytes('png')))

PAGE = 24
S = 1080 / 810


def _forms(page):
    return {x[1]: x for x in page.get_xobjects()}


def _plate(source, keep_top, keep_child, section_form, k=0):
    """Texture del testo `section_form` (sezione k) senza la forma delle lettere."""
    doc, page = _single_page(source, PAGE)
    forms = _forms(page)
    _no_background(doc, page)
    xref = page.get_contents()[0]
    data = re.sub(rb'/(X\d+)\s+Do', lambda m: m.group(0) if m.group(1).decode() == keep_top else b'',
                  doc.xref_stream(xref))
    doc.update_stream(xref, data)
    if keep_child:
        top = forms[keep_top][0]
        data = re.sub(rb'/(X\d+)\s+Do', lambda m: m.group(0) if m.group(1).decode() == keep_child else b'',
                      doc.xref_stream(top))
        doc.update_stream(top, data)
    target = forms[section_form][0]
    data = doc.xref_stream(target)
    sections = _pattern_sections(data)
    out, last = [], 0
    for bt in re.finditer(rb'BT.*?ET', data, re.S):
        out.append(data[last:bt.start()])
        out.append(b'-4000 -4000 9000 9000 re f' if bt.start() == sections[k].start(1) else b'')
        last = bt.end()
    out.append(data[last:])
    doc.update_stream(target, b''.join(out))
    image = _png(page, alpha=True)
    box = image.getchannel('A').getbbox()
    scale = 1080 / OUT_W
    return image.crop(box), [box[0] * scale, box[1] * scale, (box[2] - box[0]) * scale, (box[3] - box[1]) * scale]


def build(source, out):
    doc, page = _single_page(source, PAGE)
    forms = _forms(page)
    rows_form = forms['X165'][0]
    order = [n.decode() for n in re.findall(rb'/(X\d+) Do', doc.xref_stream(rows_form))]
    number_forms = [n for n in order if forms[n][3][2] > 1000]           # blocchi del numero
    texts = []
    for b in page.get_text('rawdict')['blocks']:
        for line in b.get('lines', []):
            for span in line['spans']:
                t = ''.join(c['c'] for c in span['chars'])
                texts.append((t, span))
    days = []
    for t, span in texts:
        if t.isdigit() and (not days or days[-1]['text'] != t):
            days.append({'text': t, 'right': round(span['bbox'][2] * S, 2),
                         'base': round(span['chars'][0]['origin'][1] * S, 2), 'size': round(span['size'] * S, 2)})
    title = [s for t, s in texts if t.isalpha()]
    title_base = round(title[0]['chars'][0]['origin'][1] * S, 2)
    title_size = round(title[0]['size'] * S, 2)
    title_left = round(title[0]['bbox'][0] * S, 2)
    title_right = round(max(s['bbox'][2] for s in title) * S, 2)

    # Loghi: riquadri per riga (sinistra = casa, destra = trasferta).
    logo_boxes = sorted({tuple(round(v * S, 1) for v in i['bbox']) for i in page.get_image_info(xrefs=True)
                         if i['width'] == i['height'] and 300 < i['width'] < 600})
    lefts = sorted({b[0] for b in logo_boxes})
    logo_x = [lefts[0], lefts[-1]]
    logo_size = round(logo_boxes[0][2] - logo_boxes[0][0], 2)
    img = [x for x in page.get_images(full=True) if x[2] == x[3] == 480][0]
    pix = pymupdf.Pixmap(pymupdf.Pixmap(doc, img[0]), pymupdf.Pixmap(doc, img[1])) if img[1] else pymupdf.Pixmap(doc, img[0])
    rgba = Image.open(io.BytesIO(pix.tobytes('png'))).convert('RGBA')
    logo_color = '#%02x%02x%02x' % Counter(p[:3] for p in rgba.getdata() if p[3] > 250).most_common(1)[0][0]

    # Sfondo: senza righe variabili e titolo.
    doc_bg, page_bg = _single_page(source, PAGE)
    xref = page_bg.get_contents()[0]
    data = re.sub(rb'/X169\s+Do', b'', doc_bg.xref_stream(xref))
    doc_bg.update_stream(xref, data)
    rows_bg = _forms(page_bg)['X165'][0]
    doc_bg.update_stream(rows_bg, b'')
    # Decorazioni delle righe (barretta + linea) da sole, per ritagliarne una.
    doc_dec, page_dec = _single_page(source, PAGE)
    _no_background(doc_dec, page_dec)
    xd = page_dec.get_contents()[0]
    doc_dec.update_stream(xd, re.sub(rb'/(X\d+)\s+Do', lambda m: m.group(0) if m.group(1) == b'X165' else b'',
                                     doc_dec.xref_stream(xd)))
    rows_dec = _forms(page_dec)['X165'][0]
    doc_dec.update_stream(rows_dec, re.sub(rb'/X\d+\s+Do', b'', doc_dec.xref_stream(rows_dec)))
    decor = _png(page_dec, alpha=True)
    _png(page_bg, alpha=False).convert('RGB').save(out / 'calendar_bg.png')

    # Texture: titolo e numero di ogni riga.
    plate, rect = _plate(source, 'X169', None, 'X169')
    plate.save(out / 'calendar_title_ink.png')
    meta = {'bg': 'calendar_bg.png',
            'title': {'base': title_base, 'size': title_size, 'left': title_left, 'right': title_right,
                      'center': round((title_left + title_right) / 2, 2), 'color': '#000000',
                      'ink': 'calendar_title_ink.png', 'ink_rect': rect},
            'logo_x': logo_x, 'logo_size': logo_size, 'logo_color': logo_color, 'rows': []}
    logo_tops = sorted({b[1] for b in logo_boxes if b[2] - b[0] < 130})
    for k, (form, day) in enumerate(zip(number_forms, days)):
        plate, rect = _plate(source, 'X165', form, form)
        file = f'calendar_day_{k + 1}.png'
        plate.save(out / file)
        top = min(logo_tops, key=lambda t: abs(t - (day['base'] - 102.6)))
        meta['rows'].append({**day, 'ink': file, 'ink_rect': rect, 'logo_top': top})
    # Una riga di decorazioni: dalla prima riga fino a metà strada verso la seconda.
    k = OUT_W / 1080
    first, second = meta['rows'][0]['base'], meta['rows'][1]['base']
    band = (round((first - 120) * k), round((first + (second - first) * 0.62) * k))
    row = decor.crop((0, band[0], OUT_W, band[1]))
    alpha = row.getchannel('A')
    sums = [sum(alpha.crop((0, y, OUT_W, y + 1)).getdata()) for y in range(row.height)]
    line_y = max(range(row.height), key=sums.__getitem__)
    row = row.crop((0, 0, OUT_W, min(row.height, line_y + 8)))
    rb = row.getchannel('A').getbbox()
    row = row.crop(rb)
    row.save(out / 'calendar_row.png')
    meta['row'] = {'file': 'calendar_row.png', 'x': rb[0] / k, 'dy': (band[0] + rb[1]) / k - first,
                   'w': (rb[2] - rb[0]) / k, 'h': (rb[3] - rb[1]) / k}
    meta['bg'] = 'calendar_bg.png'
    (out / 'calendar.json').write_text(json.dumps(meta, indent=1), encoding='utf-8')
    print('OK calendario:', len(meta['rows']), 'righe; loghi', logo_x, logo_size, logo_color)
    for r in meta['rows']:
        print('  ', r['text'], 'base', r['base'], 'logo top', r['logo_top'])


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('pdf', type=Path)
    parser.add_argument('out', type=Path)
    args = parser.parse_args()
    with pymupdf.open(args.pdf) as source:
        build(source, args.out)


if __name__ == '__main__':
    main()
