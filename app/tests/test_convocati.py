"""Lettura dei convocati da juventus.com (casi visti sul sito vero). Avvio (da app/): python -m unittest discover -s tests"""
import json
import unittest
from unittest import mock

import requests

import _percorsi  # noqa: F401 - prima degli import del servizio
import juventus_convocati as jc


def page(lines, headline='Serie A | Juventus-Napoli | I convocati', keywords=('First Team Men', '2026/27', 'Serie A')):
    article = {'@type': 'NewsArticle', 'headline': headline, 'keywords': list(keywords),
               'datePublished': '2026-11-01T12:01:16.324Z', 'articleBody': '\n\n'.join(lines)}
    paras = ''.join(f'<div class="body-part"><p>{line}</p></div>' for line in lines)
    return (f'<script type="application/ld&#x2B;json">{json.dumps(article)}</script>'
            f'<article>{paras}</article>')


SQUAD = ['3 Bremer', '4 Gatti', '6 Kelly', '8 Koopmeiners', '9 Kolo Muani', '11 Zhegrova', '12 Douglas Luiz',
         '13 Boga', '15 Kalulu', '17 Alajbegovic', '18 Ekhator', '20 Cambiaso', '22 McKennie', '23 Pinsoglio']


class RowTests(unittest.TestCase):
    def test_players(self):
        for text, num in [('3 Bremer', 3), ('3 Bremer', 3), ('9 Kolo Muani', 9), ('22 McKennie', 22),
                          ('11 Mar', 11), ("5 D'Alessandro", 5), ('7 Conceição', 7)]:
            self.assertEqual(jc._row(text)[0], num, text)

    def test_notes_and_glued_text(self):
        self.assertEqual(jc._row('50 Rizzo (inserito in Lista B UEFA)'), (50, '50 Rizzo'))
        self.assertIsNone(jc._row('45 BarrenecheaULTIMI BIGLIETTI PER LA SFIDA!'))
        self.assertEqual(jc._row('9 Vlahović'), (9, '9 Vlahović'))

    def test_not_players(self):
        for text in ['28 ott. 2026', '30 Ott 2026', '28 ott.', '1 novembre', '20:45 Allianz', '2 set.', '0 Nessuno',
                     '10 giornata 2026']:
            self.assertIsNone(jc._row(text), text)


class HeadlineTests(unittest.TestCase):
    def test_formats_seen_on_the_site(self):
        cases = {
            'Serie A | Genoa-Juventus | I convocati': ('Genoa', 'Juventus'),
            'Genoa-Juve, i convocati': ('Genoa', 'Juventus'),
            'Atalanta-Juventus, i convocati per la finale di Coppa Italia': ('Atalanta', 'Juventus'),
            "Juve-Salernitana, i convocati per l'esordio in Coppa Italia": ('Juventus', 'Salernitana'),
            'Atalanta-Juve, i convocati ': ('Atalanta', 'Juventus'),
            'I convocati per Juventus-Lecce': ('Juventus', 'Lecce'),
            'UEFA Europa League | Juventus-Stade Rennais F.C. | I convocati': ('Juventus', 'Stade Rennais F.C.'),
        }
        for headline, teams in cases.items():
            self.assertEqual(jc._teams(headline), teams, headline)

    def test_next_gen_is_not_the_first_team(self):
        self.assertIsNone(jc._teams('Serie C | Juventus Next Gen-Renate | I convocati'))


class ArticleTests(unittest.TestCase):
    def test_dates_on_the_page_are_not_players(self):
        html = page(SQUAD) + '<p>28 ott. 2026</p><p>30 ott. 2026</p>'
        item = jc.parse_article(html, 'https://www.juventus.com/it/news/articoli/x')
        names = [p.split(' ', 1)[1] for p in item['players']]
        self.assertEqual(len(names), len(SQUAD))
        self.assertIn('Bremer', names)
        self.assertNotIn('ott. 2026', ' '.join(item['players']))

    def test_next_gen_is_skipped(self):
        html = page(SQUAD, headline='Serie C | Juventus Next Gen-Renate | I convocati', keywords=('NextGen',))
        self.assertIsNone(jc.parse_article(html, 'https://www.juventus.com/it/news/articoli/y'))


class EncodingTests(unittest.TestCase):
    def test_page_without_charset_is_read_as_utf8(self):
        resp = requests.Response()
        resp.status_code = 200
        resp.headers['Content-Type'] = 'text/html'
        resp._content = '<p>3 Bremer</p><p>7 Conceição</p>'.encode('utf-8')
        with mock.patch.object(jc.requests, 'get', return_value=resp):
            text = jc._get('https://www.juventus.com/it/news/articoli/z')
        self.assertIn('3 Bremer', text)
        self.assertIn('Conceição', text)


if __name__ == '__main__':
    unittest.main()
