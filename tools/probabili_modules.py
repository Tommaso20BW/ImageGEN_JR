"""Calcola le posizioni delle carte per i moduli delle probabili non presenti su Canva.

Difesa e portiere: posizioni Canva. Attacco: altezza degli attaccanti Canva.
Le linee in mezzo vengono cercate fra molte altezze e sfalsamenti, scartando
ogni combinazione in cui un'etichetta tocca un'altra carta (testa o etichetta).
Stampa il dizionario da incollare in graphics/probabili.py.

Uso: python tools/probabili_modules.py
"""
import itertools

# Geometria carta (pixel design), relativa a (centro x, alto del box etichetta).
LABEL = (-117.0, 0.0, 233.9, 58.9)
HEAD = (-99.4, -175.4, 198.8, 198.8)
GAP = 2.5          # spazio minimo fra le carte (come la difesa a 4 di Canva)
TOP_LIMIT = 300    # le etichette non salgono oltre (la testa resta sotto il titolo)

GK = [(540.0, 1228.16)]
B4 = [(124.26, 956.16), (401.5, 991.04), (678.75, 991.04), (955.74, 956.16)]
B3 = [(225.0, 982.4), (540.0, 982.4), (851.77, 982.4)]

# Modulo: (difesa, [linee dal centrocampo all'attacco]); linea = [(x, sfalsabile?)]
SPECS = {
    '4-3-1-2': (B4, [[(225, 1), (540, 2), (855, 1)], [(540, 0)], [(306.01, 0), (773.99, 0)]]),
    '4-2-2-2': (B4, [[(384.53, 0), (695.47, 0)], [(123.53, 0), (956.47, 0)], [(384.53, 0), (695.47, 0)]]),
    '4-3-2-1': (B4, [[(225, 1), (540, 2), (855, 1)], [(300, 0), (780, 0)], [(540, 0)]]),
    '3-4-3': (B3, [[(123.53, 1), (384.53, 0), (695.47, 0), (956.47, 1)], [(225, 1), (540, 2), (855, 1)]]),
    '5-4-1': ('B5', [[(123.53, 1), (384.53, 0), (695.47, 0), (956.47, 1)], [(540, 0)]]),
}
# Non entrano nel campo senza sovrapporre le carte (ogni carta ~234x234 px):
# 4-1-4-1, 4-5-1, 5-3-2. Il 3-5-2 ha le stesse posizioni del 3-4-1-2 di Canva.
FORWARD_TOPS = (307.52, 320.32, 341.12)
STAGGER = (0, -40, -80, 40, 80)


def rects(cards):
    out = []
    for cx, top in cards:
        lab = (cx + LABEL[0], top + LABEL[1], LABEL[2], LABEL[3])
        head = (cx + HEAD[0], top + HEAD[1], HEAD[2], HEAD[3])
        out.append((lab, head))
    return out


def clearance(cards):
    """Spazio minimo fra un'etichetta e le altre carte (negativo = sovrapposte)."""
    best = 1e9
    rs = rects(cards)
    for i, (lab, _h) in enumerate(rs):
        for j, (lab2, head2) in enumerate(rs):
            if i == j:
                continue
            for other in (lab2, head2):
                x, y, w, h = lab
                ox, oy, ow, oh = other
                dx = max(ox - (x + w), x - (ox + ow))
                dy = max(oy - (y + h), y - (oy + oh))
                best = min(best, max(dx, dy))
    return best


def _ok(new, placed):
    """Clearance minima fra le carte nuove e quelle già piazzate (e fra loro)."""
    return clearance(placed + new) if placed else clearance(new)


def solve(defence, lines):
    """Ricerca a ritroso: una linea alla volta, dalla difesa verso l'attacco.
    Ogni linea: altezza libera + sfalsamento indipendente per esterni (1) e centrali (2)."""
    base = list(GK) + list(defence)
    best = [None]

    def place(k, placed, prev_top):
        if k == len(lines):
            c = clearance(placed)
            if c >= GAP:
                tops = sorted({round(t) for _x, t in placed[len(base):]})
                score = c - 0.02 * (max(tops) - min(tops) if tops else 0) * 0   # più spazio = meglio
                if best[0] is None or score > best[0][0]:
                    best[0] = (score, list(placed))
            return
        line = lines[k]
        last = k == len(lines) - 1
        ys = FORWARD_TOPS if last else range(int(prev_top) - 160, max(TOP_LIMIT + 120, int(prev_top) - 420), -10)
        for y in ys:
            for st1 in (STAGGER if any(s == 1 for _x, s in line) else (0,)):
                for st2 in (STAGGER if any(s == 2 for _x, s in line) else (0,)):
                    new = [(float(x), float(y + (st1 if s == 1 else st2 if s == 2 else 0))) for x, s in line]
                    if min(t for _x, t in new) < TOP_LIMIT:
                        continue
                    trial = placed + new
                    if clearance(trial) < GAP:
                        continue
                    place(k + 1, trial, min(t for _x, t in new))

    place(0, base, min(t for _x, t in defence))
    if best[0]:
        cards = best[0][1]
        return clearance(cards), cards
    return None


def main():
    wb_tops = range(700, 900, 20)
    for name, (defence, lines) in SPECS.items():
        if defence == 'B5':
            result = None
            for wb in wb_tops:
                five = [B3[0], B3[1], B3[2], (123.53, wb), (956.47, wb)]
                r = solve([five[3], five[0], five[1], five[2], five[4]], lines)
                if r and (result is None or r[0] > result[0]):
                    result = r
        else:
            result = solve(defence, lines)
        if not result:
            print(f'# {name}: nessuna disposizione senza sovrapposizioni')
            continue
        gap, cards = result
        print(f"    '{name}': {[[round(x, 2), round(y, 2)] for x, y in cards]},  # spazio minimo {gap:.0f}px")


if __name__ == '__main__':
    main()
