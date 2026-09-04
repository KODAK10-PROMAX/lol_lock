import json
import os
import threading
from datetime import datetime, time, timedelta

import config


def _default_data():
    return {"version": 1, "blocks": [], "unlocks": []}


def _week_start(when: datetime) -> datetime:
    """自然周起点：本周一 00:00"""
    monday = when.date() - timedelta(days=when.date().weekday())
    return datetime.combine(monday, time.min)


class HistoryStore:
    """本地历史记录：%LOCALAPPDATA%/lol_lock/history.json，线程安全。"""

    def __init__(self, path=None):
        self.path = path or config.HISTORY_FILE
        self._lock = threading.Lock()

    def _load(self) -> dict:
        if not os.path.exists(self.path):
            return _default_data()
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError):
            return _default_data()
        data.setdefault("version", 1)
        data.setdefault("blocks", [])
        data.setdefault("unlocks", [])
        return data

    def _save(self, data: dict) -> None:
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def record_block(self, process: str, result: str, detail: str = "",
                     when: datetime = None) -> dict:
        entry = {
            "time": (when or datetime.now()).isoformat(timespec="seconds"),
            "type": "block",
            "process": process,
            "result": result,  # blocked | test_mode
            "detail": detail,
        }
        with self._lock:
            data = self._load()
            data["blocks"].append(entry)
            self._save(data)
        return entry

    def record_unlock(self, result: str, reason: str = "", detail: str = "",
                      duration: int = None, when: datetime = None) -> dict:
        entry = {
            "time": (when or datetime.now()).isoformat(timespec="seconds"),
            "type": "unlock",
            "process": "",
            "result": result,  # submitted | confirmed | cancelled | denied
            "detail": detail,
            "reason": reason,
            "duration": duration,
        }
        with self._lock:
            data = self._load()
            data["unlocks"].append(entry)
            self._save(data)
        return entry

    # ---------- 当前生效的临时解锁持久化（供重启恢复） ----------

    def save_active_unlock(self, active_until: datetime, reason: str) -> None:
        """记录当前生效的临时解锁截止时刻与理由，供程序重启后恢复。"""
        with self._lock:
            data = self._load()
            data["active_unlock"] = {
                "active_until": active_until.isoformat(timespec="seconds"),
                "reason": reason,
            }
            self._save(data)

    def load_active_unlock(self) -> dict:
        """读取持久化的临时解锁快照；不存在返回空 dict。"""
        with self._lock:
            data = self._load()
        return data.get("active_unlock") or {}

    def clear_active_unlock(self) -> None:
        """清除持久化的临时解锁快照（过期/取消时调用）。"""
        with self._lock:
            data = self._load()
            if "active_unlock" in data:
                del data["active_unlock"]
                self._save(data)

    def get_weekly_unlock_count(self, when: datetime = None) -> int:
        """本周（周一00:00起）已确认的解锁次数"""
        when = when or datetime.now()
        start = _week_start(when)
        with self._lock:
            data = self._load()
        count = 0
        for e in data.get("unlocks", []):
            if e.get("result") != "confirmed":
                continue
            try:
                t = datetime.fromisoformat(e["time"])
            except (ValueError, KeyError):
                continue
            if t >= start:
                count += 1
        return count

    def get_today_block_count(self, when: datetime = None) -> int:
        """当日阻断记录条数（含 TEST_MODE 记录）"""
        when = when or datetime.now()
        prefix = when.strftime("%Y-%m-%d")
        with self._lock:
            data = self._load()
        return sum(1 for e in data.get("blocks", [])
                   if e.get("time", "").startswith(prefix))


store = HistoryStore()


def record_block(process, result, detail="", when=None):
    return store.record_block(process, result, detail, when)


def record_unlock(result, reason="", detail="", duration=None, when=None):
    return store.record_unlock(result, reason, detail, duration, when)


def get_weekly_unlock_count(when=None):
    return store.get_weekly_unlock_count(when)


def get_today_block_count(when=None):
    return store.get_today_block_count(when)


def save_active_unlock(active_until, reason=""):
    return store.save_active_unlock(active_until, reason)


def load_active_unlock():
    return store.load_active_unlock()


def clear_active_unlock():
    return store.clear_active_unlock()
