import io
import unittest

from PIL import Image

from graphics import potm as P


def photo_and_cut(w=600, h=900):
    """Foto intera finta e scontornato della stessa misura."""
    photo = Image.new('RGBA', (w, h), (90, 140, 90, 255))
    cut = Image.new('RGBA', (w, h), (0, 0, 0, 0))
    cut.paste((230, 190, 160, 255), (w // 3, h // 8, w * 2 // 3, h * 7 // 8))
    photo.alpha_composite(cut)
    return photo, cut


class MonthTest(unittest.TestCase):
    def test_months_in_season_order(self):
        self.assertEqual(P.clean_month(['settembre', 'Agosto', 'agosto']), 'AGOSTO/SETTEMBRE')
        self.assertEqual(P.clean_month('gennaio/dicembre'), 'DICEMBRE/GENNAIO')
        self.assertEqual(P.clean_month(''), '')
        self.assertEqual(P.clean_month('Fine stagione'), 'FINE STAGIONE')


class RenderTest(unittest.TestCase):
    def test_render_and_ghost(self):
        photo, cut = photo_and_cut()
        for kw in ({'person': cut, 'photo': photo}, {'person': cut}, {'ghost': True}):
            png = P.render(surname='Bremer', name='GLEISON', month='Agosto/Settembre', **kw)
            with Image.open(io.BytesIO(png)) as im:
                self.assertEqual(im.size, (P.W, P.H))

    def test_player_breaks_out_of_frame(self):
        photo, cut = photo_and_cut()
        lay, cl = P._photo_layers(photo, cut, (100, 200, 900, 1500))
        a = cl.getchannel('A').getbbox()
        self.assertLess(a[1], 200)              # esce sopra
        self.assertGreater(a[3], 1500)          # esce sotto

    def test_errors(self):
        with self.assertRaises(ValueError):
            P.render(surname='', month='Ottobre', ghost=True)
        with self.assertRaises(ValueError):
            P.render(surname='X', month='', ghost=True)
        with self.assertRaises(ValueError):
            P.render(surname='X', month='Ottobre')


class PayloadTest(unittest.TestCase):
    def test_payload(self):
        import webapp_payload
        env = {'v': 1, 'action': 'render', 'session': 's1', 'data': {
            'kind': 'potm', 'surname': 'bremer', 'name': 'GLEISON', 'months': ['SETTEMBRE', 'AGOSTO'],
            'photo_id': '0123456789abcdef'}}
        d = webapp_payload.parse_webapp_request(env, None, 0, 's1')['data']
        self.assertEqual((d['surname'], d['name'], d['month']), ('BREMER', 'Gleison', 'AGOSTO/SETTEMBRE'))
        env['data']['months'] = []
        with self.assertRaises(ValueError):
            webapp_payload.parse_webapp_request(env, None, 0, 's1')


if __name__ == '__main__':
    unittest.main()
