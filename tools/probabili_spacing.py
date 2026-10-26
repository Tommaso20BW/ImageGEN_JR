"""Ridistribuisce le linee dei moduli probabili: stessa distanza fra tutte le linee.

Per ogni modulo (tranne quelli Canva) tiene la forma di ogni linea (x e piccoli
scalini interni) e cerca le altezze delle linee che rendono UGUALI gli spazi vuoti
fra una linea e l'altra (dalla difesa all'attacco), senza carte sovrapposte.
Stampa il nuovo dizionario MODULES da incollare in graphics/probabili.py.

Uso: python tools/probabili_spacing.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from graphics.probabili import MODULE_SCALE, MODULES  # noqa: E402

CANVA = {'4-2-3-1', '3-4-2-1', '3-4-1-2'}
LABEL = (-117.0, 0.0, 233.9, 58.9)
HEAD = (-99.4, -175.4, 198.8, 198.8)
TOP_HEAD_MIN = 120      # la testa più alta resta sotto il titolo
GAP_MIN = 2.5           # spazio minimo fra carte (come la difesa a 4 di Canva)


def lines_of(module):
    """[[(x, y)...], ...] dalla difesa all'attacco (portiere escluso)."""
    sizes = [int(n) for n in module.split('-')]
    cards = MODULES[module][1:]
    out, i = [], 0
    for n in sizes:
        out.append([tuple(c) for c in cards[i:i + n]])
        i += n
    return out


def extent(line, s):
    """(alto testa, basso etichetta) della linea."""
    return min(y + HEAD[1] * s for _x, y in line), max(y + (LABEL[1] + LABEL[3]) * s for _x, y in line)


def clearance(cards, s):
    best = 1e9
    rs = [((x + LABEL[0] * s, y + LABEL[1] * s, LABEL[2] * s, LABEL[3] * s),
           (x + HEAD[0] * s, y + HEAD[1] * s, HEAD[2] * s, HEAD[3] * s)) for x, y in cards]
    for i, (lab, _h) in enumerate(rs):
        for j, (lab2, head2) in enumerate(rs):
            if i != j:
                for o in (lab2, head2):
                    dx = max(o[0] - (lab[0] + lab[2]), lab[0] - (o[0] + o[2]))
                    dy = max(o[1] - (lab[1] + lab[3]), lab[1] - (o[1] + o[3]))
                    best = min(best, max(dx, dy))
    return best


def place(lines, shifts):
    """Linee (dalla seconda in poi) spostate in verticale di shifts[k]."""
    return [lines[0]] + [[(x, y + d) for x, y in line] for line, d in zip(lines[1:], shifts)]


def gaps(lines, s):
    ext = [extent(line, s) for line in lines]
    return [ext[k][0] - ext[k + 1][1] for k in range(len(ext) - 1)]   # sotto - sopra


def centre(line):
    return sum(y for _x, y in line) / len(line)


def respace(module):
    """Carta più grande possibile (da 100% in giù) con linee equidistanti."""
    for s in (1.0, 0.97, 0.94, 0.91, 0.88, 0.85, 0.82, 0.79):
        result = respace_at(module, s)
        if result[2] >= GAP_MIN:
            return result + (s,)
    return result + (s,)


def respace_at(module, s):
    """Centri delle linee equidistanti fra difesa e attacco; l'attacco più in alto
    possibile. Se due carte si toccano, l'attacco scende un poco e si riprova."""
    gk = tuple(MODULES[module][0])
    lines = lines_of(module)
    base = centre(lines[0])
    best = None
    for drop in range(0, 160, 4):
        top_shift = TOP_HEAD_MIN - extent(lines[-1], s)[0] + drop
        top_c = centre(lines[-1]) + top_shift
        n = len(lines) - 1
        shifts = []
        for k in range(1, len(lines)):
            target = base + (top_c - base) * k / n
            shifts.append(target - centre(lines[k]))
        placed = place(lines, shifts)
        cards = [gk] + [c for line in placed for c in line]
        c = clearance(cards, s)
        if c >= GAP_MIN:
            return cards, gaps(placed, s), c
        if best is None or c > best[2]:
            best = (cards, gaps(placed, s), c)
    return best


def main():
    for module in MODULES:
        if module in CANVA:
            print(f"    # '{module}': Canva, invariato")
            continue
        cards, g, c, sc = respace(module)
        flag = '' if c >= GAP_MIN else '   <-- SOVRAPPOSTO'
        print(f"    '{module}': {[[round(x, 2), round(y, 2)] for x, y in cards]},"
              f"  # scala {sc}, spazi {[round(v) for v in g]}, minimo fra carte {c:.0f}{flag}")


if __name__ == '__main__':
    main()
