import os
import sys
import winreg

import config

_RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"


def _command() -> str:
    """注册表值：pythonw.exe 静默运行本程序"""
    script = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "main.py"))
    python = sys.executable
    pythonw = python.replace("python.exe", "pythonw.exe")
    if os.path.exists(pythonw):
        python = pythonw
    return f'"{python}" "{script}"'


def enable() -> bool:
    """写入开机自启注册表项（当前用户，无需管理员）。

    失败（如权限/被安全软件拦截）返回 False，不影响主程序运行。
    """
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _RUN_KEY, 0,
                            winreg.KEY_SET_VALUE) as key:
            winreg.SetValueEx(key, config.AUTO_START_REG_KEY, 0,
                              winreg.REG_SZ, _command())
        return True
    except OSError:
        return False


def disable() -> None:
    """移除开机自启注册表项"""
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _RUN_KEY, 0,
                            winreg.KEY_SET_VALUE) as key:
            winreg.DeleteValue(key, config.AUTO_START_REG_KEY)
    except FileNotFoundError:
        pass


def is_enabled() -> bool:
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _RUN_KEY, 0,
                            winreg.KEY_QUERY_VALUE) as key:
            winreg.QueryValueEx(key, config.AUTO_START_REG_KEY)
        return True
    except FileNotFoundError:
        return False
