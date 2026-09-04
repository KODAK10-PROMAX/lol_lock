from datetime import datetime, date, time

import config


def is_restriction_day(day: date) -> bool:
    """周一至周五（Monday=0 ... Friday=4）"""
    return day.weekday() in config.RESTRICT_DAYS


def is_in_restriction(now: datetime) -> bool:
    """是否处于限制时段：周内 13:30 <= t < 18:00"""
    if not is_restriction_day(now.date()):
        return False
    return config.RESTRICT_START <= now.time() < config.RESTRICT_END


def restriction_window(d: date) -> tuple[time, time]:
    """指定日期对应的限制窗口"""
    return config.RESTRICT_START, config.RESTRICT_END
