import os
from datetime import time

APP_NAME = "LOL LOCK"

RESTRICT_DAYS = [0, 1, 2, 3, 4, 5, 6]  # 每天（周一=0 ... 周日=6）
RESTRICT_START = time(13, 30)
RESTRICT_END = time(18, 0)

POLL_INTERVAL_SECONDS = 30

TARGET_PROCESSES = [
    "LeagueClient.exe",
    "League of Legends.exe",
]

PROTECTED_PROCESS = "League of Legends.exe"

WARNING_POPUP_SECONDS = 5

TEST_MODE = False  # 警告：True 时只记录/提示，不会真的结束进程（调试用，正式使用必须为 False）

UNLOCK_DURATION_MINUTES = 60
UNLOCK_REASON_MIN_LEN = 4
UNLOCK_WAIT_MINUTES = 10
UNLOCK_MAX_PER_WEEK = 3

DATA_DIR = os.path.join(os.environ.get("LOCALAPPDATA", "."), "lol_lock")
HISTORY_FILE = os.path.join(DATA_DIR, "history.json")

AUTO_START = True
AUTO_START_REG_KEY = "LOL Lock"
