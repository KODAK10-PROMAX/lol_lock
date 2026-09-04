import json
import os
import tempfile
import unittest
from datetime import datetime, timedelta

from storage.history import HistoryStore


class TestHistory(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.tmp.name, "history.json")

    def tearDown(self):
        self.tmp.cleanup()

    def store(self):
        return HistoryStore(self.path)

    def test_file_auto_created_on_write(self):
        s = self.store()
        s.record_block("LeagueClient.exe", "test_mode")
        self.assertTrue(os.path.exists(self.path))

    def test_write_and_read_block(self):
        s = self.store()
        s.record_block("League of Legends.exe", "blocked", detail="警告5秒后已结束进程")
        s2 = self.store()
        data = s2._load()
        self.assertEqual(len(data["blocks"]), 1)
        e = data["blocks"][0]
        self.assertEqual(e["type"], "block")
        self.assertEqual(e["process"], "League of Legends.exe")
        self.assertEqual(e["result"], "blocked")
        self.assertTrue(e["time"])

    def test_write_and_read_unlock(self):
        s = self.store()
        s.record_unlock("confirmed", reason="会议演示需要")
        s2 = self.store()
        data = s2._load()
        self.assertEqual(len(data["unlocks"]), 1)
        self.assertEqual(data["unlocks"][0]["result"], "confirmed")

    def test_json_structure_and_extension(self):
        s = self.store()
        s.record_block("LeagueClient.exe", "test_mode")
        with open(self.path, "r", encoding="utf-8") as f:
            raw = json.load(f)
        self.assertEqual(raw["version"], 1)
        self.assertIn("blocks", raw)
        self.assertIn("unlocks", raw)
        raw["future_field"] = True
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(raw, f, ensure_ascii=False)
        s2 = self.store()
        data = s2._load()
        self.assertTrue(data["future_field"])  # 后续扩展字段不丢失

    def test_weekly_count_same_week(self):
        monday = datetime(2026, 8, 24, 13, 40)
        s = self.store()
        s.record_unlock("confirmed", when=monday)
        s.record_unlock("confirmed", when=monday + timedelta(days=3))  # 周四
        self.assertEqual(s.get_weekly_unlock_count(monday), 2)

    def test_weekly_count_excludes_last_week(self):
        monday = datetime(2026, 8, 24, 13, 40)
        s = self.store()
        last_sunday = datetime(2026, 8, 23, 20, 0)
        s.record_unlock("confirmed", when=last_sunday)
        s.record_unlock("confirmed", when=monday)
        self.assertEqual(s.get_weekly_unlock_count(monday), 1)

    def test_weekly_count_same_week_sunday_included(self):
        s = self.store()
        sunday = datetime(2026, 8, 30, 12, 0)
        monday = datetime(2026, 8, 24, 13, 40)
        s.record_unlock("confirmed", when=sunday)
        self.assertEqual(s.get_weekly_unlock_count(sunday), 1)
        self.assertEqual(s.get_weekly_unlock_count(monday), 1)

    def test_weekly_count_ignores_non_confirmed(self):
        s = self.store()
        t = datetime(2026, 8, 24, 13, 40)
        s.record_unlock("submitted", when=t)
        s.record_unlock("cancelled", when=t)
        self.assertEqual(s.get_weekly_unlock_count(t), 0)

    def test_broken_json_falls_back(self):
        with open(self.path, "w", encoding="utf-8") as f:
            f.write("{broken")
        s = self.store()
        self.assertEqual(s.get_weekly_unlock_count(), 0)
        s.record_block("LeagueClient.exe", "test_mode")
        self.assertEqual(len(s._load()["blocks"]), 1)

    def test_today_block_count(self):
        s = self.store()
        t = datetime(2026, 8, 24, 14, 0)
        s.record_block("LeagueClient.exe", "test_mode", when=t)
        s.record_block("LeagueClient.exe", "blocked", when=t + timedelta(minutes=1))
        s.record_block("LeagueClient.exe", "blocked",
                       when=t + timedelta(days=1))  # 昨天
        self.assertEqual(s.get_today_block_count(t), 2)


if __name__ == "__main__":
    unittest.main()
