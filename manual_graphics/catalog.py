"""Read the production player/team catalogs from the graphics core."""
import html
import json
from pathlib import Path
import re
import unicodedata

import goal_graphics as g


_SPECIAL_FOLD = str.maketrans({
    'ı': 'i',
    'ł': 'l',
    'đ': 'd',
    'ð': 'd',
    'þ': 'th',
    'ø': 'o',
    'æ': 'ae',
    'œ': 'oe',
    'ß': 'ss',
})


def normalize_key(value):
    """Accent/special-character-insensitive key used only for matching."""
    raw = html.unescape(str(value or '')).strip().casefold().translate(_SPECIAL_FOLD)
    raw = ''.join(
        char
        for char in unicodedata.normalize('NFKD', raw)
        if unicodedata.category(char) != 'Mn'
    )
    return re.sub(r'[^a-z0-9]+', ' ', raw).strip()


class Catalog:
    def __init__(self, assets=g.DEFAULT_ASSET_DIR):
        self.assets = Path(assets)

    def teams(self, query):
        path = self.assets / 'team_logos/fclogo_cache/manifest.json'
        rows = json.loads(path.read_text(encoding='utf-8')).get('teams', [])
        q = normalize_key(query)
        matches, exact = [], []

        for row in rows:
            names = [row.get('name', ''), *row.get('aliases', [])]
            normalized = [normalize_key(name) for name in names]

            # Exclude only Juventus itself, not Juve Stabia or other clubs.
            if any(name == 'juventus' for name in normalized):
                continue

            value = {
                'name': row['name'],
                'id': str(row.get('espn_id') or ''),
            }

            if q and any(q in name for name in normalized):
                matches.append(value)
            if q and q in normalized:
                exact.append(value)

        return exact or matches

    def players(self, query, goalkeeper=False):
        q = normalize_key(query)
        matches, exact = [], []

        for player in g.load_players():
            if goalkeeper and player.role != 'goalkeeper':
                continue

            normalized = [
                normalize_key(name)
                for name in [player.name, *player.aliases]
            ]

            if q and any(q in name for name in normalized):
                matches.append(player.name)
            if q and q in normalized:
                exact.append(player.name)

        return exact or matches
