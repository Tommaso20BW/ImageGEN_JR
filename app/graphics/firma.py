"""Firma scritta a mano da calligrapher.ai (rete neurale che scrive come una persona, nel browser).

Il servizio apre il sito in Chrome senza finestra e scrive "Nome Cognome" in una volta sola, con uno
stile a caso: ogni firma è diversa, ma nome e cognome hanno sempre la stessa mano. Poi la riga si
divide nello spazio tra le due parole (nome sopra, cognome sotto) e si copiano i tratti (contorni
pieni in SVG). Se il sito non risponde la grafica esce senza firma (meglio che bloccare l'invio)."""
import os
import random
import re
import threading
import unicodedata

URL = 'https://www.calligrapher.ai/'
STYLES = ('44', '54', '23', '1', '19', '6', '30', '11', '21')   # tutti gli stili del sito
SPEED, WIDTH = '9.5', '1.5'                                   # tratto al massimo: firma piena
BIAS = (1.5, 2.5)                     # leggibilità del sito: a caso in questo intervallo, una per firma
TIMEOUT_S = 40


def ascii_text(text):
    """Il modello conosce solo lettere senza accenti: ć -> c, ø -> o."""
    t = unicodedata.normalize('NFKD', str(text or '')).replace('ø', 'o').replace('Ø', 'O')
    t = t.replace('ł', 'l').replace('Ł', 'L').replace('đ', 'd').replace('Đ', 'D')
    return re.sub(r'\s+', ' ', ''.join(c for c in t if c.isascii() and (c.isalpha() or c in " '-."))).strip()[:50]


_JS_WRITE = """async ([text, style, speed, bias, width]) => {
  const set = (id, v) => { const e = document.getElementById(id); e.value = v;
    e.dispatchEvent(new Event('input', {bubbles: true})); e.dispatchEvent(new Event('change', {bubbles: true})); };
  set('select-style', style); set('speed-slider', speed); set('bias-slider', bias); set('width-slider', width);
  set('text-input', text);
  const canvas = document.getElementById('canvas');
  canvas.innerHTML = '';
  document.getElementById('draw-button').dispatchEvent(new MouseEvent('mousedown', {bubbles: true}));
  let last = -1, same = 0;
  await new Promise(r => setTimeout(r, 300));
  for (let i = 0; i < 160; i++) {
    await new Promise(r => setTimeout(r, 250));
    const n = canvas.innerHTML.length;
    if (n === last && n > 100) { if (++same >= 4) break; } else same = 0;
    last = n;
  }
  return [...canvas.querySelectorAll('path')].map(p => p.getAttribute('d'));
}"""


def _write(lines, style):
    """Apre il sito e scrive le righe con lo stesso stile: per ognuna la lista dei contorni (d)."""
    from playwright.sync_api import sync_playwright

    out = {}

    def run():                         # thread a parte: la API sync di Playwright non vuole asyncio attorno
        try:
            with sync_playwright() as pw:
                browser = pw.chromium.launch(executable_path=os.environ.get('IMAGEGEN_CHROME') or None)
                try:
                    page = browser.new_page(viewport={'width': 1200, 'height': 800})
                    page.goto(URL, wait_until='load', timeout=TIMEOUT_S * 1000)
                    page.wait_for_selector('#loading-indicator', state='detached', timeout=TIMEOUT_S * 1000)
                    bias = f'{random.uniform(*BIAS):.2f}'      # nome e cognome con la stessa leggibilità
                    out['paths'] = [page.evaluate(_JS_WRITE, [t, style, SPEED, bias, WIDTH]) for t in lines]
                finally:
                    browser.close()
        except Exception as exc:       # noqa: BLE001 - la firma non deve mai bloccare la grafica
            out['error'] = exc

    th = threading.Thread(target=run, name='firma', daemon=True)
    th.start()
    th.join(TIMEOUT_S * 2)
    if 'paths' not in out:
        raise RuntimeError(f"calligrapher.ai non risponde: {out.get('error', 'tempo scaduto')}")
    return out['paths']


