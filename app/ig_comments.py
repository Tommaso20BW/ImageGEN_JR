"""CITAZIONE IG: legge i commenti da uno o più screenshot di Instagram (RapidOCR, sul servizio:
le immagini non vanno a siti esterni). Ritorna nome e testo di ogni commento, da far scegliere
nella Mini App. Le emoji non si leggono: il testo si può correggere a mano.
"""
import base64
import io
import re
import threading
import unicodedata

import numpy as np
from PIL import Image, ImageOps

MAX_COMMENTS = 40
RIGHT_COLUMN = .82           # oltre questa parte della larghezza: cuore e numero di mi piace
_TIME = (r'(?:\d{1,3}\s*(?:sec|min|ore|ora|sett|mesi|mese|anni|anno|gg|s|m|h|g|d|w|y|a)\.?|ora|adesso|now)')
HEADER = re.compile(rf'^@?([A-Za-z0-9._]{{1,30}})\W*\s+[·•]?\s*({_TIME})(?:\s*[·•]?\s*(?:autore|author|modificato|edited))?\W*$', re.I)
# Nome e tempo letti come un pezzo solo ("antonio_189731 min" = antonio_1897, 31 min).
GLUED = re.compile(r'^@?([A-Za-z0-9._]{3,30}?)(\d{1,2}\s*(?:sec|min|ore|ora|sett|mesi|mese|anni|anno|gg|s|m|h|g|d|w|y|a)\.?)\W*$', re.I)
NOISE = re.compile(r'^(?:rispondi|reply|vedi traduzione|see translation|commenti|comments|altro|more|'
                   r'(?:visualizza|vedi|view)\b.*(?:rispost|repl).*|nascondi.*|hide.*|'
                   r'aggiungi un commento.*|add a comment.*|commenta come.*|'
                   r'[\d.,]+\s*(?:k|mila|mln)?|[♡♥❤\W]+)$', re.I)

_engine = None
_engine_lock = threading.Lock()
_run_lock = threading.Lock()
LIKES = re.compile(r'^\d[\d.,]*\s*(?:k|mila|mln)?$', re.I)


def _ocr():
    global _engine
    with _engine_lock:
        if _engine is None:
            from rapidocr import RapidOCR
            _engine = RapidOCR(params={'Global.log_level': 'error'})
        return _engine


def _rows(boxes):
    """Righe di testo: i pezzi alla stessa altezza si uniscono da sinistra a destra."""
    rows = []
    for box in sorted(boxes, key=lambda b: b[1] + b[2] / 2):
        mid = box[1] + box[2] / 2
        if rows and abs(mid - rows[-1]['mid']) < min(box[2], rows[-1]['h']) * .5:
            rows[-1]['parts'].append(box)
        else:
            rows.append({'mid': mid, 'h': box[2], 'parts': [box]})
    out = []
    for row in rows:
        parts = sorted(row['parts'], key=lambda b: b[0])
        out.append({'x': parts[0][0], 'y': min(p[1] for p in parts), 'h': row['h'],
                    'text': ' '.join(p[3].strip() for p in parts).strip()})
    return out


def parse(boxes, width):
    """boxes: (x, y, altezza, testo). Un commento parte da una riga "nome + tempo"; le righe dopo,
    tolti i pulsanti di Instagram, sono il suo testo. Il numero nella colonna a destra sono i mi piace."""
    left = [b for b in boxes if b[0] < width * RIGHT_COLUMN]
    out, current = [], None
    for row in _rows(left):
        head = HEADER.match(row['text']) or GLUED.match(row['text'])
        if head:
            current = {'user': head.group(1), 'time': ' '.join(head.group(2).split()), 'likes': '',
                       'x': row['x'], 'y': row['y'], 'h': row['h'], 'lines': []}
            out.append(current)
        elif current is not None and not NOISE.match(row['text']):
            current['lines'].append(row['text'])
    for box in sorted(boxes, key=lambda b: b[1]):
        if box[0] >= width * RIGHT_COLUMN and LIKES.match(box[3].strip()):
            mid = box[1] + box[2] / 2
            above = [c for c in out if c['y'] - c['h'] * .5 <= mid]
            if above and not above[-1]['likes']:
                above[-1]['likes'] = box[3].strip()
    return [{'user': c['user'], 'text': ' '.join(c['lines']).strip(), 'time': c['time'], 'likes': c['likes'],
             'box': (c['x'], c['y'], c['h'])} for c in out if c['lines']]


