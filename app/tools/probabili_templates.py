"""Pezzi fissi delle PROBABILI FORMAZIONI dal PDF Canva (pagine 3, 8, 13).

Per ogni maglia:
  probabili_<kit>_bg.png      campo, titolo, JR (senza carte e loghi)
  probabili_<kit>_plates.png  lastre sfumate dietro la testa (una carta)
  probabili_<kit>_label.png   etichetta vuota (box + ombra, senza nome)
  probabili_<kit>_ink.png     texture del nome (solo third: oro)
  probabili.json              misure, colori, posizioni dei moduli Canva

Uso:
    python tools/probabili_templates.py _canva_ref/design.pdf ../LiveScore_Assets_JR/canva
"""
import argparse
import io
import json
import re
from collections import Counter
from pathlib import Path

import numpy as np
import pymupdf
from PIL import Image, ImageFilter

OUT_W, OUT_H = 1920, 2560
S = 1080 / 810          # punti PDF -> pixel design
U = 3.125               # unità contenuto pagina -> pixel design
PAGES = {'home': (3, 4, 5), 'away': (8, 9, 10), 'third': (13, 14, 15)}


def _page(source, n):
    doc = pymupdf.open()
    doc.insert_pdf(source, from_page=n - 1, to_page=n - 1)
    return doc, doc[0]


def _structure(doc, page):
    """Nomi dei blocchi: carte (gruppi di 4), loghi."""
    data = doc.xref_stream(page.get_contents()[0])
    order = [n.decode() for n in re.findall(rb'/(X\d+) Do', data)]
    forms = {x[1]: x for x in page.get_xobjects() if x[2] == 0}
    images = {x[7]: x for x in page.get_images(full=True) if x[9] == 0}
    label_names = [n for n in order if n in images and images[n][2] > 800 and images[n][3] < 700]
    cards = []
    for label in label_names:
        i = order.index(label)
        cards.append(order[i - 3:i + 1])          # lastra A, lastra B, testa, etichetta
    logos = [n for n in order if n in forms and 280 < forms[n][3][2] < 320]
    return data, order, cards, logos, images


def _keep_only(doc, page, data, keep, background=True):
    def repl(m):
        return m.group(0) if m.group(1).decode() in keep else b''
    out = re.sub(rb'/(X\d+)\s+Do', repl, data)
    if not background:
        out = re.sub(rb'(0 0 1080 1440 re)\s+f\b', rb'\1 n', out)
    doc.update_stream(page.get_contents()[0], out)


def _png(page, alpha):
    z = OUT_W / page.rect.width
    return Image.open(io.BytesIO(page.get_pixmap(matrix=pymupdf.Matrix(z, z), alpha=alpha).tobytes('png')))


def _image(doc, xref, smask):
    pix = pymupdf.Pixmap(doc, xref)
    if smask:
        pix = pymupdf.Pixmap(pix, pymupdf.Pixmap(doc, smask))
    if pix.colorspace and pix.colorspace.n != 3:
        pix = pymupdf.Pixmap(pymupdf.csRGB, pix)
    return Image.open(io.BytesIO(pix.tobytes('png'))).convert('RGBA')


def _rect(page, xref):
    return [round(v * S, 3) for v in page.get_image_rects(xref)[0]]


def _label_parts(label):
    """Box scuro dell'etichetta, maschera del testo e colore del box."""
    a = np.asarray(label).astype(np.float32)
    alpha = a[..., 3]
    lum = a[..., :3].mean(axis=2)
    solid = alpha > 250
    box_lum = np.median(lum[solid])
    box_color = np.median(a[solid][:, :3], axis=0)
    ys, xs = np.where(solid)
    box = (int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1)
    ink = solid & (lum > box_lum + 6)
    return box, box_color, ink


