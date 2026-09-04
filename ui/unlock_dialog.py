from PyQt5.QtWidgets import (QDialog, QLabel, QPlainTextEdit, QPushButton,
                             QVBoxLayout)

import config


class ReasonDialog(QDialog):
    """第一步：输入解锁理由"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"{config.APP_NAME} - 申请临时解锁")
        self.setMinimumWidth(360)

        layout = QVBoxLayout(self)
        hint = QLabel(f"请输入解锁理由（至少 {config.UNLOCK_REASON_MIN_LEN} 个字），"
                      f"提交后需等待 {config.UNLOCK_WAIT_MINUTES} 分钟并二次确认。")
        hint.setWordWrap(True)
        self.edit = QPlainTextEdit()
        self.edit.setPlaceholderText("例如：需要向朋友演示游戏功能")
        self.edit.setMaximumHeight(80)
        self.error = QLabel("")
        self.error.setStyleSheet("color: red;")

        btn_row = QVBoxLayout()
        self.ok_btn = QPushButton("提交申请")
        self.cancel_btn = QPushButton("取消")
        self.ok_btn.clicked.connect(self._submit)
        self.cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(self.ok_btn)
        btn_row.addWidget(self.cancel_btn)

        layout.addWidget(hint)
        layout.addWidget(self.edit)
        layout.addWidget(self.error)
        layout.addLayout(btn_row)

    def _submit(self):
        reason = self.reason()
        if len(reason) < config.UNLOCK_REASON_MIN_LEN:
            self.error.setText(f"理由至少 {config.UNLOCK_REASON_MIN_LEN} 个字")
            return
        self.accept()

    def reason(self) -> str:
        return self.edit.toPlainText().strip()
