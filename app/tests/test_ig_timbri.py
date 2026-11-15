import unittest

import numpy as np

try:
    from graphics import ig_timbri as T
    T.stamps_mask((1080, 1920), 1)
    HAVE_ASSETS = True
except Exception:          # font non disponibili (senza LiveScore_JR accanto)
    HAVE_ASSETS = False


@unittest.skipUnless(HAVE_ASSETS, 'font non disponibili')
class TimbriTests(unittest.TestCase):
    W, H = 1080, 1920

    def test_same_seed_same_stamps(self):
        a = T.stamps_mask((self.W, self.H), 42)
        b = T.stamps_mask((self.W, self.H), 42)
        self.assertTrue(np.array_equal(a, b))
        self.assertFalse(np.array_equal(a, T.stamps_mask((self.W, self.H), 43)))

    def test_two_stamps_far_apart(self):
        """Uno in alto e uno in basso, in angoli opposti: in mezzo non c'è niente."""
        for seed in range(60):
            m = T.stamps_mask((self.W, self.H), seed)
            self.assertLess(m[int(self.H * .42):int(self.H * .58)].max(), .01, seed)
            top, bottom = m[:self.H // 2], m[self.H // 2:]
            self.assertGreater(top.sum(), 1000, seed)
            self.assertGreater(bottom.sum(), 1000, seed)
            # angoli opposti: il centro di massa in alto e quello in basso stanno ai lati opposti
            xs = np.arange(self.W)
            cx_top = (top.sum(0) * xs).sum() / top.sum()
            cx_bot = (bottom.sum(0) * xs).sum() / bottom.sum()
            self.assertGreater(abs(cx_top - cx_bot), self.W * .3, seed)

    def test_every_style_draws(self):
        rng = np.random.default_rng(0)
        for style in T.STYLES:
            im = np.asarray(style(220, rng))
            self.assertGreater((im > 128).mean(), .02, style.__name__)

    def test_stamp_is_faint(self):
        paper = np.full((self.H, self.W, 3), .85, np.float32)
        out = T.stamp(paper, 7)
        self.assertGreaterEqual(out.min(), .85 * (1 - T.STRENGTH) - 1e-6)
        self.assertLess(out.min(), .85)


if __name__ == '__main__':
    unittest.main()
