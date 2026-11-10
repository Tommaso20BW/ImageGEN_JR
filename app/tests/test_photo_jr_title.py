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


class TitleShadeTests(unittest.TestCase):
    def test_title_page_is_darker_at_the_bottom(self):
        html = photo_jr.build_html(color='white', style='title', title='Infortunio')
        self.assertIn(photo_jr.TITLE_SHADE, html)
        self.assertNotIn(photo_jr.TITLE_SHADE, photo_jr.build_html(color='white', style='classic'))


class SavedColorsTests(unittest.TestCase):
    """Colori aggiunti con il +: servizio /colors e file imagegen/colors.json degli asset."""

    def setUp(self):
        import tempfile
        import threading
        from types import SimpleNamespace
        from unittest import mock
        import sent_store
        import service
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        env = mock.patch.dict('os.environ', {'IMAGEGEN_ASSETS': self.tmp.name})
        env.start(); self.addCleanup(env.stop)
        save = mock.patch.object(sent_store, '_flush', lambda: None)       # niente commit nel repo
        save.start(); self.addCleanup(save.stop)
        self.sent_store = sent_store
        self.svc = SimpleNamespace(history_lock=threading.Lock(), saved_colors={'title': [], 'jr': []})
        self.call = lambda **e: service.Service.colors(self.svc, {'v': 1, **e})

    def test_add_list_delete_and_reload(self):
        self.call(action='add', target='title', color='#AA0011')
        self.call(action='add', target='jr', color={'type': 'solid', 'hex': '#00FF00'})
        grad = {'type': 'gradient', 'angle': 90, 'stops': [{'c': '#ffffff', 'p': 100}, {'c': '#000000', 'p': 0}]}
        out = self.call(action='add', target='jr', color=grad)['colors']
        self.assertEqual(out['title'], ['#aa0011'])
        self.assertEqual(out['jr'][1], {'type': 'solid', 'hex': '#00ff00'})
        self.assertEqual(out['jr'][0]['stops'][0], {'c': '#000000', 'p': 0.0})      # ordinato come il servizio
        self.assertEqual(self.sent_store.load_colors(), out)                          # resta nel file
        out = self.call(action='delete', target='title', color='#aa0011')['colors']
        self.assertEqual(out['title'], [])
        self.assertEqual(self.call(action='list')['colors'], out)

    def test_same_colour_is_not_doubled(self):
        for _ in range(3):
            out = self.call(action='add', target='title', color='#123456')['colors']
        self.assertEqual(out['title'], ['#123456'])

    def test_bad_requests(self):
        for envelope in ({'action': 'add', 'target': 'title', 'color': 'rosso'},
                         {'action': 'add', 'target': 'jr', 'color': 'white'},
                         {'action': 'add', 'target': 'altro', 'color': '#ffffff'},
                         {'action': 'boh', 'target': 'title', 'color': '#ffffff'}):
            with self.assertRaises(ValueError):
                self.call(**envelope)


class GradientStopsTests(unittest.TestCase):
    def test_up_to_seven_colours(self):
        stops = lambda n: [{'c': '#%02x0000' % (i * 30), 'p': i * 100 / max(1, n - 1)} for i in range(n)]
        self.assertEqual(len(photo_jr.clean_color({'type': 'gradient', 'angle': 90, 'stops': stops(7)})['stops']), 7)
        for n in (1, 8):
            with self.assertRaises(ValueError):
                photo_jr.clean_color({'type': 'gradient', 'angle': 90, 'stops': stops(n)})


if __name__ == '__main__':
    unittest.main()
