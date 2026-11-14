import unittest
from datetime import datetime, timedelta

from app.normalize import RawEvent, dedupe_key, guess_city, normalize_event, parse_datetime, to_iso
from app.normalize import CST


class TestNormalize(unittest.TestCase):
    def test_parse_zh_date(self):
        dt = parse_datetime("2025年5月24日 19:30")
        self.assertIsNotNone(dt)
        self.assertEqual((dt.year, dt.month, dt.day, dt.hour, dt.minute), (2025, 5, 24, 19, 30))
        self.assertEqual(dt.tzinfo, CST)

    def test_parse_iso(self):
        dt = parse_datetime("2025-05-24 20:00")
        self.assertEqual((dt.month, dt.day, dt.hour), (5, 24, 20))

    def test_parse_month_day_uses_ref_year(self):
        ref = datetime(2025, 12, 20, tzinfo=CST)
        dt = parse_datetime("1月5日 19:00", ref=ref)
        self.assertEqual((dt.year, dt.month, dt.day), (2026, 1, 5))

    def test_parse_garbage_returns_none(self):
        self.assertIsNone(parse_datetime("когда-нибудь"))

    def test_dedupe_key_stable(self):
        dt = parse_datetime("2025-05-24 20:00")
        k1 = dedupe_key("Jazz Night!", dt, "Livehouse")
        k2 = dedupe_key("jazz  night", dt, "livehouse ")
        self.assertEqual(k1, k2)

    def test_guess_city(self):
        self.assertEqual(guess_city("苏州工业园区某酒吧"), "suzhou")
        self.assertEqual(guess_city("上海静安区"), "shanghai")
        self.assertIsNone(guess_city("somewhere"))

    def test_normalize_event_fills_defaults(self):
        raw = RawEvent(title="Expat Meetup 苏州", start_raw="2025年5月24日 19:30",
                       address="苏州工业园区星湖街", source="manual", city="suzhou")
        ev = normalize_event(raw)
        self.assertEqual(ev["city"], "suzhou")
        self.assertIsNotNone(ev["lat"])
        self.assertIn("dedupe_key", ev)
        self.assertTrue(ev["start_time"].startswith("2025-05-24"))
        self.assertGreaterEqual(ev["foreign_score"], 50)
        self.assertEqual(ev["is_foreign"], 1)

    def test_normalize_unknown_date_falls_back(self):
        raw = RawEvent(title="TBD event", source="manual", city="suzhou")
        ev = normalize_event(raw)
        self.assertTrue(ev["start_time"] > to_iso(datetime.now(CST) - timedelta(hours=1)))


if __name__ == "__main__":
    unittest.main()
