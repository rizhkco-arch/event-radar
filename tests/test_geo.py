import unittest

from app.geo import bounding_box, haversine_km, in_radius

SUZHOU = (31.2989, 120.5853)
SHANGHAI = (31.2304, 121.4737)


class TestGeo(unittest.TestCase):
    def test_haversine_suzhou_shanghai(self):
        d = haversine_km(*SUZHOU, *SHANGHAI)
        self.assertGreater(d, 70)
        self.assertLess(d, 110)

    def test_haversine_same_point(self):
        self.assertAlmostEqual(haversine_km(*SUZHOU, *SUZHOU), 0.0)

    def test_in_radius(self):
        near = (31.35, 120.60)
        self.assertTrue(in_radius(*SUZHOU, *near, 30))
        self.assertFalse(in_radius(*SUZHOU, *SHANGHAI, 30))
        self.assertTrue(in_radius(*SUZHOU, *SHANGHAI, 200))

    def test_bounding_box_contains_center(self):
        min_lat, max_lat, min_lon, max_lon = bounding_box(*SUZHOU, 50)
        self.assertLess(min_lat, SUZHOU[0])
        self.assertLess(SUZHOU[0], max_lat)
        self.assertLess(min_lon, SUZHOU[1])
        self.assertLess(SUZHOU[1], max_lon)


if __name__ == "__main__":
    unittest.main()
