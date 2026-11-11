import unittest
from unittest import mock

import _percorsi  # noqa: F401

import instagram
import webapp_payload
from graphics import ig_quote

LINK = 'https://www.instagram.com/stories/francisco.conceicao7/4028137600010949312?utm_source=ig_story_item_share'
PAGE = ('<meta property="og:title" content="Watch this story by Francisco Conceic&#x327;a&#x303;o on Instagram '
        'before it disappears." />"props":{"user":{"id":"1","profile_pic_url":"https:\\/\\/cdn.example\\/a.jpg",'
        '"username":"francisco.conceicao7"}')


class Response:
    def __init__(self, text='', content=b'', status=200):
        self.text, self.content, self.status_code = text, content, status


class StoryLinkTest(unittest.TestCase):
    def test_story_user(self):
        self.assertEqual(instagram.story_user(LINK), 'francisco.conceicao7')
        self.assertEqual(instagram.story_user('instagram.com/stories/juventus/'), 'juventus')
        self.assertIsNone(instagram.story_user('https://www.instagram.com/p/ABCDE123/'))
        self.assertIsNone(instagram.story_user('https://x.com/stories/juventus/1'))

    def test_fetch_story_name_and_avatar(self):
        session = mock.Mock()
        session.get.side_effect = lambda url, **_: (Response(PAGE) if 'stories' in url
                                                    else Response(content=b'\xff\xd8avatar'))
        story = instagram.fetch_story(LINK, session)
        self.assertEqual(story['user'], 'francisco.conceicao7')
        self.assertEqual(story['name'], 'Francisco Conceição')
        self.assertEqual(story['avatar'], b'\xff\xd8avatar')
        self.assertEqual(story['photos'], [])
        self.assertEqual(session.get.call_args_list[1].args[0], 'https://cdn.example/a.jpg')


class StoryPayloadTest(unittest.TestCase):
    def envelope(self, **data):
        return {'v': 1, 'action': 'render', 'session': 's',
                'data': {'kind': 'igq', 'photo_id': 'a' * 16, 'frame': {'x': 0, 'y': 0, 'zoom': 1}, 'name': 'Francisco', 'handle': 'fc7', **data}}

    def test_story_text_optional(self):
        state = webapp_payload.parse_webapp_request(self.envelope(text='', story=True), None, 0, 's')
        self.assertTrue(state['data']['story'])
        with self.assertRaises(ValueError):          # post normale: il testo serve
            webapp_payload.parse_webapp_request(self.envelope(text=''), None, 0, 's')
        state = webapp_payload.parse_webapp_request(self.envelope(text='Ciao'), None, 0, 's')
        self.assertNotIn('story', state['data'])

    def test_story_bars(self):
        state = webapp_payload.parse_webapp_request(self.envelope(text='', story=True, bars=[1, 0.5, 0]), None, 0, 's')
        self.assertEqual(state['data']['bars'], [1.0, 0.5, 0.0])
        for bad in ([2], 'x', [], [True]):
            state = webapp_payload.parse_webapp_request(self.envelope(text='', story=True, bars=bad), None, 0, 's')
            self.assertNotIn('bars', state['data'])

    def test_story_card(self):
        import io
        from PIL import Image
        raw = io.BytesIO(); Image.new('RGB', (90, 160), (30, 120, 60)).save(raw, 'JPEG')
        with mock.patch('graphics.ig_quote._font_css', return_value=''),                 mock.patch('graphics.photo_jr._logo', return_value=''):
            page = ig_quote.build_html(photo=raw.getvalue(), text='', name='Francisco', handle='fc7', story=True,
                                       verified=True)
            two = ig_quote.build_html(photo=raw.getvalue(), story=True, bars=[1, 0.4])
            self.assertEqual(two.count('<s style'), 2)
            self.assertIn('width:40%', two)
            for part in ('body>img{position:absolute}', 'id="card"', 'id="back"', 'id="bars"', 'Invia messaggio', '<b>fc7</b>', 'class="tick"'):
                self.assertIn(part, page)
            post = ig_quote.build_html(photo=raw.getvalue(), text='Ciao', name='Francisco', handle='fc7')
            self.assertNotIn('id="card"', post)


class StoryShotTest(unittest.TestCase):
    def test_crop_screenshot(self):
        import io
        import story_shot
        from PIL import Image, ImageDraw
        shot = Image.new('RGB', (600, 1400), (11, 16, 20))           # sfondo scuro del telefono
        d = ImageDraw.Draw(shot)
        for y in range(120, 120 + 1067):                               # storia 9:16, a righe colorate
            d.line([(0, y), (599, y)], fill=(40 + y % 180, 120, 60))
        d.ellipse((12, 120 + 30, 72, 120 + 90), fill=(250, 0, 0))     # foto profilo
        d.rectangle((10, 132, 200, 134), fill=(255, 255, 255))         # barrette: vista, a metà, da vedere
        d.rectangle((205, 132, 300, 134), fill=(255, 255, 255))
        d.rectangle((301, 132, 395, 134), fill=(170, 170, 170))
        d.rectangle((400, 132, 590, 134), fill=(170, 170, 170))
        out = io.BytesIO(); shot.save(out, 'PNG')
        self.assertEqual(story_shot.read(out.getvalue())[2], [1.0, 0.5, 0.0])
        photo, avatar = story_shot.crop(out.getvalue())
        w, h = Image.open(io.BytesIO(photo)).size
        self.assertEqual(w, 600)
        self.assertLessEqual(abs(h - 1067), 4)      # storia intera; misura su immagine ridotta: +-4 px
        self.assertGreater(Image.open(io.BytesIO(avatar)).getpixel((24, 24))[0], 200)
        plain = io.BytesIO(); Image.new('RGB', (800, 600), (200, 30, 30)).save(plain, 'PNG')
        self.assertEqual(story_shot.crop(plain.getvalue()), (plain.getvalue(), None))   # foto normale: com'è


class StoryEraseTest(unittest.TestCase):
    def test_header_text_erased(self):
        import io
        import story_shot
        from PIL import Image, ImageDraw
        shot = Image.new('RGB', (600, 1400), (11, 16, 20))
        d = ImageDraw.Draw(shot)
        d.rectangle((0, 120, 599, 120 + 1066), fill=(100, 110, 105))     # storia grigia
        d.rectangle((90, 160, 300, 180), fill=(255, 255, 255))            # nome dell'account
        d.rectangle((150, 400, 300, 420), fill=(255, 255, 255))           # scritta della storia: resta
        out = io.BytesIO(); shot.save(out, 'PNG')
        photo = Image.open(io.BytesIO(story_shot.crop(out.getvalue())[0]))
        self.assertLess(abs(photo.getpixel((200, 50))[0] - 100), 12)      # nome sparito
        self.assertGreater(photo.getpixel((220, 290))[0], 230)            # testo della storia intatto


class StoryNoPageTest(unittest.TestCase):
    def test_story_link_without_page(self):
        """Storia che Instagram non mostra più: si va avanti con l'@ preso dal link."""
        import service
        fake = mock.Mock()
        with mock.patch('instagram.fetch_story', side_effect=ValueError('niente')), \
                mock.patch('sent_store.load_names', return_value={}):
            out = service.Service.ig_post(fake, {'url': LINK})
        self.assertTrue(out['story'])
        self.assertEqual(out['handle'], 'francisco.conceicao7')
        self.assertIsNone(out['avatar_id'])
