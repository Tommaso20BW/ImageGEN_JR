"""Crea gli sfondi dei modelli ImageGEN dal PDF del design Canva.

Ogni modello è una pagina del design JUVENTUS REBORN 2.0 da cui si tolgono
le parti che cambiano (nomi, loghi, foto...). Il resto resta identico a Canva.

Uso (in locale, dopo aver scaricato il PDF da Canva > Scarica > PDF):
    python tools/canva_templates.py _canva_ref/design.pdf ../LiveScore_Assets_JR/canva

Se modifichi il design su Canva, riscarica il PDF e rilancia lo script.
"""
import argparse
import io
import json
import re
from collections import Counter
from pathlib import Path

import pymupdf
from PIL import Image

# Misure di output: 3:4 come le altre grafiche HD di ImageGEN.
OUT_W, OUT_H = 1920, 2560
DESIGN_W = 1080

# ---------------------------------------------------------------------------
# Modelli "piatti": la pagina meno testi e immagini variabili.
#   fonts:  testi con questi font vengono rimossi
#   images: immagini il cui riquadro (in punti PDF, pagina 810x1080) sta
#           tutto dentro questa zona vengono rimosse
#   bg:     sostituisce lo sfondo a pagina intera con questa immagine degli asset
#   paper:  ricolora il foglio di carta (colore medio RGB), nastro escluso
SQUAD_LIST = {
    'fonts': ('BebasNeue', 'Allogist'),        # nomi e titolo li scrive ImageGEN
    'images': [(300, 880, 510, 1000)],
}

FLAT = {
    'squad_list_serie_a': (17, SQUAD_LIST),
    'squad_list_coppa_italia': (18, SQUAD_LIST),
    'squad_list_europa_league': (19, SQUAD_LIST),
    # Non su Canva: stile Europa League con sfondi e colori della competizione.
    'squad_list_champions_league': (17, {**SQUAD_LIST, 'bg': 'portrait/ucl_clean_1086x1448.png',
                                         'paper': (14, 24, 82)}),      # pagina con JR bianco
    'squad_list_conference_league': (19, {**SQUAD_LIST, 'bg': 'portrait/conference_clean_1086x1448.png',
                                          'paper': (16, 56, 33)}),
}

# Modelli "a livelli": foto (caricata dall'utente) sotto, livello fisso sopra,
# loghi e testi generati. Pagina Canva per ogni maglia.
LAYERED = {
    'starting_xi': {'home': 6, 'away': 11, 'third': 16},
    'matchday': {'home': 2, 'away': 7, 'third': 12},
}

# Solo logo JR (foto + JR: compleanni, MOTM, foto libere). Colore -> pagina
# in cui il JR ha quel colore (pagine con i testi dentro i blocchi).
JR_PAGES = {'black': 6, 'white': 11, 'gold': 16}

# Testi variabili scritti direttamente nella pagina (non in un blocco):
# font da togliere, fascia verticale (pixel design) e centri dei riquadri.
PAGE_TEXT = {
    'matchday': {
        'font': 'Nimbus',
        'band': (1380, 1440),
        'slots': {'stadium': 132.87, 'sep1': 270.31, 'competition': 404.18, 'sep2': 542.31,
                  'time': 674.18, 'sep3': 816.31, 'date': 948.43},
    },
}


def _inside(rect, zone):
    x0, y0, x1, y1 = zone
    return rect.x0 >= x0 and rect.y0 >= y0 and rect.x1 <= x1 and rect.y1 <= y1


def _single_page(source, page_number):
    doc = pymupdf.open()
    doc.insert_pdf(source, from_page=page_number - 1, to_page=page_number - 1)
    return doc, doc[0]


def _png(page, alpha):
    zoom = OUT_W / page.rect.width
    pix = page.get_pixmap(matrix=pymupdf.Matrix(zoom, zoom), alpha=alpha)
    if (pix.width, pix.height) != (OUT_W, OUT_H):
        raise ValueError(f'Misura inattesa {pix.width}x{pix.height}')
    return pix


