import unittest
from datetime import date, datetime

from core.scheduler import is_in_restriction, is_restriction_day


class TestScheduler(unittest.TestCase):

    def d(self, s):
        return datetime.strptime(s, "%Y-%m-%d %H:%M")

    def day(self, s):
        return date.fromisoformat(s)

    def test_weekday_morning(self):
        self.assertFalse(is_in_restriction(self.d("2026-08-24 10:00")))

    def test_weekday_before_start(self):
        self.assertFalse(is_in_restriction(self.d("2026-08-24 13:29")))

    def test_weekday_at_start(self):
        self.assertTrue(is_in_restriction(self.d("2026-08-24 13:30")))

    def test_weekday_mid(self):
        self.assertTrue(is_in_restriction(self.d("2026-08-24 15:00")))

    def test_weekday_before_end(self):
        self.assertTrue(is_in_restriction(self.d("2026-08-24 17:59")))

    def test_weekday_at_end(self):
        self.assertFalse(is_in_restriction(self.d("2026-08-24 18:00")))

    def test_friday_still_restricted(self):
        self.assertTrue(is_in_restriction(self.d("2026-08-28 14:00")))

    def test_saturday_restricted(self):
        self.assertTrue(is_in_restriction(self.d("2026-08-29 14:00")))

    def test_sunday_restricted(self):
        self.assertTrue(is_in_restriction(self.d("2026-08-30 14:00")))

    def test_restriction_day_flag(self):
        self.assertTrue(is_restriction_day(self.day("2026-08-24")))
        self.assertTrue(is_restriction_day(self.day("2026-08-29")))
        self.assertTrue(is_restriction_day(self.day("2026-08-30")))


if __name__ == "__main__":
    unittest.main()
