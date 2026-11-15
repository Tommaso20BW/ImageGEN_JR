"""Storia IG (collage): testo, etichetta, impaginazione e richiesta della Mini App.
Avvio (da app/): python -m unittest discover -s tests"""
import io
import unittest

from PIL import Image

import _percorsi  # noqa: F401 - prima degli import del servizio
import webapp_payload
from graphics import ig_story as S
from graphics.common import asset_dir

HAS_ASSETS = (asset_dir() / 'fonts' / S.MONO).is_file() and (asset_dir() / 'canva' / 'jr.json').is_file()
LONG = ('La Juventus ha chiesto informazioni per un esterno offensivo da prendere già a gennaio. '
        "In cima alla lista c'è un profilo giovane della Ligue 1, ma servirà prima una cessione. ") * 4
LONG = LONG[:S.MAX_TEXT]


def jpeg(w, h):
    buf = io.BytesIO()
    Image.new('RGB', (w, h), (90, 120, 160)).save(buf, 'JPEG')
    return buf.getvalue()


class TextTests(unittest.TestCase):
    def test_tidy_and_limits(self):
        self.assertEqual(S.clean_text('Ciao 👋  mondo\n\n\n\nfine 👉 @Juventus_Reborn'), 'Ciao mondo\n\nfine')
        with self.assertRaises(ValueError):
            S.clean_text('x' * (S.MAX_TEXT + 1))

    def test_label_and_color_keys(self):
        self.assertEqual(S.label_key('ufficiale'), 'ufficiale')
        self.assertEqual(S.label_key('boh'), 'ultimora')
        self.assertEqual(S.label_key(None), 'ultimora')
        self.assertEqual(S.LABELS['none'], ())
        self.assertEqual(S.text_color('red'), 'red')
        self.assertEqual(S.text_color('white'), 'black')


@unittest.skipUnless(HAS_ASSETS, 'servono i font e il logo degli asset privati')
class LayoutTests(unittest.TestCase):
    def check_fits(self, text, label, photo):
        parts, lines, size, ph_h, y = S.layout(text, label, photo)
        lab = S._label_height(parts)
        blocks = bool(parts) + bool(photo) + bool(text)
        total = lab + S.text_height(lines, size) + ph_h + S.GAP * max(blocks - 1, 0)
        self.assertGreaterEqual(y, S.TOP)
        self.assertLessEqual(y + total, S.BOTTOM + 1)
        return parts, lines, size, ph_h

    def test_everything_fits_in_the_safe_zone(self):
        for label in S.LABELS:
            for text in ('', 'Breve.', LONG):
                for photo in (None, (600, 330), (900, 1600)):
                    if text or photo:
                        with self.subTest(label=label, n=len(text), photo=photo):
                            self.check_fits(text, label, photo)

    def test_sizes(self):
        _, _, short, _ = self.check_fits('UFFICIALE: rinnovo fino al 2030.', 'ufficiale', None)
        _, _, long_, _ = self.check_fits(LONG, 'ufficiale', None)
        self.assertGreater(short, long_)
        _, _, size, ph_h = self.check_fits(LONG, 'mercato', (600, 330))
        self.assertGreaterEqual(size, S.FS_KEEP - 6)
        self.assertGreaterEqual(ph_h, S.PHOTO_LOW)

    def test_wrap_keeps_newlines_and_breaks_long_words(self):
        lines = S.wrap('Prima\n\nSeconda ' + 'x' * 200, 54)
        self.assertEqual(lines[:2], ['Prima', ''])
        fnt = S.cp._font(S.MONO, 54)
        self.assertTrue(all(fnt.getlength(ln) <= S.TEXT_W for ln in lines))
        self.assertEqual(''.join(lines[2:]).replace(' ', ''), 'Seconda' + 'x' * 200)


@unittest.skipUnless(HAS_ASSETS, 'servono i font e il logo degli asset privati')
class RenderTests(unittest.TestCase):
    def test_render_size_and_seed(self):
        one = S.render(text='Notizia di prova.', label='ultimora', seed=3)
        self.assertEqual(Image.open(io.BytesIO(one)).size, (S.W, S.H))
        self.assertEqual(one, S.render(text='Notizia di prova.', label='ultimora', seed=3))
        self.assertNotEqual(one, S.render(text='Notizia di prova.', label='ultimora', seed=4))

    def test_render_photo_only_without_label(self):
        out = S.render(photo=jpeg(800, 1200), label='none', seed=1)
        self.assertEqual(Image.open(io.BytesIO(out)).size, (S.W, S.H))

    def test_needs_text_or_photo(self):
        with self.assertRaises(ValueError):
            S.render(text='  ', seed=1)


class PayloadTests(unittest.TestCase):
    def parse(self, **data):
        env = {'v': 1, 'action': 'render', 'session': 's1', 'data': {'kind': 'igbn', **data}}
        return webapp_payload.parse_webapp_request(env, None, 0, 's1')['data']

    def test_label_and_seed(self):
        data = self.parse(text='Ciao', label='mercato', color='red')
        self.assertEqual((data['label'], data['color']), ('mercato', 'red'))
        self.assertIsInstance(data['seed'], int)
        self.assertEqual(self.parse(text='Ciao', label='???')['label'], 'ultimora')
        self.assertEqual(self.parse(text='Ciao')['label'], 'ultimora')

    def test_empty(self):
        with self.assertRaises(ValueError):
            self.parse(text='')


if __name__ == '__main__':
    unittest.main()
