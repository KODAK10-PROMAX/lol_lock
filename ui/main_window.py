from datetime import datetime

from PyQt5.QtCore import QObject, Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QColor, QIcon, QPainter, QPixmap
from PyQt5.QtWidgets import (QAction, QHBoxLayout, QLabel, QMenu,
                             QMessageBox, QPushButton, QSystemTrayIcon,
                             QVBoxLayout, QWidget)

import config
from core.scheduler import is_in_restriction
from ui.unlock_dialog import ReasonDialog
from ui.warning_dialog import WarningDialog


def _make_icon() -> QIcon:
    """程序化生成简单托盘图标，避免依赖外部图片文件"""
    pixmap = QPixmap(64, 64)
    pixmap.fill(QColor("#1a6fb5"))
    painter = QPainter(pixmap)
    painter.setPen(QColor("white"))
    from PyQt5.QtGui import QFont
    painter.setFont(QFont("Arial", 30, QFont.Bold))
    painter.drawText(pixmap.rect(), Qt.AlignCenter, "L")
    painter.end()
    return QIcon(pixmap)


class Notifier(QObject):
    """monitor 后台线程 -> 主线程信号桥（弹窗必须在主线程）"""
    violation = pyqtSignal(str)


def _fmt_remaining(seconds: float) -> str:
    seconds = max(0, int(seconds))
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"


class MainWindow(QWidget):
    """主窗口：仅负责展示与调用 core，不含业务判断。"""

    STATE_TEXT = {
        "IDLE": "锁定中",
        "COOLDOWN": "解锁等待中",
        "CONFIRM_REQUIRED": "解锁等待中",
        "ACTIVE": "临时解锁",
        "EXPIRED": "锁定中",
    }

    def __init__(self, monitor, unlock_manager, history, parent=None):
        super().__init__(parent)
        self.monitor = monitor
        self.unlock = unlock_manager
        self.history = history
        self.notifier = Notifier(self)
        self.notifier.violation.connect(self._on_violation)
        monitor.notifier = self.notifier.violation.emit

        self.setWindowTitle(config.APP_NAME)
        self.setFixedSize(380, 300)

        layout = QVBoxLayout(self)

        self.title = QLabel(config.APP_NAME)
        self.title.setStyleSheet("font-size: 22px; font-weight: bold;")
        self.status = QLabel()
        self.status.setStyleSheet("font-size: 16px; font-weight: bold; color: #1a6fb5;")

        self.countdown_label = QLabel()
        self.blocks_label = QLabel()
        self.weekly_label = QLabel()
        self.reason_label = QLabel()
        self.reason_label.setWordWrap(True)

        self.unlock_btn = QPushButton("申请60分钟解锁")
        self.unlock_btn.clicked.connect(self._on_request)
        self.confirm_btn = QPushButton("确认解锁")
        self.confirm_btn.clicked.connect(self._on_confirm)
        self.cancel_btn = QPushButton("取消申请")
        self.cancel_btn.clicked.connect(self._on_cancel)

        btn_row = QHBoxLayout()
        btn_row.addWidget(self.unlock_btn)
        btn_row.addWidget(self.confirm_btn)
        btn_row.addWidget(self.cancel_btn)

        layout.addWidget(self.title)
        layout.addWidget(self.status)
        layout.addWidget(self.countdown_label)
        layout.addWidget(self.blocks_label)
        layout.addWidget(self.weekly_label)
        layout.addWidget(self.reason_label)
        layout.addWidget(QLabel(""))
        layout.addLayout(btn_row)

        self._tray_notified = False
        self._setup_tray()

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh)
        self.timer.start(1000)

        self.refresh()

    def _on_violation(self, process_name: str):
        WarningDialog(process_name, self).exec_()

    def _on_request(self):
        dlg = ReasonDialog(self)
        if dlg.exec_():
            result = self.unlock.request(dlg.reason())
            if not result["ok"]:
                QMessageBox.warning(self, config.APP_NAME, result["error"])
            self.refresh()

    def _on_confirm(self):
        result = self.unlock.confirm()
        if not result["ok"]:
            QMessageBox.warning(self, config.APP_NAME, result["error"])
        self.refresh()

    def _on_cancel(self):
        self.unlock.cancel()
        self.refresh()

    def refresh(self):
        now = datetime.now()
        restricted = is_in_restriction(now)
        st = self.unlock.status(now)
        state = st["state"]

        if not restricted:
            self.status.setText("当前状态：正常")
            self.countdown_label.setText("当前无需限制")
        else:
            self.status.setText(f"当前状态：{self.STATE_TEXT.get(state, '锁定中')}")
            if state in ("COOLDOWN", "CONFIRM_REQUIRED"):
                target = st["cooldown_until"]
                self.countdown_label.setText(
                    f"距离可确认：{_fmt_remaining((target - now).total_seconds())}")
            elif state == "ACTIVE":
                target = st["active_until"]
                self.countdown_label.setText(
                    f"距离解锁结束：{_fmt_remaining((target - now).total_seconds())}")
            else:
                target = datetime.combine(now.date(), config.RESTRICT_END)
                self.countdown_label.setText(
                    f"距离解除限制：{_fmt_remaining((target - now).total_seconds())}")

        self.blocks_label.setText(f"今日阻断次数：{self.history.get_today_block_count(now)}")
        self.weekly_label.setText(
            f"本周解锁额度：{st['weekly_used']} / {st['weekly_max']}")

        if st["reason"]:
            self.reason_label.setText(f"解锁理由：{st['reason']}")
        else:
            self.reason_label.setText("")

        self.unlock_btn.setVisible(restricted and state in ("IDLE", "EXPIRED"))
        self.confirm_btn.setVisible(restricted and state == "CONFIRM_REQUIRED")
        self.cancel_btn.setVisible(restricted and state in ("COOLDOWN", "CONFIRM_REQUIRED"))

    # ---------- 托盘 ----------

    def _setup_tray(self):
        self.tray = QSystemTrayIcon(_make_icon(), self)
        self.tray.setToolTip(config.APP_NAME)
        menu = QMenu()
        show_action = QAction("显示主窗口", menu)
        show_action.triggered.connect(self._show_from_tray)
        quit_action = QAction("退出", menu)
        quit_action.triggered.connect(self._quit_from_tray)
        menu.addAction(show_action)
        menu.addAction(quit_action)
        self.tray.setContextMenu(menu)
        self.tray.activated.connect(self._on_tray_activated)
        self.tray.show()

    def _on_tray_activated(self, reason):
        if reason == QSystemTrayIcon.Trigger:
            self._show_from_tray()

    def _show_from_tray(self):
        self.show()
        self.raise_()
        self.activateWindow()

    def _quit_from_tray(self):
        if QMessageBox.question(
                self, config.APP_NAME,
                "确定要退出吗？退出后后台监督将停止。",
        ) == QMessageBox.Yes:
            self.tray.hide()
            from PyQt5.QtWidgets import QApplication
            QApplication.instance().quit()

    def closeEvent(self, event):
        """点 × 仅隐藏到托盘，监督不中断"""
        if QSystemTrayIcon.isSystemTrayAvailable():
            event.ignore()
            self.hide()
            if not self._tray_notified:
                self._tray_notified = True
                self.tray.showMessage(
                    config.APP_NAME,
                    "已最小化到托盘，后台监督持续运行中",
                )
        else:
            event.accept()
