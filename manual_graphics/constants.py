"""Shared constants and parsers for the Mini App."""
import math
import re

KINDS = [
    ('GOAL', 'goal'),
    ('SAVED', 'saved'),
    ('KICK OFF', 'kick'),
    ('HALF TIME', 'half'),
    ("END OF 90'", 'end_of_90'),
    ('FULL TIME', 'full'),
    ('STATS', 'stats'),
]

COMPETITIONS = [
    ('Serie A', 'ita.1'),
    ('Coppa Italia', 'ita.coppa_italia'),
    ('Supercoppa Italiana', 'ita.super_cup'),
    ('Champions League', 'uefa.champions'),
    ('Europa League', 'uefa.europa'),
    ('Conference League', 'uefa.europa.conf'),
    ('Supercoppa UEFA', 'uefa.super_cup'),
    ('Mondiale per Club', 'fifa.cwc'),
]

STATS = (
    'POSSESSO', 'xG', 'TIRI', 'TIRI IN PORTA', 'CORNER', 'FALLI',
    'FUORIGIOCO', 'AMMONITI', 'ESPULSI', 'PARATE',
    'PRECISIONE PASSAGGI', 'PASSAGGI',
)


def parse_minute(text):
    match = re.fullmatch(r"(\d{1,3})(?:\+(\d{1,2}))?", text.strip().rstrip("'’"))
    if not match or int(match[1]) > 120:
        raise ValueError('Minuto non valido. Esempi: 56 oppure 90+12.')
    return str(int(match[1])) + ('+' + str(int(match[2])) if match[2] else '')


def parse_stat_pair(text):
    if text.strip() == '-':
        return None
    match = re.fullmatch(
        r'\s*(\d+(?:[.,]\d+)?%?)\s*[-/]\s*(\d+(?:[.,]\d+)?%?)\s*',
        text,
    )
    if not match:
        raise ValueError(
            'Due valori casa-trasferta (es. 57-43, 1.72/0.95) o - per omettere.'
        )
    values = tuple(v.replace(',', '.') for v in match.groups())
    for value in values:
        number = float(value.rstrip('%'))
        if not math.isfinite(number) or number < 0 or number > 100000:
            raise ValueError('Valore statistica fuori intervallo.')
        if '%' in value and number > 100:
            raise ValueError('Una percentuale non può superare 100.')
    return values