def build(source, out):
    meta = {'modules': {}}
    for kit, pages in PAGES.items():
        doc, page = _page(source, pages[0])
        data, order, cards, logos, images = _structure(doc, page)
        if len(cards) != 11:
            raise ValueError(f'{kit}: trovate {len(cards)} carte invece di 11')

        # Sfondo: tutto tranne carte e loghi.
        drop = {n for c in cards for n in c} | set(logos)
        doc_bg, page_bg = _page(source, pages[0])
        _keep_only(doc_bg, page_bg, data, set(order) - drop)
        _png(page_bg, alpha=False).convert('RGB').save(out / f'probabili_{kit}_bg.png')

        # Etichetta del portiere come riferimento.
        gk = cards[0]
        label_img = images[gk[3]]
        label_rect = _rect(page, label_img[0])
        label = _image(doc, label_img[0], label_img[1])
        box, box_color, _ink = _label_parts(label)
        kx = (label_rect[2] - label_rect[0]) / label.width
        ky = (label_rect[3] - label_rect[1]) / label.height
        box_design = [label_rect[0] + box[0] * kx, label_rect[1] + box[1] * ky,
                      label_rect[0] + box[2] * kx, label_rect[1] + box[3] * ky]
        anchor = ((box_design[0] + box_design[2]) / 2, box_design[1])   # centro alto del box

        # Nome del portiere: altezza maiuscole e linea di base rispetto al box.
        _b, _c, gk_ink = _label_parts(label)
        arr = np.asarray(label).astype(np.float32)
        lum = arr[..., :3].mean(axis=2)
        core = gk_ink & (lum >= np.percentile(lum[gk_ink], 50))
        ys, xs = np.where(core)
        cap_h = (ys.max() + 1 - ys.min()) * ky
        text_base = label_rect[1] + (ys.max() + 1) * ky - anchor[1]
        text_cx = label_rect[0] + (xs.min() + xs.max() + 1) / 2 * kx - anchor[0]

        # Testo: colore del centro delle lettere su tutte le 11 etichette.
        # Uniforme -> colore pieno; altrimenti sfumatura liscia (u, v nel box).
        us, vs, cols = [], [], []
        for card in cards:
            img = images[card[3]]
            lab = _image(doc, img[0], img[1])
            b, _c, ink = _label_parts(lab)
            arr = np.asarray(lab).astype(np.float32)
            lum = arr[..., :3].mean(axis=2)
            core = ink & (lum >= np.percentile(lum[ink], 60))
            yy, xx = np.where(core)
            us.append((xx - b[0]) / (b[2] - b[0])); vs.append((yy - b[1]) / (b[3] - b[1]))
            cols.append(arr[core][:, :3])
        u, v, c = np.concatenate(us), np.concatenate(vs), np.concatenate(cols)
        spread = float(c.std(axis=0).mean())
        if spread < 10:
            text = {'color': '#%02x%02x%02x' % tuple(int(x) for x in np.median(c, axis=0))}
        else:
            terms = lambda u, v: np.stack([np.ones_like(u), u, v, u * u, v * v, u * v], axis=1)
            coef, *_ = np.linalg.lstsq(terms(u, v), c, rcond=None)
            w, h = box[2] - box[0], box[3] - box[1]
            gu, gv = np.meshgrid((np.arange(w) + 0.5) / w, (np.arange(h) + 0.5) / h)
            tex = (terms(gu.ravel(), gv.ravel()) @ coef).clip(0, 255).reshape(h, w, 3)
            Image.fromarray(tex.astype(np.uint8)).save(out / f'probabili_{kit}_ink.png')
            text = {'texture': f'probabili_{kit}_ink.png'}
        print(f'   {kit}: variazione colore testo {spread:.1f}')

        # Etichetta vuota: testo e bordi del testo ricoperti col colore del box.
        clean = np.asarray(label).copy()
        ink_ref = _label_parts(label)[2]
        grow = np.asarray(Image.fromarray((ink_ref * 255).astype(np.uint8)).filter(ImageFilter.MaxFilter(5))) > 0
        clean[grow, :3] = box_color.astype(np.uint8)
        clean[grow, 3] = 255
        Image.fromarray(clean).save(out / f'probabili_{kit}_label.png')

        # Lastre dietro la testa (solo la prima carta), su fondo trasparente.
        doc2, page2 = _page(source, pages[0])
        data2 = doc2.xref_stream(page2.get_contents()[0])
        _keep_only(doc2, page2, data2, set(gk[:2]), background=False)
        plates = _png(page2, alpha=True)
        pbox = plates.getchannel('A').getbbox()
        plates.crop(pbox).save(out / f'probabili_{kit}_plates.png')
        k = 1080 / OUT_W
        plates_rect = [pbox[0] * k, pbox[1] * k, pbox[2] * k, pbox[3] * k]

        # Testa del portiere: riquadro rispetto al box.
        head = [x for x in page.get_image_info(xrefs=True) if x['width'] == x['height'] == 650]
        head_rect = min(([round(v * S, 3) for v in h['bbox']] for h in head),
                        key=lambda r: abs((r[0] + r[2]) / 2 - anchor[0]) + abs(r[3] - anchor[1] - 23))

        # Loghi in basso: posizione e colore.
        logo_boxes, logo_color = [], None
        for name in logos:
            m = re.search(rb'1 0 0 1 ([\d.\-]+) ([\d.\-]+) cm[^Q]*?/' + name.encode() + rb' Do', data)
            logo_boxes.append([float(m.group(1)) / U, float(m.group(2)) / U, 297.95663 / U])
            child = [i for i in page.get_images(full=True) if i[9] == [f for f in page.get_xobjects() if f[1] == name][0][0]][0]
            img = _image(doc, child[0], child[1])
            solid = Counter(px[:3] for px in img.getdata() if px[3] > 250)
            logo_color = logo_color or '#%02x%02x%02x' % solid.most_common(1)[0][0]

        rel = lambda r: [r[0] - anchor[0], r[1] - anchor[1], r[2] - r[0], r[3] - r[1]]
        meta[kit] = {
            'bg': f'probabili_{kit}_bg.png',
            'label': f'probabili_{kit}_label.png', 'label_rect': rel(label_rect),
            'box': rel(box_design),
            'plates': f'probabili_{kit}_plates.png', 'plates_rect': rel(plates_rect),
            # Stessa disposizione in tutte le maglie: la testa si misura sulla home.
            'head_rect': meta['home']['head_rect'] if kit != 'home' else rel(head_rect),
            'text': {**text, 'cap': round(cap_h, 2), 'base': round(text_base, 2), 'cx': round(text_cx, 2)},
            'logos': logo_boxes, 'logo_color': logo_color,
        }
        print(f'OK probabili {kit}: testo {text}, loghi {logo_color}, box {[round(v, 1) for v in rel(box_design)]}')

        # Moduli Canva (posizioni delle carte) dalle tre pagine della maglia home.
        if kit == 'home':
            for module, n in zip(('4-2-3-1', '3-4-2-1', '3-4-1-2'), pages):
                d3, p3 = _page(source, n)
                _data, _o, cards3, _l, imgs3 = _structure(d3, p3)
                slots = []
                for card in cards3:
                    r = _rect(p3, imgs3[card[3]][0])
                    lab = _image(d3, imgs3[card[3]][0], imgs3[card[3]][1])
                    b, _c, _i = _label_parts(lab)
                    kx3 = (r[2] - r[0]) / lab.width
                    cx = r[0] + (b[0] + b[2]) / 2 * kx3
                    # Etichette tagliate dal bordo pagina: centro dalla testa.
                    heads3 = [[v * S for v in h['bbox']] for h in p3.get_image_info(xrefs=True)
                              if h['width'] == h['height'] == 650]
                    top = r[1] + b[1] * (r[3] - r[1]) / lab.height
                    hx = min(heads3, key=lambda h: abs(h[3] - top - head_rect[3] + anchor[1]) + abs((h[0] + h[2]) / 2 - cx))
                    slots.append([round((hx[0] + hx[2]) / 2, 2), round(top, 2)])
                meta['modules'][module] = slots
                print(f'   modulo {module}: {slots}')

    (out / 'probabili.json').write_text(json.dumps(meta, indent=1), encoding='utf-8')


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('pdf', type=Path)
    parser.add_argument('out', type=Path)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    with pymupdf.open(args.pdf) as source:
        build(source, args.out)


if __name__ == '__main__':
    main()
