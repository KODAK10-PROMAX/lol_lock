import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import psutil
from PyQt5.QtWidgets import QApplication

import config
from core import enforcer
from main import build_components
from storage.history import HistoryStore


class SmokeTest(unittest.TestCase):
    """整体冒烟：启动、UI 显示、monitor 线程、BLOCK 结束进程"""

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_app_starts_and_ui_shows(self):
        app, history, unlock, monitor, window = build_components(self.app)
        window.show()
        self.app.processEvents()
        self.assertFalse(window.isHidden())
        self.assertEqual(window.windowTitle(), config.APP_NAME)
        self.assertTrue(window.status.text())
        monitor.stop()
        window.close()

    def test_monitor_thread_runs_and_stops(self):
        _, _, _, monitor, window = build_components(self.app)
        monitor.start()
        self.assertTrue(monitor.is_alive())
        monitor.stop()
        monitor.join(timeout=5)
        self.assertFalse(monitor.is_alive())
        window.close()

    def test_block_kills_real_lol_process(self):
        tmp = tempfile.mkdtemp()
        dummy = os.path.join(tmp, "League of Legends.exe")
        shutil.copy2(sys.executable, dummy)
        proc = subprocess.Popen([dummy, "-c", "import time; time.sleep(30)"])
        try:
            p = psutil.Process(proc.pid)
            self.assertEqual(p.name(), "League of Legends.exe")

            events = []
            history = HistoryStore(os.path.join(tmp, "history.json"))
            enforcer.block(p, datetime.now(), recorder=events.append)

            self.assertFalse(p.is_running(), "非 TEST_MODE 应结束进程")
            self.assertEqual(len(events), 1)
            self.assertEqual(events[0]["type"], "blocked")
            self.assertEqual(events[0]["process"], "League of Legends.exe")
        finally:
            try:
                proc.kill()
            except Exception:
                pass


if __name__ == "__main__":
    unittest.main()
