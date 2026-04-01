from PyQt6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QMessageBox,
)
from PyQt6.QtCore import Qt

from gui.frameless import FramelessDialog
from gui.theme import (
    FONT_MONO, FONT_MD, FONT_SM, FONT_LG,
    TEXT_PRIMARY, TEXT_SECONDARY, ACCENT, ERROR, SUCCESS,
    SPACING_MD,
)
from utils.license import save_activation, get_license_error, get_licensed_username


class ActivationDialog(FramelessDialog):
    """License activation dialog shown on first launch."""

    def __init__(self, parent=None, reactivate: bool = False) -> None:
        super().__init__(parent, title="StreamBridge — Activation")
        self.setFixedSize(480, 380)
        self._activated = False

        layout = self.content_layout
        layout.setSpacing(SPACING_MD)

        # Title
        title = QLabel("License Activation")
        title.setStyleSheet(
            f"font-size: {FONT_LG + 2}px; font-weight: 700; color: {TEXT_PRIMARY};"
        )
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        # Show error if reactivating due to machine conflict
        if reactivate:
            error = get_license_error()
            if error:
                err_label = QLabel(error)
                err_label.setStyleSheet(
                    f"font-size: {FONT_SM}px; color: {ERROR}; padding: 6px;"
                )
                err_label.setWordWrap(True)
                err_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                layout.addWidget(err_label)

        # Username
        user_label = QLabel("Your Name:")
        user_label.setStyleSheet(f"font-size: {FONT_SM}px; color: {TEXT_SECONDARY};")
        layout.addWidget(user_label)

        self._username_input = QLineEdit()
        self._username_input.setPlaceholderText("Enter your name")
        self._username_input.setStyleSheet(f"font-size: {FONT_MD}px;")
        self._username_input.setMinimumHeight(36)
        # Pre-fill username if reactivating
        existing = get_licensed_username()
        if existing:
            self._username_input.setText(existing)
        layout.addWidget(self._username_input)

        # Activation code input
        code_label = QLabel("Activation Code:")
        code_label.setStyleSheet(f"font-size: {FONT_SM}px; color: {TEXT_SECONDARY};")
        layout.addWidget(code_label)

        self._code_input = QLineEdit()
        self._code_input.setPlaceholderText("XXXX-XXXX-XXXX")
        self._code_input.setStyleSheet(
            f"font-size: {FONT_LG}px; font-family: {FONT_MONO}; "
            f"letter-spacing: 2px; text-align: center;"
        )
        self._code_input.setMinimumHeight(36)
        layout.addWidget(self._code_input)

        # Status label
        self._status_label = QLabel("")
        self._status_label.setStyleSheet(f"font-size: {FONT_SM}px;")
        self._status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._status_label.setWordWrap(True)
        layout.addWidget(self._status_label)

        layout.addStretch()

        # Buttons
        btn_row = QHBoxLayout()
        quit_btn = QPushButton("Quit")
        quit_btn.clicked.connect(self.reject)
        btn_row.addWidget(quit_btn)
        activate_btn = QPushButton("Activate")
        activate_btn.setObjectName("saveBtn")
        activate_btn.clicked.connect(self._on_activate)
        btn_row.addWidget(activate_btn)
        layout.addLayout(btn_row)

    def _on_activate(self) -> None:
        username = self._username_input.text().strip()
        code = self._code_input.text().strip()

        if not username:
            self._status_label.setText("Enter your name")
            self._status_label.setStyleSheet(f"font-size: {FONT_SM}px; color: {ERROR};")
            return

        if not code:
            self._status_label.setText("Enter an activation code")
            self._status_label.setStyleSheet(f"font-size: {FONT_SM}px; color: {ERROR};")
            return

        self._status_label.setText("Connecting to license server...")
        self._status_label.setStyleSheet(f"font-size: {FONT_SM}px; color: {TEXT_SECONDARY};")
        self._status_label.repaint()

        success, error = save_activation(username, code)
        if success:
            self._activated = True
            self._status_label.setText("Activated!")
            self._status_label.setStyleSheet(f"font-size: {FONT_SM}px; color: {SUCCESS};")
            self.accept()
        else:
            self._status_label.setText(error)
            self._status_label.setStyleSheet(f"font-size: {FONT_SM}px; color: {ERROR};")

    @property
    def activated(self) -> bool:
        return self._activated
