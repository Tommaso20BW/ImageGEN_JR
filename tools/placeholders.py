"""Sagome fisse per l'editor foto (Starting XI, Matchday, Foto + JR).

Non contengono dati veri: sfumature e titolo Canva + riquadri tratteggiati dove
andranno loghi, numeri, nomi e riga info. Servono solo a posizionare la foto.
Una immagine 540x720 per grafica e maglia: canva/<nome>_<maglia>_placeholder.png

Uso: python tools/placeholders.py ../LiveScore_Assets_JR/canva
"""
import json
import sys
from pathlib import Path

from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from graphics import matchday as md, starting_xi as sx  # noqa: E402

W, H = 540, 720
K = W / 1080            # pixel design -> sagoma


def _rgb(hex_color):
    h = hex_color.lstrip('#')
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def _box(draw, x0, y0, x1, y1, color, radius=6):
    """Riquadro tratteggiato semitrasparente."""
    box = [round(x0 * K), round(y0 * K), round(x1 * K), round(y1 * K)]
    draw.rounded_rectangle(box, radius=radius, fill=color + (70,))
    x0, y0, x1, y1 = box
    dash, gap = 6, 4
    for x in range(x0, x1, dash + gap):
        draw.line([(x, y0), (min(x + dash, x1), y0)], fill=color + (200,), width=1)
        draw.line([(x, y1), (min(x + dash, x1), y1)], fill=color + (200,), width=1)
    for y in range(y0, y1, dash + gap):
        draw.line([(x0, y), (x0, min(y + dash, y1))], fill=color + (200,), width=1)
        draw.line([(x1, y), (x1, min(y + dash, y1))], fill=color + (200,), width=1)


def _base(canva, kit_meta):
    """Sfumature (crema per la home) + titolo e JR, ridotti a 540x720."""
    fx = Image.open(canva / kit_meta['fx']).convert('RGBA')
    if kit_meta.get('fx_light'):
        import numpy as np
        from graphics.common import HOME_FX_COLOR
        a = np.asarray(fx).astype(float)
        solid = a[..., 3] > 240
        base = np.median(a[solid][:, :3], axis=0)
        a[..., :3] = np.clip(a[..., :3] * (np.array(HOME_FX_COLOR) / base), 0, 255)
        fx = Image.fromarray(a.astype('uint8'), 'RGBA')
    text = Image.open(canva / kit_meta['text_overlay']).convert('RGBA')
    fx.alpha_composite(text)
    return fx.resize((W, H), Image.LANCZOS)


def starting_xi(canva, out):
    meta = json.loads((canva / 'starting_xi.json').read_text(encoding='utf-8'))
    for kit, km in meta.items():
        img = _base(canva, km)
        d = ImageDraw.Draw(img)
        color = _rgb(km['logo_color'])
        for x, y in sx.LOGO_BOXES:
            _box(d, x + 14, y + 14, x + sx.LOGO_SIZE - 14, y + sx.LOGO_SIZE - 14, color, radius=10)
        widths = (150, 120, 160, 135, 145, 185, 230, 240, 175, 210, 200)     # nomi di lunghezze diverse
        for k, w in enumerate(widths):
            base = sx.NAME_BASE + k * sx.ROW_STEP
            _box(d, sx.NUMBER_RIGHT - 70, base - 62, sx.NUMBER_RIGHT, base, color)
            _box(d, sx.NAME_X, base - 50, sx.NAME_X + w, base, color)
        img.save(out / f'starting_xi_{kit}_placeholder.png', optimize=True)
        print('OK starting_xi', kit)


def matchday(canva, out):
    meta = json.loads((canva / 'matchday.json').read_text(encoding='utf-8'))
    for kit, km in meta.items():
        img = _base(canva, km)
        d = ImageDraw.Draw(img)
        color = _rgb(km['logo_color'])
        for x, y in md.LOGO_BOXES:
            _box(d, x + 12, y + 12, x + md.LOGO_SIZE - 12, y + md.LOGO_SIZE - 12, color, radius=10)
        for slot in ('stadium', 'competition', 'time', 'date'):
            cx = md.CENTERS[slot]
            _box(d, cx - 80, md.INFO_BASE - 18, cx + 80, md.INFO_BASE + 3, color, radius=4)
        img.save(out / f'matchday_{kit}_placeholder.png', optimize=True)
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
