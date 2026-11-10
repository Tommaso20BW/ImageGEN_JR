"""Post JR · Titolo: controlli della richiesta e pagina della grafica. Avvio (da app/): python -m unittest discover -s tests"""
import unittest

import _percorsi  # noqa: F401 - prima degli import del servizio
import webapp_payload
from graphics import photo_jr


def envelope(**data):
    base = {'kind': 'jr', 'style': 'title', 'color': 'white', 'title': 'Infortunio', 'title_color': '#E7E4DF',
            'photo_id': 'a' * 16, 'frame': {'x': 0, 'y': 0, 'zoom': 1}}
    return {'v': 1, 'action': 'render', 'session': 's1', 'data': {**base, **data}}


def parse(**data):
    return webapp_payload.parse_webapp_request(envelope(**data), None, 0, 's1')['data']


class TitlePayloadTests(unittest.TestCase):
    def test_valid_request(self):
        data = parse(title='  Rinnovo   ufficiale ')
        self.assertEqual((data['style'], data['title'], data['title_color']), ('title', 'Rinnovo ufficiale', '#e7e4df'))
        self.assertEqual(data['photo_id'], 'a' * 16)

    def test_missing_or_too_long_title(self):
        for title in ('', '   ', 'x' * (photo_jr.TITLE_MAX + 1)):
            with self.assertRaises(ValueError):
                parse(title=title)

    def test_bad_colour_and_missing_photo(self):
        with self.assertRaises(ValueError):
            parse(title_color='rosso')
        with self.assertRaises(ValueError):
            parse(photo_id='')


class TitlePageTests(unittest.TestCase):
    def test_title_is_escaped_and_fitted(self):
        html = photo_jr.build_html(color='white', style='title', title='<Ciao> & co', title_color='#ff0000')
        self.assertIn('&lt;Ciao&gt; &amp; co', html)
        self.assertIn('window.__ready', html)            # la pagina adatta la scritta prima dello scatto
        self.assertIn('#ff0000', html)

    def test_other_styles_have_no_title(self):
        self.assertNotIn('class="ttl"', photo_jr.build_html(color='white', style='classic'))


if __name__ == '__main__':
    unittest.main()
