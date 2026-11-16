import io
import unittest

import numpy as np
from PIL import Image

from graphics import affare_fatto as A
from graphics import firma

_real_paths = firma.paths
# un tratto finto per riga: i test non vanno su calligrapher.ai
FAKE = 'M 0,0 C 10 -20, 30 -20, 40 0 C 30 5, 10 5, 0,0'


def setUpModule():
    firma.paths = lambda lines, style=None: [[FAKE] if t else [] for t in lines]


def tearDownModule():
    firma.paths = _real_paths


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

    def test_surname_clean(self):
        """La J resta sulla riga e niente righine dal bordo opposto (es. dalla E finale accanto alla J)."""
        m = A._surname('JANE')
        self.assertLessEqual(np.where(m.max(1) > .3)[0][-1], A.TITLE_BASE + 8)
        left = m[:, :A.TITLE_X0 + 12]
        self.assertLess(left[A.TITLE_BASE - 300:A.TITLE_BASE - 120].max(), .3)

    def test_signature(self):
        """Firma in basso a sinistra, sopra il filo di AFFARE FATTO; se il sito non risponde, niente firma."""
        m = A._signature('KERIM', 'ALAJBEGOVIĆ')
        ys, xs = np.where(m > .3)
        self.assertGreater(len(xs), 0)
        self.assertGreaterEqual(xs.min(), A.SIGN_X0 - 40)
        self.assertLessEqual(xs.max(), A.SIGN_X1 + 40)
        self.assertLessEqual(ys.max(), A.SIGN_BOTTOM + 40)
        def down(lines, style=None):
            raise RuntimeError('offline')
        firma.paths = down
        try:
            self.assertEqual(A._signature('X', 'OFFLINE').max(), 0)
        finally:
            setUpModule()

    def test_split_words(self):
        """Nome Cognome scritti insieme si dividono nello spazio tra le parole."""
        ds = ['M 0,0 C 10 1, 20 2, 30 0', 'M 35,0 C 40 1, 50 2, 60 0', 'M 90,0 C 100 1, 110 2, 120 0', 'M 125,5 C 150 1, 170 2, 200 0']
        a, b = firma.split_words(ds, 'Kerim', 'Alajbegovic')
        self.assertEqual((len(a), len(b)), (2, 2))
        self.assertIsNone(firma.split_words(['M 0,0 C 10 1, 20 2, 30 0'], 'A', 'B'))
        self.assertTrue(firma.runaway([['M 0,0 C 10 1, 20 2, 50 0'], ['M 0,0 C 10 1, 20 2, 900 0']], ['Kerim', 'Alajbegovic']))
        self.assertFalse(firma.runaway([['M 0,0 C 10 1, 20 2, 50 0'], ['M 0,0 C 10 1, 20 2, 110 0']], ['Kerim', 'Alajbegovic']))

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
