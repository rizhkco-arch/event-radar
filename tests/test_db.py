import os
import tempfile
import unittest
from datetime import timedelta

from app.db import Database
from app.normalize import RawEvent, normalize_event, now_cst, to_iso


def make_event(title="Jazz Night", city="suzhou", lat=31.30, lon=120.59, start=None, category="music", is_foreign=1, source="manual"):
    raw = RawEvent(title=title, start_raw=start or to_iso(now_cst() + timedelta(days=1)),
                   city=city, lat=lat, lon=lon, source=source)
    ev = normalize_event(raw)
    ev["category"] = category
    ev["is_foreign"] = is_foreign
    return ev


class TestDb(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.db = Database(os.path.join(self.tmp, "test.db"))

    def test_insert_dedupes(self):
        ev = make_event()
        _, is_new = self.db.insert_event(ev)
        self.assertTrue(is_new)
        _, is_new2 = self.db.insert_event(ev)
        self.assertFalse(is_new2)

    def test_radius_query(self):
        near = make_event(title="Near", lat=31.30, lon=120.59)
        far = make_event(title="Far", lat=31.2304, lon=121.4737)
        self.db.insert_event(near)
        self.db.insert_event(far)
        res = self.db.events_in_radius(31.2989, 120.5853, 30)
        titles = [e["title"] for e in res]
        self.assertIn("Near", titles)
        self.assertNotIn("Far", titles)
        res_all = self.db.events_in_radius(31.2989, 120.5853, 200)
        self.assertIn("Far", [e["title"] for e in res_all])

    def test_radius_sorted_by_start(self):
        e1 = make_event(title="Later", start=to_iso(now_cst() + timedelta(days=5)))
        e2 = make_event(title="Sooner", start=to_iso(now_cst() + timedelta(days=1)))
        self.db.insert_event(e1)
        self.db.insert_event(e2)
        res = self.db.events_in_radius(31.2989, 120.5853, 30)
        self.assertEqual(res[0]["title"], "Sooner")

    def test_foreign_only_filter(self):
        self.db.insert_event(make_event(title="Foreign", is_foreign=1))
        self.db.insert_event(make_event(title="Local", is_foreign=0))
        res = self.db.events_in_radius(31.2989, 120.5853, 30, foreign_only=True)
        self.assertEqual([e["title"] for e in res], ["Foreign"])

    def test_users_matching_event_and_notified(self):
        self.db.upsert_user(1, lat=31.2989, lon=120.5853, radius_km=30)
        self.db.upsert_user(2, lat=39.9042, lon=116.4074, radius_km=30)
        users = self.db.users_matching_event(31.30, 120.59)
        self.assertEqual([u["telegram_id"] for u in users], [1])
        self.db.mark_notified(1, 42)
        self.assertTrue(self.db.is_notified(1, 42))
        self.assertFalse(self.db.is_notified(1, 43))

    def test_saved_events(self):
        ev = make_event()
        eid, _ = self.db.insert_event(ev)
        self.db.upsert_user(1)
        self.db.save_event(1, eid)
        self.assertEqual(len(self.db.saved_events(1)), 1)
        self.db.unsave_event(1, eid)
        self.assertEqual(len(self.db.saved_events(1)), 0)


if __name__ == "__main__":
    unittest.main()
