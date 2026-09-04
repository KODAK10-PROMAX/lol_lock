from datetime import datetime
from threading import Event, Thread

import psutil

import config
from core import enforcer
from core.scheduler import is_in_restriction


def find_target_processes():
    """遍历系统进程，产出名称在 config.TARGET_PROCESSES 中的进程（不硬编码）"""
    targets = set(config.TARGET_PROCESSES)
    for p in psutil.process_iter(["name"]):
        try:
            if p.info["name"] in targets:
                yield p
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue


class MonitorThread(Thread):
    """后台轮询线程：受限期间检测目标进程并交由 enforcer 处理。

    notifier: callable(proc_name)  -> UI 弹窗回调（第7步接入）
    recorder: callable(event_dict) -> 历史记录回调（第5步接入）
    unlock_manager: UnlockManager -> 判断临时解锁是否生效，生效期间不阻断
    """

    def __init__(self, notifier=None, recorder=None, unlock_manager=None):
        super().__init__(daemon=True, name="lol-lock-monitor")
        self._stop_event = Event()
        self.notifier = notifier
        self.recorder = recorder
        self.unlock_manager = unlock_manager

    def stop(self):
        self._stop_event.set()

    def run(self):
        while not self._stop_event.is_set():
            now = datetime.now()
            if is_in_restriction(now):
                unlocked = (self.unlock_manager.is_active(now)
                            if self.unlock_manager else False)
                in_match = enforcer.is_match_in_progress()
                for proc in find_target_processes():
                    if self._stop_event.is_set():
                        break
                    if enforcer.decide(proc, now, unlocked=unlocked,
                                       in_match=in_match) == enforcer.BLOCK:
                        enforcer.block(proc, now, self.notifier, self.recorder)
            self._stop_event.wait(config.POLL_INTERVAL_SECONDS)
