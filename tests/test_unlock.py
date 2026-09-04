import os
import tempfile
import unittest
from datetime import datetime, time, timedelta

import config
from core.unlock import UnlockManager
from storage.history import HistoryStore

MONDAY_1400 = datetime(2026, 8, 24, 14, 0)
MONDAY_1330 = datetime(2026, 8, 24, 13, 30)
MONDAY_1405 = datetime(2026, 8, 24, 14, 5)
NEXT_MONDAY = datetime(2026, 8, 31, 14, 0)


def _future_restriction_time(days_ahead: int = 30) -> datetime:
    """返回一个未来、且处于限制时段（每天 13:30-18:00，14:00）的时刻。

    用于持久化类测试：`_restore_active()` 内部会与 `datetime.now()` 比较，
    写死的过去日期会被误判为已过期，故用未来时刻保证恒为未过期。
    """
    d = (datetime.now() + timedelta(days=days_ahead)).date()
    return datetime.combine(d, time(14, 0))


class UnlockTestBase(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.history = HistoryStore(os.path.join(self.tmp.name, "history.json"))
        self.m = UnlockManager(history=self.history)

    def tearDown(self):
        self.tmp.cleanup()

    def seed_confirmed(self, count, when=MONDAY_1400):
        for _ in range(count):
            self.history.record_unlock("confirmed", when=when)


class TestRequest(UnlockTestBase):

    def test_normal_request(self):
        r = self.m.request("想试一个新英雄打法", MONDAY_1400)
        self.assertTrue(r["ok"])
        self.assertEqual(self.m.state, UnlockManager.COOLDOWN)
        self.assertEqual(self.m.cooldown_until, MONDAY_1400 + timedelta(minutes=10))

    def test_short_reason_rejected(self):
        r = self.m.request("玩", MONDAY_1400)
        self.assertFalse(r["ok"])
        self.assertEqual(self.m.state, UnlockManager.IDLE)

    def test_outside_restriction_rejected(self):
        r = self.m.request("想试一个新英雄打法", datetime(2026, 8, 24, 12, 0))
        self.assertFalse(r["ok"])

    def test_count_exhausted_rejected(self):
        self.seed_confirmed(config.UNLOCK_MAX_PER_WEEK)
        r = self.m.request("想试一个新英雄打法", MONDAY_1400)
        self.assertFalse(r["ok"])
        self.assertIn("次数", r["error"])

    def test_last_week_count_does_not_block(self):
        self.seed_confirmed(config.UNLOCK_MAX_PER_WEEK, when=NEXT_MONDAY - timedelta(days=1))
        r = self.m.request("想试一个新英雄打法", NEXT_MONDAY)
        self.assertTrue(r["ok"])

    def test_cross_week_reset(self):
        self.seed_confirmed(config.UNLOCK_MAX_PER_WEEK)
        r = self.m.request("想试一个新英雄打法", NEXT_MONDAY)
        self.assertTrue(r["ok"])


class TestCooldownAndCancel(UnlockTestBase):

    def test_cancel_during_wait(self):
        self.m.request("想试一个新英雄打法", MONDAY_1400)
        r = self.m.cancel(MONDAY_1405)
        self.assertTrue(r["ok"])
        self.assertEqual(self.m.state, UnlockManager.IDLE)
        r = self.m.confirm(MONDAY_1405)
        self.assertFalse(r["ok"])

    def test_confirm_too_early_rejected(self):
        self.m.request("想试一个新英雄打法", MONDAY_1400)
        r = self.m.confirm(MONDAY_1405)
        self.assertFalse(r["ok"])

    def test_wait_finish_then_confirm(self):
        self.m.request("想试一个新英雄打法", MONDAY_1400)
        self.m.update(MONDAY_1400 + timedelta(minutes=10))
        self.assertEqual(self.m.state, UnlockManager.CONFIRM_REQUIRED)
        r = self.m.confirm(MONDAY_1400 + timedelta(minutes=10))
        self.assertTrue(r["ok"])
        self.assertEqual(self.m.state, UnlockManager.ACTIVE)
        self.assertEqual(self.m.active_until, MONDAY_1400 + timedelta(minutes=70))


class TestActiveAndExpiry(UnlockTestBase):

    def test_active_rejects_new_request(self):
        self.m.request("想试一个新英雄打法", MONDAY_1400)
        self.m.update(MONDAY_1400 + timedelta(minutes=10))
        self.m.confirm(MONDAY_1400 + timedelta(minutes=10))
        r = self.m.request("再开一局", MONDAY_1400 + timedelta(minutes=20))
        self.assertFalse(r["ok"])

    def test_expire_after_60_minutes(self):
        self.m.request("想试一个新英雄打法", MONDAY_1400)
        self.m.update(MONDAY_1400 + timedelta(minutes=10))
        self.m.confirm(MONDAY_1400 + timedelta(minutes=10))
        self.assertEqual(self.m.state, UnlockManager.ACTIVE)
        self.m.update(MONDAY_1400 + timedelta(minutes=71))
        self.assertEqual(self.m.state, UnlockManager.EXPIRED)

    def test_end_at_1800_shorter_than_60min(self):
        self.m.request("想试一个新英雄打法", datetime(2026, 8, 24, 17, 0))
        self.m.update(datetime(2026, 8, 24, 17, 10))
        r = self.m.confirm(datetime(2026, 8, 24, 17, 10))
        self.assertTrue(r["ok"])
        self.assertEqual(self.m.active_until, datetime(2026, 8, 24, 18, 0))
        self.m.update(datetime(2026, 8, 24, 17, 59))
        self.assertEqual(self.m.state, UnlockManager.ACTIVE)
        self.m.update(datetime(2026, 8, 24, 18, 0))
        self.assertEqual(self.m.state, UnlockManager.EXPIRED)

    def test_confirm_after_1800_rejected(self):
        self.m.request("想试一个新英雄打法", MONDAY_1330)
        self.m.update(datetime(2026, 8, 24, 18, 0))
        self.assertEqual(self.m.state, UnlockManager.CONFIRM_REQUIRED)
        r = self.m.confirm(datetime(2026, 8, 24, 18, 0))
        self.assertFalse(r["ok"])


class TestIsActive(UnlockTestBase):

    def test_not_active_by_default(self):
        self.assertFalse(self.m.is_active(MONDAY_1400))

    def test_active_after_confirm(self):
        self.m.request("想试一个新英雄打法", MONDAY_1400)
        self.m.update(MONDAY_1400 + timedelta(minutes=10))
        self.m.confirm(MONDAY_1400 + timedelta(minutes=10))
        self.assertTrue(self.m.is_active(MONDAY_1400 + timedelta(minutes=20)))

    def test_false_after_expiry(self):
        self.m.request("想试一个新英雄打法", MONDAY_1400)
        self.m.update(MONDAY_1400 + timedelta(minutes=10))
        self.m.confirm(MONDAY_1400 + timedelta(minutes=10))
        self.assertFalse(self.m.is_active(MONDAY_1400 + timedelta(minutes=71)))

    def test_false_when_not_confirmed(self):
        self.m.request("想试一个新英雄打法", MONDAY_1400)
        self.assertFalse(self.m.is_active(MONDAY_1400 + timedelta(minutes=9)))


class TestPersistence(UnlockTestBase):
    """临时解锁持久化：快照必须早于 datetime.now() 才算未过期，故用未来时刻。"""

    def test_restart_restores_active_unlock(self):
        base = _future_restriction_time()
        self.m.request("想试一个新英雄打法", base)
        self.m.update(base + timedelta(minutes=10))
        self.m.confirm(base + timedelta(minutes=10))
        self.assertTrue(self.m.is_active(base + timedelta(minutes=11)))

        m2 = UnlockManager(history=self.history)
        self.assertEqual(m2.state, UnlockManager.ACTIVE)
        self.assertEqual(m2.active_until, base + timedelta(minutes=70))
        self.assertEqual(m2.reason, "想试一个新英雄打法")

    def test_restart_drops_expired(self):
        base = _future_restriction_time()
        self.m.request("想试一个新英雄打法", base)
        self.m.update(base + timedelta(minutes=10))
        self.m.confirm(base + timedelta(minutes=10))
        self.m.update(base + timedelta(minutes=71))
        m2 = UnlockManager(history=self.history)
        self.assertEqual(m2.state, UnlockManager.IDLE)

    def test_no_active_unlock_by_default(self):
        m2 = UnlockManager(history=self.history)
        self.assertEqual(m2.state, UnlockManager.IDLE)

    def test_clear_on_cancel_restores_idle(self):
        base = _future_restriction_time()
        self.m.request("想试一个新英雄打法", base)
        self.m.update(base + timedelta(minutes=10))
        self.m.confirm(base + timedelta(minutes=10))
        self.assertTrue(self.m.is_active(base + timedelta(minutes=11)))
        m3 = UnlockManager(history=self.history)
        self.assertEqual(m3.state, UnlockManager.ACTIVE)
        m3.update(base + timedelta(minutes=71))  # 过期并清除
        m4 = UnlockManager(history=self.history)
        self.assertEqual(m4.state, UnlockManager.IDLE)


class TestHistoryLink(UnlockTestBase):

    def test_confirm_records_history(self):
        self.m.request("想试一个新英雄打法", MONDAY_1400)
        self.m.update(MONDAY_1400 + timedelta(minutes=10))
        self.m.confirm(MONDAY_1400 + timedelta(minutes=10))
        data = self.history._load()
        self.assertEqual(len(data["unlocks"]), 1)
        e = data["unlocks"][0]
        self.assertEqual(e["result"], "confirmed")
        self.assertEqual(e["reason"], "想试一个新英雄打法")
        self.assertEqual(e["duration"], 60)
        self.assertEqual(self.history.get_weekly_unlock_count(MONDAY_1400), 1)

    def test_rejected_request_not_recorded(self):
        self.m.request("玩", MONDAY_1400)
        self.assertEqual(len(self.history._load()["unlocks"]), 0)


if __name__ == "__main__":
    unittest.main()
