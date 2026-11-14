import unittest

from app.scoring import detect_language, foreign_score, infer_category


class TestScoring(unittest.TestCase):
    def test_expat_event_scores_high(self):
        score, is_foreign = foreign_score(
            "Expat Language Exchange Meetup — English corner",
            "International community night, all welcome",
            "meetup", "en",
        )
        self.assertTrue(is_foreign)
        self.assertGreaterEqual(score, 50)

    def test_local_event_scores_low(self):
        score, is_foreign = foreign_score(
            "本地相亲活动 同城交友", "单身青年本地专场", "douban", "zh"
        )
        self.assertFalse(is_foreign)
        self.assertLess(score, 50)

    def test_source_boost(self):
        base, _ = foreign_score("Board game night", "casual", "manual", "en")
        meetup, _ = foreign_score("Board game night", "casual", "meetup", "en")
        self.assertGreater(meetup, base)

    def test_category_inference(self):
        self.assertEqual(infer_category("Jazz festival 大型音乐节"), "music")
        self.assertEqual(infer_category("语言交换 language exchange"), "education")
        self.assertEqual(infer_category("徒步 hiking 周末"), "sport")
        self.assertEqual(infer_category("qwerty zzz"), "other")

    def test_language_detection(self):
        self.assertEqual(detect_language("hello world"), "en")
        self.assertEqual(detect_language("你好世界"), "zh")
        self.assertEqual(detect_language("hello 你好"), "zh+en")


if __name__ == "__main__":
    unittest.main()