def _recolor_paper(doc, img, tint):
    """Foglio di carta ricolorato: stessa texture, nastro adesivo invariato."""
    import numpy as np
    pix = pymupdf.Pixmap(pymupdf.Pixmap(doc, img[0]), pymupdf.Pixmap(doc, img[1]))
    if pix.colorspace and pix.colorspace.n != 3:
        pix = pymupdf.Pixmap(pymupdf.csRGB, pix)
    rgba = np.asarray(Image.open(io.BytesIO(pix.tobytes('png'))).convert('RGBA')).astype(float)
    rgb, alpha = rgba[..., :3], rgba[..., 3]
    lum = rgb.mean(axis=2)
    paper = (alpha > 250) & (lum < np.percentile(lum[alpha > 250], 80))
    shade = lum / lum[paper].mean()                               # texture: luce/ombra della carta
    tinted = shade[..., None] * np.array(tint, dtype=float)
    weight = np.clip((150 - lum) / 70, 0, 1)[..., None]          # zone chiare (nastro) invariate
    out = np.clip(rgb * (1 - weight) + tinted * weight, 0, 255)
    image = Image.fromarray(np.dstack([out, alpha]).astype('uint8'), 'RGBA')
    buf = io.BytesIO(); image.save(buf, format='PNG')
    return pymupdf.Pixmap(buf.getvalue())


def _background(path):
    """Sfondo competizione (asset 'portrait'): il pannello scuro centrale sbucherebbe
    sopra e sotto il foglio. Si stringe in verticale il pannello (finisce tutto
    sotto il foglio) e si allungano le fasce del bordo: strisce continue, senza copie."""
    image = Image.open(path).convert('RGB')
    w, h = image.size
    top, bottom = 76, 1371                   # bordi del pannello (foto 1086x1448)
    new_top, new_bottom = 128, 1336          # dentro il foglio di carta (che va da ~122 a ~1343)
    out = Image.new('RGB', (w, h))
    for (y0, y1), (t0, t1) in (((0, top), (0, new_top)), ((top, bottom), (new_top, new_bottom)),
                               ((bottom, h), (new_bottom, h))):
        out.paste(image.crop((0, y0, w, y1)).resize((w, t1 - t0), Image.LANCZOS), (0, t0))
    buf = io.BytesIO(); out.save(buf, format='PNG')
    return buf.getvalue()


def clean_page(source, page_number, spec, assets=None):
    """Ritorna i byte PNG della pagina senza le parti variabili."""
    doc, page = _single_page(source, page_number)

    if spec.get('bg') or spec.get('paper'):
        for img in page.get_images(full=True):
            if img[2] == 1086 and img[3] == 1448:
                if not img[1] and spec.get('bg'):
                    page.replace_image(img[0], stream=_background(assets / spec['bg']))
                elif img[1] and spec.get('paper'):
                    page.replace_image(img[0], pixmap=_recolor_paper(doc, img, spec['paper']))

    for xref, *_ in page.get_images(full=True):
        rects = page.get_image_rects(xref)
        if rects and all(any(_inside(r, z) for z in spec.get('images', ())) for r in rects):
            page.delete_image(xref)

    fonts = spec.get('fonts', ())
    removed = 0
    for block in page.get_text('dict')['blocks']:
        for line in block.get('lines', []):
            for span in line['spans']:
                if any(f in span['font'] for f in fonts):
                    page.add_redact_annot(pymupdf.Rect(span['bbox']), fill=False)
                    removed += 1
    if removed:
        page.apply_redactions(
            images=pymupdf.PDF_REDACT_IMAGE_NONE,
            graphics=pymupdf.PDF_REDACT_LINE_ART_NONE,
            text=pymupdf.PDF_REDACT_TEXT_REMOVE,
        )
    return _png(page, alpha=False).tobytes('png')


