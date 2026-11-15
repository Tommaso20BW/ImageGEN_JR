import io
import unittest

from PIL import Image

from graphics import motm as M


def person(w=300, h=900):
    im = Image.new('RGBA', (w, h), (0, 0, 0, 0))
    im.paste((30, 30, 30, 255), (w // 4, 0, w * 3 // 4, h))
    return im


class PersonBoxTest(unittest.TestCase):
    def test_default_feet_and_centroid(self):
        x, y, w, h = M.person_box((300, 900), None, 0.4)
        self.assertEqual(h, M.PLAYER_H)
        self.assertEqual(y + h, M.FEET_Y)
        self.assertAlmostEqual(x + w * 0.4, M.W / 2, delta=1)

    def test_never_above_logo_nor_below_match(self):
        for fr in ({'y': -0.6, 'zoom': 3}, {'y': 0.6, 'zoom': 3}, {'y': -0.6, 'zoom': 0.4}, {'y': 0.6, 'zoom': 0.4}):
            _, y, _, h = M.person_box((300, 900), fr)
            self.assertGreaterEqual(y, M.TOP_MIN)
            self.assertLessEqual(y + h, M.FOOT_MAX)

    def test_page_info_has_limits(self):
        p = M.page_info(person())
        self.assertEqual((p['top'], p['bottom']), (M.TOP_MIN, M.FOOT_MAX))
        self.assertLess(M.LOGO_Y + M.LOGO_H, p['top'])
        self.assertLess(p['bottom'], M.TEAMS_Y)


class TextTest(unittest.TestCase):
    def test_clean(self):
        self.assertEqual(M.clean_text('  di   gregorio ', 14), 'DI GREGORIO')
        self.assertEqual(M.clean_text('Michele', 16, upper=False), 'Michele')

    def test_frame_defaults(self):
        self.assertEqual(M.clean_frame(None), {'x': 0.0, 'y': 0.0, 'zoom': 1.0})
        self.assertEqual(M.clean_frame({'x': 'a', 'zoom': float('nan')})['zoom'], 1.0)


class RenderTest(unittest.TestCase):
    def test_render_and_ghost(self):
        for ghost in (True, False):
            png = M.render(surname='Bremer', name='Gleison', home='Frosinone', away='Juventus',
                           comp='Serie A – Matchday 1', person=None if ghost else person(), ghost=ghost)
            with Image.open(io.BytesIO(png)) as im:
                self.assertEqual(im.size, (M.W, M.H))

    def test_needs_surname_and_teams(self):
        with self.assertRaises(ValueError):
            M.render(surname='', home='A', away='B', ghost=True)
        with self.assertRaises(ValueError):
            M.render(surname='X', home='', away='B', ghost=True)


if __name__ == '__main__':
    unittest.main()
