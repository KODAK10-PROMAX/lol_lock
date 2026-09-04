import unittest
from datetime import datetime

import psutil

import config
from core import enforcer


class FakeProc:
    def __init__(self, name, create_time, pid=1000):
        self._name = name
        self._create_time = create_time.timestamp()
        self.pid = pid

    def name(self):
        return self._name

    def create_time(self):
        return self._create_time


MONDAY_14_00 = datetime(2026, 8, 24, 14, 0)
MONDAY_13_00 = datetime(2026, 8, 24, 13, 0)
SATURDAY_14_00 = datetime(2026, 8, 29, 14, 0)


class TestDecide(unittest.TestCase):

    def test_league_client_after_1330_blocks(self):
        p = FakeProc("LeagueClient.exe", MONDAY_14_00)
        self.assertEqual(enforcer.decide(p, MONDAY_14_00), enforcer.BLOCK)

    def test_league_client_before_1330_still_blocks(self):
        p = FakeProc("LeagueClient.exe", MONDAY_13_00)
        self.assertEqual(enforcer.decide(p, MONDAY_14_00), enforcer.BLOCK)

    def test_lol_before_1330_allowed(self):
        p = FakeProc("League of Legends.exe", MONDAY_13_00)
        self.assertEqual(enforcer.decide(p, MONDAY_14_00), enforcer.ALLOW)

    def test_lol_after_1330_blocks(self):
        p = FakeProc("League of Legends.exe", MONDAY_14_00)
        self.assertEqual(enforcer.decide(p, MONDAY_14_00), enforcer.BLOCK)

    def test_unknown_process_allowed(self):
        p = FakeProc("notepad.exe", MONDAY_14_00)
        self.assertEqual(enforcer.decide(p, MONDAY_14_00), enforcer.ALLOW)

    def test_weekend_client_blocks(self):
        p = FakeProc("LeagueClient.exe", SATURDAY_14_00)
        self.assertEqual(enforcer.decide(p, SATURDAY_14_00), enforcer.BLOCK)

    def test_outside_window_allowed(self):
        p = FakeProc("League of Legends.exe", MONDAY_14_00)
        outside = datetime(2026, 8, 24, 10, 0)
        self.assertEqual(enforcer.decide(p, outside), enforcer.ALLOW)

    def test_unlocked_allows_target_during_restriction(self):
        p = FakeProc("LeagueClient.exe", MONDAY_14_00)
        self.assertEqual(enforcer.decide(p, MONDAY_14_00, unlocked=True), enforcer.ALLOW)

    def test_unlocked_allows_lol_after_start(self):
        p = FakeProc("League of Legends.exe", MONDAY_14_00)
        self.assertEqual(enforcer.decide(p, MONDAY_14_00, unlocked=True), enforcer.ALLOW)

    def test_in_match_allows_client(self):
        p = FakeProc("LeagueClient.exe", MONDAY_14_00)
        self.assertEqual(enforcer.decide(p, MONDAY_14_00, in_match=True), enforcer.ALLOW)

    def test_in_match_allows_game(self):
        p = FakeProc("League of Legends.exe", MONDAY_14_00)
        self.assertEqual(enforcer.decide(p, MONDAY_14_00, in_match=True), enforcer.ALLOW)

    def test_not_in_match_still_blocks(self):
        p = FakeProc("LeagueClient.exe", MONDAY_14_00)
        self.assertEqual(enforcer.decide(p, MONDAY_14_00, in_match=False), enforcer.BLOCK)


class TestBlock(unittest.TestCase):

    def test_block_terminates_process(self):
        class TerminatingProc(FakeProc):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                self.terminated = False

            def terminate(self):
                self.terminated = True

            def wait(self, timeout=3):
                return None

        p = TerminatingProc("LeagueClient.exe", MONDAY_14_00)
        events = []
        old_wait = config.WARNING_POPUP_SECONDS
        config.WARNING_POPUP_SECONDS = 0
        try:
            enforcer.block(p, MONDAY_14_00, recorder=events.append)
        finally:
            config.WARNING_POPUP_SECONDS = old_wait
        self.assertTrue(p.terminated, "非 TEST_MODE 应结束进程")
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["type"], "blocked")

    def test_terminate_failure_is_swallowed(self):
        if __import__("config").TEST_MODE:
            self.skipTest("当前为 TEST_MODE")
        p = FakeProc("LeagueClient.exe", MONDAY_14_00)

        def boom():
            raise psutil.NoSuchProcess(9999)

        p.terminate = boom
        enforcer.block(p, MONDAY_14_00)  # 不应抛出


if __name__ == "__main__":
    unittest.main()
