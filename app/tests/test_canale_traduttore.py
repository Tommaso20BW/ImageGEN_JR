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
<div class="tgme_widget_message_wrap"><div class="tgme_widget_message" data-post="juventus_reborn/13">
<div class="tgme_widget_message_grouped_wrap"><a class="tgme_widget_message_photo_wrap grouped_media_wrap js-message_photo" style="width:2px;background-image:url('https://cdn4.telesco.pe/file/a.jpg')"></a>
<a class="tgme_widget_message_photo_wrap grouped_media_wrap js-message_photo" style="background-image:url('https://cdn4.telesco.pe/file/b.jpg')"></a></div>
<div class="tgme_widget_message_text js-message_text" dir="auto">Album <b>Juve</b><br/><br/>👉 <a href="https://t.me/juventus_reborn">@Juventus_Reborn</a></div></div></div>
<div class="tgme_widget_message_wrap"><div class="tgme_widget_message" data-post="juventus_reborn/14">
<div class="tgme_widget_message_text js-message_text" dir="auto"><i class="emoji"><b>🗞</b></i> PRIME PAGINE | 14/11/2026</div></div></div>
<div class="tgme_widget_message_wrap"><div class="tgme_widget_message" data-post="juventus_reborn/15">
<div class="tgme_widget_message_text js-message_text" dir="auto">ACCADDE OGGI: nel 1990...</div></div></div>
'''


class CanaleTests(unittest.TestCase):
    def test_parse_keeps_only_posts_with_text(self):
        posts = tgchannel.parse(PAGE)
        self.assertEqual([p['id'] for p in posts], ['10', '12', '13', '14', '15'])
        self.assertEqual(posts[2]['photos'], ['https://cdn4.telesco.pe/file/a.jpg', 'https://cdn4.telesco.pe/file/b.jpg'])
        self.assertEqual(posts[0]['photos'], [])
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
        # solo i post firmati @Juventus_Reborn (niente LiveScore, rubriche, post senza firma)
        posts = tgchannel.fetch(session=Fake(), limit=5)
        self.assertEqual([p['id'] for p in posts], ['13', '10'])
        self.assertEqual(len(posts[0]['photos']), 2)
        self.assertEqual(posts[0]['text'], 'Album Juve')
        self.assertEqual(posts[0]['source'], '')
        self.assertEqual(posts[1]['source'], 'Nicolò Schira')
        self.assertEqual(len(tgchannel.fetch(session=Fake(), limit=1)), 1)

    def test_photo_only_from_telegram_cdn(self):
        self.assertTrue(tgchannel.is_photo_url('https://cdn4.telesco.pe/file/a.jpg'))
        self.assertFalse(tgchannel.is_photo_url('https://evil.com/telesco.pe/a.jpg'))
        self.assertFalse(tgchannel.is_photo_url('http://cdn4.telesco.pe/file/a.jpg'))
        with self.assertRaisesRegex(ValueError, 'non valida'):
            tgchannel.download_photo('https://127.0.0.1/x.jpg')


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
