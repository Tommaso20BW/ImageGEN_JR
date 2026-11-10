import unittest
from unittest.mock import patch

import _percorsi  # noqa: F401 - prima degli import del servizio
import webapp_payload
from graphics import classifica


def envelope(competition):
    return {'v': 1, 'action': 'render', 'session': 's1', 'data': {'kind': 'table', 'competition': competition}}


class PayloadTests(unittest.TestCase):
    def test_table_needs_only_the_competition(self):
        state = webapp_payload.parse_webapp_request(envelope('UCL'), None, 0, 's1')
        self.assertEqual(state['data'], {'kind': 'table', 'competition': 'UCL'})

    def test_unknown_competition_is_refused(self):
        with self.assertRaises(ValueError):
            webapp_payload.parse_webapp_request(envelope('ita.1'), None, 0, 's1')


class HtmlTests(unittest.TestCase):
    def test_page_is_self_contained(self):
        data = {'competition': 'SA', 'giornata': 9, 'stagione': '2026/27',
                'classifica': [{'pos': 1, 'team': 'Juventus', 'logo': 'data:image/png;base64,AA', 'pt': 3, 'dr': 1}]}
        with patch.object(classifica, '_font_css', return_value='@font-face{}'):
            html = classifica.build_html(data)
        self.assertIn('window.__CLASSIFICA__ = {"competition": "SA"', html)
        self.assertIn('window.__ready', html)
        self.assertNotIn('fonts.googleapis', html)
        for name in classifica.IMAGES:
            self.assertNotIn(name, html)


if __name__ == '__main__':
    unittest.main()
