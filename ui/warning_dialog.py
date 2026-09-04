from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtWidgets import QDialog, QLabel, QVBoxLayout

import config


class WarningDialog(QDialog):
    """阻断前的警告弹窗：倒计时 WARNING_POPUP_SECONDS 秒后自动关闭。

    TEST_MODE 下仅提示不结束进程，文案随之变化。
    """

    def __init__(self, process_name: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"{config.APP_NAME} - 限制中")
        self.setWindowFlag(Qt.WindowStaysOnTopHint)
        self.setModal(True)
        self.setMinimumWidth(320)

        if config.TEST_MODE:
            msg = f"检测到 {process_name}（TEST_MODE：仅记录，不结束进程）"
        else:
            msg = f"检测到 {process_name}，将在 {config.WARNING_POPUP_SECONDS} 秒后自动结束进程"

        layout = QVBoxLayout(self)
        self.msg = QLabel(msg)
        self.msg.setWordWrap(True)
        self.countdown = QLabel()
        layout.addWidget(self.msg)
        layout.addWidget(self.countdown)

        self.remaining = config.WARNING_POPUP_SECONDS
        self._update_countdown()
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)
        self.timer.start(1000)

    def _update_countdown(self):
        self.countdown.setText(f"{self.remaining} 秒后自动关闭")

    def _tick(self):
        self.remaining -= 1
        if self.remaining <= 0:
            self.accept()
        else:
            self._update_countdown()
