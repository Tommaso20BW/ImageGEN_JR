import io
import unittest

import numpy as np
from PIL import Image

from graphics import affare_fatto as A


def cut(w=500, h=900):
    """Scontornato finto: un rettangolo color pelle su trasparente."""
    im = Image.new('RGBA', (w, h), (0, 0, 0, 0))
    im.paste((230, 190, 160, 255), (w // 4, 0, w * 3 // 4, h))
    return im


class RenderTest(unittest.TestCase):
    def test_render_and_ghost(self):
        for kw in ({'person': cut()}, {'person': cut(), 'frame': {'x': .3, 'y': -.2, 'zoom': 1.4}}, {'ghost': True}):
            png = A.render(surname='Alajbegović', name='Kerim', **kw)
            with Image.open(io.BytesIO(png)) as im:
                self.assertEqual(im.size, (A.W, A.H))

    def test_errors(self):
        with self.assertRaises(ValueError):
            A.render(surname='', ghost=True)
        with self.assertRaises(ValueError):
            A.render(surname='ZHEGROVA')            # senza foto

    def test_text_centred(self):
        """Cognome e nome centrati sulla pagina (stesso margine a sinistra e a destra)."""
        for mask in (A._surname('ALAJBEGOVIĆ'), A._surname('DI GREGORIO'), A._first('KERIM'), A._label()):
            xs = np.where(mask.max(0) > .3)[0]
            self.assertLessEqual(abs(xs[0] - (A.W - 1 - xs[-1])), 3)

    def test_long_first_name_fits(self):
        xs = np.where(A._first('MAXIMILIANO JOSÉ').max(0) > .3)[0]
        self.assertLessEqual(xs[-1] - xs[0], A.FIRST_MAX_W)

    def test_frame_moves_player(self):
        size = (500, 900)
        x0, y0, w0, h0 = A.person_box(size)
        self.assertAlmostEqual(x0 + w0 / 2, A.W / 2, delta=1)        # centrato di base
        x1, y1, w1, h1 = A.person_box(size, {'x': .8, 'y': -.8, 'zoom': 2})
        self.assertAlmostEqual(x1 + w1 / 2, A.W / 2 + A.W * .8, delta=1)   # spostamento libero, oltre 0.6
        self.assertLess(y1, y0)
        self.assertGreater(h1, h0 * 1.9)
        self.assertEqual(A.clean_frame({'x': 5, 'zoom': 'x'}), {'x': A.MOVE, 'y': 0.0, 'zoom': 1.0})


class PayloadTest(unittest.TestCase):
    def test_payload(self):
        import webapp_payload
        env = {'v': 1, 'action': 'render', 'session': 's1', 'data': {
            'kind': 'af', 'surname': 'zhegrova', 'name': 'edon', 'photo_id': '0123456789abcdef',
            'frame': {'x': .9, 'y': 0, 'zoom': 1.2}}}
        d = webapp_payload.parse_webapp_request(env, None, 0, 's1')['data']
        self.assertEqual((d['surname'], d['name'], d['frame']['x']), ('ZHEGROVA', 'EDON', .9))
        env['data']['surname'] = ''
        with self.assertRaises(ValueError):
            webapp_payload.parse_webapp_request(env, None, 0, 's1')

    def test_caption(self):
        from caption import build as build_caption
        text = build_caption({'kind': 'af', 'name': 'EDON', 'surname': 'ZHEGROVA'})
        self.assertIn('Edon Zhegrova', text)


if __name__ == '__main__':
    unittest.main()
