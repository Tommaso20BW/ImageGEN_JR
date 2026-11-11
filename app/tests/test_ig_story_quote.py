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

    def test_story_card(self):
        with mock.patch('graphics.ig_quote._font_css', return_value=''), \
                mock.patch('graphics.photo_jr._logo', return_value=''):
            page = ig_quote.build_html(photo=None, text='Ciao', name='Francisco', handle='fc7', story=True)
            self.assertIn('id="bars"', page)
            self.assertIn('Invia messaggio', page)
            self.assertIn('Storia · @fc7', page)
            only_photo = ig_quote.build_html(photo=None, text='', name='Francisco', handle='fc7', story=True)
            self.assertIn('class="low"', only_photo)
            post = ig_quote.build_html(photo=None, text='Ciao', name='Francisco', handle='fc7')
            self.assertNotIn('Invia messaggio', post)


if __name__ == '__main__':
    unittest.main()