# ---------------------------------------------------------------------------
# Modelli a livelli

class _Tree:
    """Albero dei blocchi (XObject) della pagina."""

    def __init__(self, page):
        self.page = page
        self.doc = page.parent
        self.forms = {}      # xref -> (nome, xref genitore o 0)
        for xref, name, parent, _bbox in page.get_xobjects():
            self.forms[xref] = (name, parent)
        self.images = []     # (xref, nome, genitore, larghezza, altezza)
        for x in page.get_images(full=True):
            self.images.append((x[0], x[7], x[9], x[2], x[3]))
        self.fonts = [(f[3], f[6]) for f in page.get_fonts(full=True)]

    def top(self, xref):
        while self.forms.get(xref, ('', 0))[1]:
            xref = self.forms[xref][1]
        return xref

    def ancestors(self, xref):
        out = [xref]
        while self.forms.get(xref, ('', 0))[1]:
            xref = self.forms[xref][1]
            out.append(xref)
        return out

    def children(self, parent):
        names = [n for x, (n, p) in self.forms.items() if p == parent]
        names += [n for _x, n, p, _w, _h in self.images if p == parent]
        return names

    def name(self, xref):
        return self.forms[xref][0]

    def roles(self):
        """Foto, gruppo loghi e gruppo testi (nomi + numeri)."""
        # Foto = immagine verticale più grande (le copie quadrate 2400x2400 sono effetti).
        page_images = [i for i in self.images if i[2] == 0 and i[4] > i[3]]
        photo = max(page_images, key=lambda i: i[3] * i[4])
        logo_parents = {self.top(i[2]) for i in self.images
                        if i[2] and i[3] == i[4] and 300 <= i[3] <= 800}
        text_forms = {self.top(ref) for name, ref in self.fonts if 'Bebas' in name and ref}
        if len(logo_parents) != 1 or len(text_forms) > 1:
            raise ValueError(f'Livelli ambigui: loghi {logo_parents}, testi {text_forms}')
        return photo[1], self.name(logo_parents.pop()), (text_forms.pop() if text_forms else None)


def _page_streams(page):
    return page.get_contents()


def _drop_do(doc, xref, names):
    data = doc.xref_stream(xref)
    for name in names:
        data = re.sub(rb'/' + name.encode() + rb'\s+Do', b'', data)
    doc.update_stream(xref, data)


def _no_background(doc, page):
    for xref in _page_streams(page):
        data = re.sub(rb'(0 0 1080 1440 re)\s+f\b', rb'\1 n', doc.xref_stream(xref))
        doc.update_stream(xref, data)


def _pattern_sections(data):
    return list(re.finditer(rb'/Pattern cs.*?/P\d+ scn.*?(BT.*?ET)', data, re.S))


def _row_plate(source, page_number, target_form_name, keep_section):
    """Texture della riga `keep_section` (tutta piena, senza forma del testo)."""
    doc, page = _single_page(source, page_number)
    tree = _Tree(page)
    target = next(x for x, (n, _p) in tree.forms.items() if n == target_form_name)
    keep = set(tree.ancestors(target))
    keep_names = {tree.name(x) for x in keep}

    _no_background(doc, page)
    for xref in _page_streams(page):
        others = [n for n in tree.children(0) if n not in keep_names]
        _drop_do(doc, xref, others)
    for form in keep:
        if form != target:
            _drop_do(doc, form, [n for n in tree.children(form) if n not in keep_names])

    data = doc.xref_stream(target)
    for i, match in reversed(list(enumerate(_pattern_sections(data)))):
        fill = b'-2000 -2000 6000 6000 re f' if i == keep_section else b''
        data = data[:match.start(1)] + fill + data[match.end(1):]
    doc.update_stream(target, data)

    image = Image.open(io.BytesIO(_png(page, alpha=True).tobytes('png')))
    box = image.getchannel('A').getbbox()
    return image.crop(box), box


