from datetime import datetime, timedelta

import config
from core.scheduler import is_in_restriction
from storage import history as history_module


class UnlockManager:
    """临时解锁状态机。

    状态流：IDLE -> REQUESTED -> COOLDOWN -> CONFIRM_REQUIRED -> ACTIVE -> EXPIRED
    时间迁移采用惰性判断：调用 update()/status() 时依据截止时刻推进状态。
    """

    IDLE = "IDLE"
    REQUESTED = "REQUESTED"
    COOLDOWN = "COOLDOWN"
    CONFIRM_REQUIRED = "CONFIRM_REQUIRED"
    ACTIVE = "ACTIVE"
    EXPIRED = "EXPIRED"

    def __init__(self, history=None):
        self.history = history or history_module
        self.reset()
        self._restore_active()

    def reset(self):
        self.state = self.IDLE
        self.reason = ""
        self.requested_at = None
        self.cooldown_until = None
        self.active_until = None

    def _restore_active(self) -> None:
        """从持久化快照恢复未过期的临时解锁（程序重启后保留生效中的解锁）。"""
        snap = self.history.load_active_unlock()
        raw = snap.get("active_until") if isinstance(snap, dict) else None
        if not raw:
            return
        try:
            active_until = datetime.fromisoformat(raw)
        except ValueError:
            return
        if active_until > datetime.now():
            self.state = self.ACTIVE
            self.active_until = active_until
            self.reason = snap.get("reason", "")
        else:
            self.history.clear_active_unlock()

    def _ok(self, **kw):
        return {"ok": True, **kw}

    def _err(self, msg, **kw):
        return {"ok": False, "error": msg, **kw}

    def update(self, now: datetime = None) -> None:
        """按当前时间推进状态机（提交后进入等待 / 10分钟等待到期 / 解锁过期 / 18:00截止）"""
        now = now or datetime.now()
        if self.state == self.REQUESTED:
            self.state = self.COOLDOWN
        if self.state == self.COOLDOWN and now >= self.cooldown_until:
            self.state = self.CONFIRM_REQUIRED
        if self.state == self.ACTIVE and now >= self.active_until:
            self.state = self.EXPIRED
            self.active_until = None
            self.history.clear_active_unlock()

    def request(self, reason: str, now: datetime = None) -> dict:
        """提交解锁申请：校验时段、周次数、理由，进入等待"""
        now = now or datetime.now()
        self.update(now)
        if not is_in_restriction(now):
            return self._err("当前不在限制时段，无需解锁")
        if self.state in (self.COOLDOWN, self.CONFIRM_REQUIRED):
            return self._err("已有进行中的申请，请等待或取消")
        if self.state == self.ACTIVE:
            return self._err("已处于临时解锁中，无需重复申请")
        if len((reason or "").strip()) < config.UNLOCK_REASON_MIN_LEN:
            return self._err(f"解锁理由至少 {config.UNLOCK_REASON_MIN_LEN} 个字")
        if self.history.get_weekly_unlock_count(now) >= config.UNLOCK_MAX_PER_WEEK:
            return self._err("本周解锁次数已用完")

        self.state = self.REQUESTED
        self.reason = reason.strip()
        self.requested_at = now
        self.cooldown_until = now + timedelta(minutes=config.UNLOCK_WAIT_MINUTES)
        self.update(now)  # REQUESTED -> COOLDOWN 立即过渡
        return self._ok(state=self.state,
                        cooldown_until=self.cooldown_until,
                        message=f"申请已提交，等待 {config.UNLOCK_WAIT_MINUTES} 分钟后确认")

    def cancel(self, now: datetime = None) -> dict:
        """等待期间取消申请"""
        now = now or datetime.now()
        self.update(now)
        if self.state not in (self.REQUESTED, self.COOLDOWN, self.CONFIRM_REQUIRED):
            return self._err("当前没有可取消的申请")
        self.state = self.IDLE
        self.reason = ""
        self.cooldown_until = None
        return self._ok(message="申请已取消")

    def confirm(self, now: datetime = None) -> dict:
        """二次确认，获得 60 分钟临时解锁（最迟 18:00 失效）"""
        now = now or datetime.now()
        self.update(now)
        if self.state != self.CONFIRM_REQUIRED:
            return self._err("当前没有待确认的申请")
        if self.history.get_weekly_unlock_count(now) >= config.UNLOCK_MAX_PER_WEEK:
            return self._err("本周解锁次数已用完")
        end = datetime.combine(now.date(), config.RESTRICT_END)
        if now >= end:
            return self._err("已过限制结束时间，无需解锁")

        active_until = min(now + timedelta(minutes=config.UNLOCK_DURATION_MINUTES), end)
        self.state = self.ACTIVE
        self.active_until = active_until
        self.history.record_unlock(
            "confirmed",
            reason=self.reason,
            duration=config.UNLOCK_DURATION_MINUTES,
            when=now,
        )
        self.history.save_active_unlock(active_until, self.reason)
        return self._ok(state=self.state,
                        active_until=active_until,
                        message="解锁已生效")

    def is_active(self, now: datetime = None) -> bool:
        """是否处于生效的临时解锁（含惰性过期处理）。

        供监控线程判断：ACTIVE 且在截止时刻前返回 True，此时不阻断目标进程。
        """
        now = now or datetime.now()
        self.update(now)
        return self.state == self.ACTIVE

    def status(self, now: datetime = None) -> dict:
        """当前状态快照（供 UI 展示），顺带推进状态迁移"""
        now = now or datetime.now()
        self.update(now)
        return {
            "state": self.state,
            "reason": self.reason,
            "cooldown_until": self.cooldown_until,
            "active_until": self.active_until,
            "weekly_used": self.history.get_weekly_unlock_count(now),
            "weekly_max": config.UNLOCK_MAX_PER_WEEK,
        }
