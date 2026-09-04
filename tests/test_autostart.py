import unittest

from core import autostart


class TestAutostart(unittest.TestCase):

    def test_enable_disable_roundtrip(self):
        self.assertIsInstance(autostart.is_enabled(), bool)
        autostart.enable()
        try:
            self.assertTrue(autostart.is_enabled())
        finally:
            autostart.disable()
        self.assertFalse(autostart.is_enabled())

    def test_disable_when_absent_no_error(self):
        autostart.disable()  # 不应抛异常
        self.assertFalse(autostart.is_enabled())


if __name__ == "__main__":
    unittest.main()
