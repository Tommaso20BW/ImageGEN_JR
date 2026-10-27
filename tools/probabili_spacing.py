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


# Forme fisse di alcune linee (x, scalino) che sostituiscono quelle attuali.
SHAPES = {
    # 3-5-2: esterni più alti delle mezzali, regista al centro più basso.
    '3-5-2': {1: [(123.53, -70.0), (340.0, 0.0), (540.0, 70.0), (740.0, 0.0), (956.47, -70.0)]},
    '3-5-1-1': {1: [(123.53, -70.0), (340.0, 0.0), (540.0, 70.0), (740.0, 0.0), (956.47, -70.0)]},
}


def respace(module):
    """Misura piena se possibile; si rimpicciolisce solo se a misura piena le
    carte si toccano comunque."""
    for s in (1.0, 0.97, 0.94, 0.91, 0.9, 0.88, 0.85, 0.82):
        result = respace_at(module, s)
        if result:
            return result + (s,)
    raise ValueError(module)


def respace_at(module, s):
    """Linee il più possibile equidistanti, senza carte sovrapposte.
    Prova l'attacco a diverse altezze e sposta le linee intermedie attorno alla
    posizione "equidistante" (scostamento minimo)."""
    import itertools
    gk = tuple(MODULES[module][0])
    lines = lines_of(module)
    for k, shape in SHAPES.get(module, {}).items():
        c = centre(lines[k])
        lines[k] = [(x, c + dy) for x, dy in shape]
    base = centre(lines[0])
    n = len(lines) - 1
    best = None
    for drop in range(0, 81, 8):
        top_c = centre(lines[-1]) + TOP_HEAD_MIN - extent(lines[-1], s)[0] + drop
        even = [base + (top_c - base) * k / n for k in range(1, len(lines))]
        offsets = range(-80, 81, 10)
        for devs in itertools.product(offsets, repeat=n - 1):
            targets = [e + d for e, d in zip(even[:-1], devs)] + [even[-1]]
            shifts = [t - centre(line) for t, line in zip(targets, lines[1:])]
            placed = place(lines, shifts)
            cards = [gk] + [c for line in placed for c in line]
            if clearance(cards, s) < GAP_MIN:
                continue
            score = (max([abs(d) for d in devs] or [0]), drop)
            if best is None or score < best[0]:
                best = (score, cards, gaps(placed, s), clearance(cards, s))
        if best and best[0][0] == 0:
            break
    return best[1:] if best else None


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
