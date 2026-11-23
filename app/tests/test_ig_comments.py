"""Commenti di Instagram letti da uno screenshot: dalle righe ai commenti."""
import unittest

import _percorsi  # noqa: F401 - prima degli import del servizio
import ig_comments as c


def rows(*lines):
    return [(x, i * 50.0, 40.0, text) for i, (x, text) in enumerate(lines)]


class ParseTests(unittest.TestCase):
    def test_name_time_text_without_buttons(self):
        got = c.parse(rows((400, 'Commenti'), (180, 'marco.bianconero 2 h'), (180, 'Forza Juve!'), (180, 'Rispondi'),
                           (1050, '1.204'), (180, 'giulia_jj10 58 min'), (180, 'Yildiz è di'), (180, 'un altro pianeta'),
                           (180, 'Visualizza altre 3 risposte')), 1170)
        self.assertEqual([(x['user'], x['text'], x['time'], x['likes']) for x in got],
                         [('marco.bianconero', 'Forza Juve!', '2 h', '1.204'),
                          ('giulia_jj10', 'Yildiz è di un altro pianeta', '58 min', '')])

    def test_name_and_time_in_two_pieces(self):
        got = c.parse([(180, 100, 40, 'luca9'), (420, 102, 40, '12 min'), (180, 150, 40, 'Che gol')], 1170)
        self.assertEqual([(x['user'], x['text'], x['time']) for x in got], [('luca9', 'Che gol', '12 min')])

    def test_name_and_time_glued_together(self):
        got = c.parse(rows((180, 'sara.fino 47 min'), (180, 'Bremer è un muro'), (180, 'antonio_189731 min'),
                           (180, 'Testa alla Champions')), 1170)
        self.assertEqual([(x['user'], x['text'], x['time']) for x in got],
                         [('sara.fino', 'Bremer è un muro', '47 min'),
                          ('antonio_1897', 'Testa alla Champions', '31 min')])

    def test_text_before_first_comment_ignored(self):
        self.assertEqual(c.parse(rows((180, 'Testo del post'), (180, 'Altra riga')), 1170), [])

    def test_comment_with_only_emoji_dropped(self):
        self.assertEqual(c.parse(rows((180, 'anna 3 h'), (180, 'Rispondi')), 1170), [])

    def test_merge_two_screenshots(self):
        a, b = {'user': 'a', 'text': 'Ciao'}, {'user': 'b', 'text': 'Forza'}
        self.assertEqual(c.merge([[a, b], [{'user': 'b', 'text': 'forza'}]]), [a, b])

    def test_avatar_cropped_left_of_name(self):
        from PIL import Image, ImageDraw
        image = Image.new('RGB', (600, 300), (0, 0, 0))
        ImageDraw.Draw(image).ellipse((20, 40, 110, 130), fill=(200, 60, 90))
        self.assertIsNotNone(c.avatar(image, 140, 50, 34))
        self.assertIsNone(c.avatar(Image.new('RGB', (600, 300)), 140, 50, 34))

    def test_story_ring_removed_from_avatar(self):
        import io
        from PIL import Image, ImageDraw
        image = Image.new('RGB', (600, 300), (0, 0, 0))
        draw = ImageDraw.Draw(image)
        draw.ellipse((20, 40, 120, 140), fill=(230, 40, 120))
        draw.ellipse((26, 46, 114, 134), fill=(0, 0, 0))
        draw.ellipse((31, 51, 109, 129), fill=(40, 170, 220))
        got = Image.open(io.BytesIO(c.avatar(image, 150, 60, 34))).convert('RGB')
        for point in ((92, 6), (6, 92), (178, 92), (92, 178)):
            r, g, b = got.getpixel(point)
            self.assertLess(r, 130, point)       # niente rosa dell'anello sul bordo

    def test_avatar_without_ring_not_cropped(self):
        from PIL import Image, ImageDraw
        face = Image.new('RGB', (100, 100), (0, 0, 0))
        ImageDraw.Draw(face).ellipse((1, 1, 98, 98), fill=(200, 60, 90))
        self.assertIsNone(c._inside_ring(face, [0, 0, 0]))

    def test_public_keeps_only_what_the_app_needs(self):
        got = c.public([{'user': 'a', 'text': 'b', 'time': '1 h', 'likes': '3', 'avatar': b'xy', 'box': (1, 2, 3)}])
        self.assertEqual(got, [{'user': 'a', 'text': 'b', 'time': '1 h', 'likes': '3', 'avatar': 'eHk='}])


class PayloadTests(unittest.TestCase):
    def parse(self, **extra):
        import webapp_payload
        data = {'kind': 'igc', 'photo_id': 'a' * 16, 'frame': {'x': 0, 'y': 0, 'zoom': 1},
                'text': 'Gigante', 'name': 'edon', **extra}
        return webapp_payload.parse_webapp_request({'v': 1, 'action': 'render', 'session': 's', 'data': data},
                                                   {'teams': [], 'players': []}, 0, 's')['data']

    def test_default_position_is_bottom(self):
        self.assertEqual(self.parse()['position'], 'sotto')
        self.assertEqual(self.parse(position='sopra')['position'], 'sopra')
        self.assertEqual(self.parse(position='boh')['position'], 'sotto')

    def test_story_version(self):
        self.assertIs(self.parse(story=True)['story'], True)

    def test_text_required(self):
        with self.assertRaises(ValueError):
            self.parse(text='')


class QuoteStoryTests(unittest.TestCase):
    def parse(self, kind='xq', **extra):
        import webapp_payload
        data = {'kind': kind, 'photo_id': 'a' * 16, 'frame': {'x': 0, 'y': 0, 'zoom': 1},
                'text': 'Gigante', 'name': 'edon', **extra}
        return webapp_payload.parse_webapp_request({'v': 1, 'action': 'render', 'session': 's', 'data': data},
                                                   {'teams': [], 'players': []}, 0, 's')['data']

    def test_all_quotes_have_vertical_version(self):
        import webapp_payload
        for kind in ('igq', 'xq', 'thq'):
            data = self.parse(kind, vertical=True)
            self.assertIs(data['vertical'], True)
            self.assertTrue(webapp_payload.is_story_version(data))
            self.assertFalse(webapp_payload.is_story_version(self.parse(kind)))

    def test_quote_of_a_story_has_vertical_version(self):
        import webapp_payload
        data = self.parse('igq', story=True, vertical=True, text='')
        self.assertIs(data['story'], True)
        self.assertIs(data['vertical'], True)
        self.assertTrue(webapp_payload.is_story_version(data))
        self.assertFalse(webapp_payload.is_story_version(self.parse('igq', story=True, text='')))


if __name__ == '__main__':
    unittest.main()