def _xspan(d):
    nums = [float(v) for v in re.findall(r'-?\d+(?:\.\d+)?', d)]
    xs = nums[0::2]
    return (min(xs), max(xs)) if xs else None


def split_words(ds, name, surname):
    """Divide i tratti di "Nome Cognome" nello spazio tra le due parti: il buco orizzontale più vicino a
    dove dovrebbe cadere (in proporzione alle lettere). None se non c'è un buco."""
    spans = sorted((sp, d) for d in ds if (sp := _xspan(d)))
    if len(spans) < 2:
        return None
    x0, x1 = spans[0][0][0], max(sp[1] for sp, _ in spans)
    want = x0 + (x1 - x0) * (len(name) + .5) / (len(name) + 1 + len(surname))
    best, end = None, spans[0][0][1]
    for i in range(1, len(spans)):
        start = spans[i][0][0]
        if start > end:                                     # buco tra i tratti prima e dopo
            score = abs((start + end) / 2 - want) - (start - end)
            if best is None or score < best[0]:
                best = (score, i)
        end = max(end, spans[i][0][1])
    if best is None:
        return None
    i = best[1]
    return [d for _, d in spans[:i]], [d for _, d in spans[i:]]


def _per_char(ds, text):
    spans = [sp for d in ds if (sp := _xspan(d))]
    return (max(e for _, e in spans) - min(x for x, _ in spans)) / max(len(text), 1) if spans else 0


def runaway(parts, texts):
    """Il modello a volte non si ferma e aggiunge scarabocchi in coda: una riga molto più larga per
    lettera dell'altra."""
    a, b = (_per_char(ds, t) for ds, t in zip(parts, texts))
    return min(a, b) <= 0 or max(a, b) > 1.6 * min(a, b)


def _once(todo, style):
    if len(todo) == 2 and len(' '.join(todo)) <= 50:
        parts = split_words(_write([' '.join(todo)], style)[0], *todo)
        if parts:
            return list(parts)
    return _write(todo, style)


def paths(lines, style=None, tries=3):
    """Contorni per ogni riga (liste di 'd'); [] per una riga vuota. Ogni chiamata scrive una firma
    nuova, con lo stile dato o uno a caso (nome e cognome scritti insieme: stessa mano). Se esce
    sbavata si riscrive con un altro stile. Errore se il sito non risponde."""
    lines = [ascii_text(t) for t in lines]
    todo = [t for t in lines if t]
    if not todo:
        return [[] for _ in lines]
    for n in range(tries):
        got = _once(todo, style if n == 0 and style else random.choice(STYLES))
        if len(todo) < 2 or not runaway(got, todo):
            break
    it = iter(got)
    return [list(next(it)) if t else [] for t in lines]


def polygons(d, steps=8):
    """Un contorno SVG (M x,y C x y, x y, x y ...) come lista di punti."""
    nums = [float(v) for v in re.findall(r'-?\d+(?:\.\d+)?', d)]
    if len(nums) < 2:
        return []
    pts = [(nums[0], nums[1])]
    cur = pts[0]
    i = 2
    while i + 5 < len(nums) + 0 and i + 6 <= len(nums):
        p1, p2, p3 = (nums[i], nums[i + 1]), (nums[i + 2], nums[i + 3]), (nums[i + 4], nums[i + 5])
        for k in range(1, steps + 1):
            t = k / steps
            a, b, c, e = (1 - t) ** 3, 3 * (1 - t) ** 2 * t, 3 * (1 - t) * t * t, t ** 3
            pts.append((a * cur[0] + b * p1[0] + c * p2[0] + e * p3[0], a * cur[1] + b * p1[1] + c * p2[1] + e * p3[1]))
        cur = p3
        i += 6
    return pts
