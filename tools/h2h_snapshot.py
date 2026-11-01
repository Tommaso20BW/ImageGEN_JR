"""Archivio HEAD TO HEAD: bilancio e precedenti Juventus-squadra da Transfermarkt.

Transfermarkt non risponde ai server GitHub (controllo anti-bot), quindi i dati
storici si scaricano da un computer e si salvano in data/h2h.json. Le partite
giocate dopo `updated` le aggiunge il servizio da ESPN (vedi h2h_data.py).

Uso:  python tools/h2h_snapshot.py            (tutte le squadre del catalogo loghi)
      python tools/h2h_snapshot.py "Napoli"   (solo le squadre indicate, aggiorna le altre già salvate)
"""
import json
import os
import sys
import time
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import h2h_data  # noqa: E402
from graphics.common import _logo_rows, normalize  # noqa: E402

OUT = Path(__file__).resolve().parents[1] / 'data' / 'h2h.json'
KEEP = 10   # precedenti salvati per squadra (ne servono 5, gli altri coprono eventuali scarti)


def main(only):
    assets = os.environ.get('IMAGEGEN_ASSETS') or str(Path(__file__).resolve().parents[2] / 'LiveScore_Assets_JR')
    rows = _logo_rows(assets)
    db = json.loads(OUT.read_text(encoding='utf-8')) if OUT.is_file() else {'teams': {}}
    todo = [r for r in rows if not only or normalize(r['name']) in only or any(normalize(a) in only for a in r.get('aliases') or [])]
    for n, row in enumerate(todo, 1):
        names = [row['name'], *(row.get('aliases') or [])]
        try:
            club = h2h_data.find_club(names)
            time.sleep(1.5)
            stats = h2h_data.head_to_head(club)
            time.sleep(1.5)
        except Exception as exc:  # noqa: BLE001
            print(f'{n}/{len(todo)} SALTATA {row["name"]}: {exc}', flush=True)
            continue
        db['teams'][normalize(row['name'])] = {
            'name': row['name'], 'tm_id': club, 'updated': date.today().isoformat(),
            **{k: stats[k] for k in ('played', 'W', 'D', 'L', 'gf', 'ga')},
            'matches': stats['matches'][:KEEP],
        }
        print(f'{n}/{len(todo)} {row["name"]}: {stats["played"]} partite', flush=True)
        OUT.write_text(json.dumps(db, ensure_ascii=False, indent=0), encoding='utf-8')
    print('fatto:', len(db['teams']), 'squadre in', OUT)


if __name__ == '__main__':
    main({normalize(a) for a in sys.argv[1:]})
