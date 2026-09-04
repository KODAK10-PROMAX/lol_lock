import sys
from datetime import datetime

from PyQt5.QtWidgets import QApplication

import config
from core import autostart
from core.monitor import MonitorThread
from core.unlock import UnlockManager
from storage.history import HistoryStore
from ui.main_window import MainWindow


def _make_recorder(history):
    """enforcer 事件字典 -> history.record_block 的适配器"""
    def record(event):
        detail = event.get("detail", "")
        if event.get("pid"):
            detail = f"{detail} (pid={event['pid']})"
        try:
            when = datetime.fromisoformat(event["time"])
        except (KeyError, ValueError):
            when = None
        history.record_block(
            event.get("process", ""),
            event.get("result") or event.get("type", ""),
            detail=detail,
            when=when,
        )
    return record


def build_components(app=None):
    """依赖组装：QApplication / HistoryStore / UnlockManager / MonitorThread / MainWindow"""
    app = app or QApplication.instance() or QApplication(sys.argv)
    history = HistoryStore(config.HISTORY_FILE)
    unlock_manager = UnlockManager(history=history)
    monitor = MonitorThread(recorder=_make_recorder(history),
                            unlock_manager=unlock_manager)
    window = MainWindow(monitor, unlock_manager, history)
    return app, history, unlock_manager, monitor, window


def main():
    app, _, _, monitor, window = build_components()
    app.setQuitOnLastWindowClosed(False)
    if config.AUTO_START:
        autostart.enable()
    app.aboutToQuit.connect(monitor.stop)
    window.show()
    monitor.start()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