def _solid_color(doc, form_xref, data=None):
    data = doc.xref_stream(form_xref) if data is None else data
    found = re.findall(rb'([\d.]+) ([\d.]+) ([\d.]+) rg', data)
    r, g, b = (round(float(v) * 255) for v in found[-1])
    return f'#{r:02x}{g:02x}{b:02x}'


def _page_stream(doc, page):
    return b''.join(doc.xref_stream(x) for x in _page_streams(page))


def _set_page_stream(doc, page, data):
    xrefs = _page_streams(page)
    doc.update_stream(xrefs[0], data)
    for xref in xrefs[1:]:
        doc.update_stream(xref, b'')


def _clip_before(data, at):
    clips = list(re.finditer(rb'([\d.\-]+) ([\d.\-]+) ([\d.\-]+) ([\d.\-]+) re\s+W\*?\s+n', data[:at]))
    x, _y, w, _h = (float(v) for v in clips[-1].groups())
    return (x + w / 2) / 3.125, clips[-1]


def _page_text_plate(source, page_number, keep_section, band):
    """Texture di un testo scritto nella pagina, allargata a tutta la riga."""
    doc, page = _single_page(source, page_number)
    _no_background(doc, page)
    data = re.sub(rb'/X\d+\s+Do', b'', _page_stream(doc, page))
    section = _pattern_sections(data)[keep_section]
    keep = (section.start(1), section.end(1))
    _center, clip = _clip_before(data, section.start())
    # Riquadro di ritaglio esteso a tutta la fascia: i testi lunghi non vengono tagliati.
    data = data[:clip.start()] + b'-10 4000 3400 500 re W n' + data[clip.end():]
    shift = len(b'-10 4000 3400 500 re W n') - (clip.end() - clip.start())
    keep = (keep[0] + shift, keep[1] + shift)
    out, last = [], 0
    for bt in re.finditer(rb'BT.*?ET', data, re.S):
        out.append(data[last:bt.start()])
        out.append(b'-2000 -2000 6000 6000 re f' if (bt.start(), bt.end()) == keep else b'')
        last = bt.end()
    out.append(data[last:])
    _set_page_stream(doc, page, b''.join(out))
    image = Image.open(io.BytesIO(_png(page, alpha=True).tobytes('png')))
    k = OUT_W / DESIGN_W
    top = round(band[0] * k)
    image = image.crop((0, top, OUT_W, round(band[1] * k)))
    box = image.getchannel('A').getbbox()
    return image.crop(box), (box[0], box[1] + top, box[2], box[3] + top)


def _page_text(source, page_number, doc, page, spec, name, kit, out):
    """Stile dei testi scritti nella pagina, per riquadro (stadio, competizione...)."""
    scale = DESIGN_W / OUT_W
    data = _page_stream(doc, page)
    slots = spec['slots']
    sections = _pattern_sections(data)
    result = {}
    for k, section in enumerate(sections):
        center, _clip = _clip_before(data, section.start())
        slot = min(slots, key=lambda s: abs(slots[s] - center))
        plate, box = _page_text_plate(source, page_number, k, spec['band'])
        file = f'{name}_{kit}_{slot}.png'
        plate.save(out / file)
        result[slot] = {'file': file, 'x': box[0] * scale, 'y': box[1] * scale,
                        'w': (box[2] - box[0]) * scale, 'h': (box[3] - box[1]) * scale}
    textured = {s.start(1) for s in sections}
    plain = [m for m in re.finditer(rb'BT.*?ET', data, re.S) if m.start() not in textured]
    color = _solid_color(doc, None, data[:plain[0].start()]) if plain else '#ffffff'
    for slot in slots:
        result.setdefault(slot, {'color': color})
    return result


