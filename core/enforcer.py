from datetime import datetime

import psutil

import config
from core.scheduler import is_in_restriction

ALLOW = "allow"
BLOCK = "block"


def _started_before_window(proc: psutil.Process, now: datetime) -> bool:
    """进程创建时间是否早于今天的限制起始时刻（13:30）"""
    start = datetime.combine(now.date(), config.RESTRICT_START)
    try:
        return datetime.fromtimestamp(proc.create_time()) < start
    except (psutil.Error, OSError, ValueError):
        return False


def is_match_in_progress() -> bool:
    """当前是否有一局正在进行的游戏（League of Legends.exe 进程存在）。

    对局保护依据：只要对局进行中，就不强制结束（包括客户端 LeagueClient.exe），
    避免打到一半被强关。对局结束、游戏进程退出后恢复拦截。
    """
    for p in psutil.process_iter(["name"]):
        try:
            if p.info["name"] == config.PROTECTED_PROCESS:
                return True
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return False


def decide(proc: psutil.Process, now: datetime, unlocked: bool = False,
           in_match: bool = False) -> str:
    """判定单个进程：ALLOW 或 BLOCK

    - 非限制时段：一律放行
    - unlocked=True（临时解锁生效中）：放行，不阻断
    - in_match=True（对局进行中）：放行，让当前对局打完（含客户端）
    - 非目标进程：放行
    - League of Legends.exe 且创建于 13:30 前：放行（对局保护）
    - 其余目标进程（13:30 后启动的 League of Legends.exe、任何 LeagueClient.exe）：阻断
    """
    if not is_in_restriction(now):
        return ALLOW
    if unlocked:
        return ALLOW
    if in_match:
        return ALLOW
    name = proc.name()
    if name not in config.TARGET_PROCESSES:
        return ALLOW
    if name == config.PROTECTED_PROCESS and _started_before_window(proc, now):
        return ALLOW
    return BLOCK


def block(proc: psutil.Process, now: datetime, notifier=None, recorder=None) -> None:
    """执行阻断：弹窗警告 WARNING_POPUP_SECONDS 秒后结束进程。

    TEST_MODE=True 时只记录与提示，不真正结束进程。
    notifier: callable(name) 用于 UI 弹窗
    recorder: callable(event_dict) 用于写历史记录
    """
    name = proc.name()
    pid = proc.pid
    event = {
        "time": now.isoformat(timespec="seconds"),
        "type": "test_mode" if config.TEST_MODE else "blocked",
        "process": name,
        "pid": pid,
        "detail": "TEST_MODE：仅记录，未结束进程" if config.TEST_MODE else "警告5秒后已结束进程",
    }
    if recorder:
        recorder(event)
    if notifier:
        notifier(name)
    if not config.TEST_MODE:
        import time as _time

        _time.sleep(config.WARNING_POPUP_SECONDS)
        try:
            proc.terminate()
            try:
                proc.wait(timeout=3)
            except psutil.TimeoutExpired:
                proc.kill()
        except psutil.Error:
            pass