def avatar(image, x, y, h):
    """Foto profilo a sinistra del nome: la parte diversa dallo sfondo, se è circa quadrata."""
    top, bottom = max(0, round(y - 1.2 * h)), min(image.height, round(y + 3.6 * h))
    right = round(x - max(3, h * .25))
    if right < 12 or bottom <= top:
        return None
    area = np.asarray(image.crop((0, top, right, bottom))).astype(int)
    back = np.median(area[:, :2].reshape(-1, 3), axis=0)
    mask = np.abs(area - back).sum(axis=2) > 36
    rows = mask.any(axis=1)
    mid = min(len(rows) - 1, round(y + h / 2) - top)
    if not rows[mid]:
        return None
    first = last = mid
    while first > 0 and rows[first - 1]:
        first -= 1
    while last < len(rows) - 1 and rows[last + 1]:
        last += 1
    cols = np.flatnonzero(mask[first:last + 1].any(axis=0))
    if not len(cols):
        return None
    wide, tall = int(cols[-1] - cols[0] + 1), last - first + 1
    if tall < 1.4 * h or not .75 <= wide / tall <= 1.33:
        return None
    side = max(wide, tall)
    cx, cy = (int(cols[0]) + int(cols[-1])) / 2, top + (first + last) / 2
    box = (round(cx - side / 2), round(cy - side / 2), round(cx + side / 2), round(cy + side / 2))
    face = image.crop(box)
    inner = _inside_ring(face, back)
    if inner:                    # aveva l'anello della storia: resta solo la foto, l'anello lo mette il grafico
        middle = face.width / 2
        face = face.crop((round(middle - inner), round(middle - inner), round(middle + inner), round(middle + inner)))
    out = io.BytesIO()
    face.resize((184, 184), Image.LANCZOS).save(out, 'JPEG', quality=92)
    return out.getvalue()


def _inside_ring(face, back):
    """Raggio della foto dentro l'anello della storia (anello, stacco color sfondo, foto); None se non c'è."""
    pixels = np.asarray(face).astype(int)
    size = pixels.shape[0]
    yy, xx = np.indices(pixels.shape[:2])
    radius = np.hypot(xx - (size - 1) / 2, yy - (size - 1) / 2)
    near = np.abs(pixels - back).sum(axis=2) <= 36
    ring_seen, gap = False, None
    for r in range(int(size * .49), int(size * .34), -1):
        band = (radius >= r - .5) & (radius < r + .5)
        share = near[band].mean()
        if gap is None and share <= .4:
            ring_seen = True
        elif ring_seen and share >= .85:
            gap = r
        elif gap is not None:
            return r
    return None


def _key(comment):
    text = unicodedata.normalize('NFKD', f"{comment['user']} {comment['text']}").casefold()
    return re.sub(r'\W+', '', text)


def merge(groups):
    """Più screenshot: stesso commento una volta sola, nell'ordine in cui compare."""
    seen, out = set(), []
    for comment in (c for group in groups for c in group):
        key = _key(comment)
        if key not in seen:
            seen.add(key)
            out.append(comment)
    return out[:MAX_COMMENTS]


def read(raw):
    """Commenti di uno screenshot (bytes)."""
    try:
        image = ImageOps.exif_transpose(Image.open(io.BytesIO(raw))).convert('RGB')
    except Exception as exc:
        raise ValueError('Immagine non leggibile.') from exc
    engine = _ocr()
    with _run_lock:
        result = engine(np.asarray(image)[:, :, ::-1])
    if result.boxes is None:
        return []
    boxes = [(float(b[0][0]), float(b[0][1]), float(b[2][1] - b[0][1]), str(t))
             for b, t in zip(result.boxes, result.txts)]
    comments = parse(boxes, image.width)
    for comment in comments:
        comment['avatar'] = avatar(image, *comment.pop('box'))
    return comments


def public(comments):
    """Commenti per la Mini App: la foto profilo viaggia nel JSON e si carica solo se scelta."""
    return [{**{k: c.get(k, '') for k in ('user', 'text', 'time', 'likes')},
             'avatar': base64.b64encode(c['avatar']).decode('ascii') if c.get('avatar') else ''}
            for c in comments[:MAX_COMMENTS]]