def build_layered(source, name, pages, out):
    meta = {}
    scale = DESIGN_W / OUT_W
    for kit, page_number in pages.items():
        doc, page = _single_page(source, page_number)
        tree = _Tree(page)
        photo, logos, text_group = tree.roles()
        page_spec = PAGE_TEXT.get(name)
        info = _page_text(source, page_number, doc, page, page_spec, name, kit, out) if page_spec else None

        # Colore dei loghi: il colore più frequente dei pixel pieni del logo su Canva.
        logo_img = next(i for i in tree.images if i[2] and i[3] == i[4] and 300 <= i[3] <= 800)
        pix = pymupdf.Pixmap(doc, logo_img[0])
        if logo_img[0] and doc.xref_get_key(logo_img[0], 'SMask')[0] == 'xref':
            mask = int(doc.xref_get_key(logo_img[0], 'SMask')[1].split()[0])
            pix = pymupdf.Pixmap(pix, pymupdf.Pixmap(doc, mask))
        if pix.colorspace and pix.colorspace.n != 3:
            pix = pymupdf.Pixmap(pymupdf.csRGB, pix)
        rgba = Image.open(io.BytesIO(pix.tobytes('png'))).convert('RGBA')
        solid = Counter(p[:3] for p in rgba.getdata() if p[3] > 250)
        logo_color = '#%02x%02x%02x' % solid.most_common(1)[0][0]

        # Copie della foto usate da Canva per effetti (ritagli 2400x2400): via ovunque.
        photo_copies = sorted({n for _x, n, _p, w, h in tree.images if (w, h) == (2400, 2400)})

        # Livello "solo scritte" per l'editor: titolo (blocchi con font) e logo JR.
        title_forms = {tree.name(tree.top(ref)) for fname, ref in tree.fonts
                       if ref and tree.top(ref) != text_group}
        jr = [n for _x, n, p, w, h in tree.images if p == 0 and w < 400 and h < 600]
        doc_t, page_t = _single_page(source, page_number)
        _no_background(doc_t, page_t)
        data = b''.join(doc_t.xref_stream(x) for x in _page_streams(page_t))
        keep = title_forms | set(jr)
        data = re.sub(rb'/(X\d+)\s+Do', lambda m: m.group(0) if m.group(1).decode() in keep else b'', data)
        data = re.sub(rb'BT.*?ET', b'', data, flags=re.S)        # testi della pagina (riga info): li scrive ImageGEN
        xrefs = _page_streams(page_t)
        doc_t.update_stream(xrefs[0], data)
        for x in xrefs[1:]:
            doc_t.update_stream(x, b'')
        for form, (fname, _p) in _Tree(page_t).forms.items():
            if photo_copies:
                _drop_do(doc_t, form, photo_copies)
        text_overlay = f'{name}_{kit}_text.png'
        _png(page_t, alpha=True).save(str(out / text_overlay))

        # Livello fisso: tutto tranne foto, loghi, testi e fondo pagina.
        _no_background(doc, page)
        for xref in _page_streams(page):
            _drop_do(doc, xref, [photo, logos] + photo_copies + ([tree.name(text_group)] if text_group else []))
        for form in tree.forms:
            if photo_copies:
                _drop_do(doc, form, photo_copies)
        if page_spec:
            for block in page.get_text('dict')['blocks']:
                for line in block.get('lines', []):
                    for span in line['spans']:
                        if page_spec['font'] in span['font']:
                            page.add_redact_annot(pymupdf.Rect(span['bbox']), fill=False)
            page.apply_redactions(images=pymupdf.PDF_REDACT_IMAGE_NONE,
                                  graphics=pymupdf.PDF_REDACT_LINE_ART_NONE,
                                  text=pymupdf.PDF_REDACT_TEXT_REMOVE)
        overlay = f'{name}_{kit}_overlay.png'
        _png(page, alpha=True).save(str(out / overlay))

        # Solo sfumature e grana (senza titolo e JR): si può ricolorare sulla foto.
        for xref in _page_streams(page):
            _drop_do(doc, xref, sorted(keep))
        fx_img = Image.open(io.BytesIO(_png(page, alpha=True).tobytes('png')))
        fx = f'{name}_{kit}_fx.png'
        fx_img.save(out / fx)
        import numpy as np
        a = np.asarray(fx_img.convert('RGBA')).astype(float)
        strong = a[..., 3] > 128
        fx_light = bool(strong.any() and a[strong][:, :3].mean() > 200)

        # Testi: colore pieno oppure texture riga per riga.
        text = {}
        for form, (form_name, _p) in tree.forms.items():
            if not text_group or tree.top(form) != text_group or form == text_group:
                continue
            fonts = {n for n, ref in tree.fonts if ref == form}
            role = 'number' if any('Allogist' in f for f in fonts) else 'name'
            data = doc.xref_stream(form)
            sections = _pattern_sections(data)
            if not sections:
                text[role] = {'color': _solid_color(doc, form)}
                continue
            rows = []
            for k in range(len(sections)):
                plate, box = _row_plate(source, page_number, form_name, k)
                file = f'{name}_{kit}_{role}_{k + 1:02d}.png'
                plate.save(out / file)
                rows.append({'file': file, 'x': box[0] * scale, 'y': box[1] * scale,
                             'w': (box[2] - box[0]) * scale, 'h': (box[3] - box[1]) * scale})
            text[role] = {'rows': rows}

        meta[kit] = {'overlay': overlay, 'text_overlay': text_overlay, 'fx': fx, 'fx_light': fx_light,
                     'logo_color': logo_color, 'text': text}
        if info:
            meta[kit]['info'] = info
            text['info'] = {'color': ' '.join(
                v.get('color', 'texture') for v in info.values())}
        print(f'OK {name} {kit} (pagina {page_number}): '
              + ', '.join(f"{r}={'texture' if 'rows' in v else v['color']}" for r, v in text.items())
              + f', loghi {logo_color}')

    (out / f'{name}.json').write_text(json.dumps(meta, indent=1), encoding='utf-8')


