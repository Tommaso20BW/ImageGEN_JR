"""Storia IG dal canale Telegram (tgchannel.py) e traduttore delle citazioni (translate.py)."""
import unittest

import _percorsi  # noqa: F401
import requests

import tgchannel
import translate

PAGE = '''
<div class="tgme_widget_message_wrap"><div class="tgme_widget_message" data-post="juventus_reborn/10">
<div class="tgme_widget_message_text js-message_text" dir="auto"><tg-emoji><i class="emoji"><b>🇽🇰</b></i></tg-emoji><tg-emoji><i class="emoji"><b>🆙</b></i></tg-emoji> <b>Zhegrova</b> potrebbe lasciare la <b>Juventus</b> a gennaio.<br/><br/><i><tg-emoji><i class="emoji"><b>📲</b></i></tg-emoji></i><i> Nicolò Schira</i><br/><br/><tg-emoji><i class="emoji"><b>👉</b></i></tg-emoji> <a href="https://t.me/juventus_reborn">@Juventus_Reborn</a></div>
<a class="tgme_widget_message_date"><time datetime="2026-11-14T22:57:32+00:00">22:57</time></a></div></div>
<div class="tgme_widget_message_wrap"><div class="tgme_widget_message" data-post="juventus_reborn/11">
<div class="tgme_widget_message_photo_wrap"></div></div></div>
<div class="tgme_widget_message_wrap"><div class="tgme_widget_message" data-post="juventus_reborn/12">
<div class="tgme_widget_message_text js-message_text" dir="auto">Riga uno<br/>Riga <b>due</b><div class="x">dentro</div><br/>#Juve #Calciomercato</div>
<time datetime="2026-11-15T08:00:00+00:00">08:00</time></div></div>
'''


class CanaleTests(unittest.TestCase):
    def test_parse_keeps_only_posts_with_text(self):
        posts = tgchannel.parse(PAGE)
        self.assertEqual([p['id'] for p in posts], ['10', '12'])
        self.assertEqual(posts[0]['date'], '2026-11-14T22:57:32+00:00')

    def test_story_text_drops_emoji_source_signature_hashtags(self):
        posts = tgchannel.parse(PAGE)
        self.assertEqual(tgchannel.story_text(posts[0]['text']),
                         'Zhegrova potrebbe lasciare la Juventus a gennaio.')
        self.assertEqual(tgchannel.story_text(posts[1]['text']), 'Riga uno\nRiga duedentro')

    def test_fetch_newest_first_and_limit(self):
        class Fake:
            def get(self, url, params=None, **kw):
                r = requests.Response()
                r.status_code = 200
                r._content = (PAGE if not params else '').encode('utf-8')
                r.encoding = 'utf-8'
                return r
        posts = tgchannel.fetch(session=Fake(), limit=1)
        self.assertEqual([p['id'] for p in posts], ['12'])


class TraduttoreTests(unittest.TestCase):
    def fake(self, payloads):
        class Fake:
            calls = []

            def get(self, url, params=None, **kw):
                Fake.calls.append(url)
                status, body = payloads.pop(0)
                r = requests.Response()
                r.status_code = status
                r._content = body.encode('utf-8')
                return r
        return Fake()

    def test_gtx(self):
        s = self.fake([(200, '[[["Ciao. ","Hello. ",null],["Tutto bene.","All good.",null]],null,"en"]')])
        self.assertEqual(translate.to_italian('Hello. All good.', session=s), {'text': 'Ciao. Tutto bene.', 'source': 'en'})

    def test_second_address_when_first_says_too_many_requests(self):
        s = self.fake([(429, ''), (200, '[["Ciao mondo","en"]]')])
        self.assertEqual(translate.to_italian('hello world', session=s)['text'], 'Ciao mondo')
        self.assertEqual(len(type(s).calls), 2)

    def test_errors(self):
        with self.assertRaisesRegex(ValueError, 'Nessun testo'):
            translate.to_italian('  ')
        s = self.fake([(429, ''), (500, '')])
        with self.assertRaisesRegex(ValueError, 'non disponibile'):
            translate.to_italian('hello', session=s)


if __name__ == '__main__':
    unittest.main()
