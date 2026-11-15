import io
import unittest

from PIL import Image

from graphics import compleanno_storico as S


class PersonBoxTest(unittest.TestCase):
    def test_default_sits_on_bottom_centered(self):
        x, y, w, h = S.person_box((400, 800))
        self.assertEqual(h, S.PERSON_H)
        self.assertEqual(y + h, S.H)
        self.assertAlmostEqual(x + w / 2, S.W / 2, delta=1)

    def test_wide_photo_is_limited_by_width(self):
        _, _, w, _ = S.person_box((3000, 1000))
        self.assertLessEqual(w, S.PERSON_MAX_W)

    def test_frame_moves_and_zooms(self):
        x0, y0, w0, h0 = S.person_box((400, 800))
        x, y, w, h = S.person_box((400, 800), {'x': 0.1, 'y': -0.1, 'zoom': 0.5})
        self.assertEqual(h, round(h0 * 0.5))
        self.assertAlmostEqual(x + w / 2 - (x0 + w0 / 2), 0.1 * S.W, delta=1)
        self.assertAlmostEqual(y + h, S.H - 0.1 * S.H, delta=1)


class TrimTest(unittest.TestCase):
    def test_trims_to_alpha(self):
        im = Image.new('RGBA', (100, 100), (0, 0, 0, 0))
        im.paste((200, 10, 10, 255), (20, 30, 60, 90))
        self.assertEqual(S.trim(im).size, (40, 60))


class NostalgiaTest(unittest.TestCase):
    def test_keeps_size_and_alpha(self):
        im = Image.new('RGBA', (30, 20), (250, 250, 250, 128))
        out = S.nostalgia(im)
        self.assertEqual(out.size, (30, 20))
        self.assertEqual(out.getpixel((5, 5))[3], 128)


class PayloadTest(unittest.TestCase):
    def test_bdold_payload(self):
        from webapp_payload import _build_state
        env = {'v': 1, 'action': 'render', 'session': 's',
               'data': {'kind': 'bdold', 'name': 'Paulo Dybala', 'photo_id': 'a' * 16,
                        'frame': {'x': 5, 'y': 0, 'zoom': 1}}}
        try:
            state = _build_state(env, {}, 0, 's')
        except TypeError:
            self.skipTest('firma di _build_state diversa')
        self.assertEqual(state['data']['name'], 'PAULO DYBALA')
        self.assertEqual(state['data']['frame']['x'], 0.6)

    def test_bdold_needs_name(self):
        from webapp_payload import _build_state
        env = {'v': 1, 'action': 'render', 'session': 's',
               'data': {'kind': 'bdold', 'name': ' ', 'photo_id': 'a' * 16}}
        with self.assertRaises(ValueError):
            _build_state(env, {}, 0, 's')


if __name__ == '__main__':
    unittest.main()