def build_jr(source, out):
    """Livello trasparente con il solo logo JR, per ogni colore."""
    meta = {}
    for color, page_number in JR_PAGES.items():
        doc, page = _single_page(source, page_number)
        tree = _Tree(page)
        jr = [i for i in tree.images if i[2] == 0 and i[3] < 400 and i[4] < 600]
        if len(jr) != 1:
            raise ValueError(f'Logo JR non trovato a pagina {page_number}')
        _no_background(doc, page)
        data = _page_stream(doc, page)
        data = re.sub(rb'/(X\d+)\s+Do', lambda m: m.group(0) if m.group(1).decode() == jr[0][1] else b'', data)
        data = re.sub(rb'BT.*?ET', b'', data, flags=re.S)
        _set_page_stream(doc, page, data)
        file = f'jr_{color}_overlay.png'
        _png(page, alpha=True).save(str(out / file))
        meta[color] = {'overlay': file}
        print(f'OK jr {color} (pagina {page_number})')
    (out / 'jr.json').write_text(json.dumps(meta, indent=1), encoding='utf-8')


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('pdf', type=Path)
    parser.add_argument('out', type=Path)
    parser.add_argument('names', nargs='*', help='solo questi modelli (default: tutti)')
    args = parser.parse_args()

    args.out.mkdir(parents=True, exist_ok=True)
    with pymupdf.open(args.pdf) as source:
        for name, (page_number, spec) in FLAT.items():
            if args.names and name not in args.names:
                continue
            (args.out / f'{name}.png').write_bytes(clean_page(source, page_number, spec, args.out.parent))
            print(f'OK {name} (pagina {page_number})')
        if not args.names or 'jr' in args.names:
            build_jr(source, args.out)
        for name, pages in LAYERED.items():
            if args.names and name not in args.names:
                continue
            build_layered(source, name, pages, args.out)


if __name__ == '__main__':
    main()
