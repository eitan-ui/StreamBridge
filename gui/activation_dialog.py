from PyQt6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QStackedWidget, QWidget,
)
from PyQt6.QtCore import Qt, QTimer

from gui.frameless import FramelessDialog
from gui.theme import (
    FONT_MONO, FONT_MD, FONT_SM, FONT_LG,
    TEXT_PRIMARY, TEXT_SECONDARY, ACCENT, ERROR, SUCCESS,
    SPACING_MD,
)
from utils.license import (
    request_activation_code, verify_activation_code,
    get_license_error, get_licensed_username,
)


class ActivationDialog(FramelessDialog):
    """License activation dialog — two-step email flow."""

    def __init__(self, parent=None, reactivate: bool = False) -> None:
        super().__init__(parent, title="StreamBridge — Activation")
        self.setFixedSize(480, 420)
        self._activated = False
        self._email = ""
        self._resend_cooldown = 0

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

        # Stacked widget for two pages
        self._stack = QStackedWidget()
        layout.addWidget(self._stack)

        self._build_email_page()
        self._build_code_page()

        layout.addStretch()

        # Bottom buttons
        btn_row = QHBoxLayout()
        self._quit_btn = QPushButton("Quit")
        self._quit_btn.clicked.connect(self.reject)
        btn_row.addWidget(self._quit_btn)

        self._action_btn = QPushButton("Send Code")
        self._action_btn.setObjectName("saveBtn")
        self._action_btn.clicked.connect(self._on_action)
        btn_row.addWidget(self._action_btn)
        layout.addLayout(btn_row)

        # Cooldown timer for resend
        self._cooldown_timer = QTimer(self)
        self._cooldown_timer.timeout.connect(self._tick_cooldown)

    def _build_email_page(self) -> None:
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(SPACING_MD)

        desc = QLabel("Enter your email to register and activate StreamBridge.")
        desc.setStyleSheet(f"font-size: {FONT_SM}px; color: {TEXT_SECONDARY};")
        desc.setWordWrap(True)
        desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(desc)

        email_label = QLabel("Email:")
        email_label.setStyleSheet(f"font-size: {FONT_SM}px; color: {TEXT_SECONDARY};")
        lay.addWidget(email_label)

        self._email_input = QLineEdit()
        self._email_input.setPlaceholderText("you@example.com")
        self._email_input.setStyleSheet(f"font-size: {FONT_MD}px;")
        self._email_input.setMinimumHeight(36)
        # Pre-fill email if reactivating
        existing = get_licensed_username()
        if existing:
            self._email_input.setText(existing)
        lay.addWidget(self._email_input)

        self._email_status = QLabel("")
        self._email_status.setStyleSheet(f"font-size: {FONT_SM}px;")
        self._email_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._email_status.setWordWrap(True)
        lay.addWidget(self._email_status)

        self._stack.addWidget(page)

    def _build_code_page(self) -> None:
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(SPACING_MD)

        self._sent_to_label = QLabel("")
        self._sent_to_label.setStyleSheet(
            f"font-size: {FONT_SM}px; color: {SUCCESS};"
        )
        self._sent_to_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._sent_to_label.setWordWrap(True)
        lay.addWidget(self._sent_to_label)

        code_label = QLabel("Activation Code:")
        code_label.setStyleSheet(f"font-size: {FONT_SM}px; color: {TEXT_SECONDARY};")
        lay.addWidget(code_label)

        self._code_input = QLineEdit()
        self._code_input.setPlaceholderText("XXXX-XXXX-XXXX")
        self._code_input.setStyleSheet(
            f"font-size: {FONT_LG}px; font-family: {FONT_MONO}; "
            f"letter-spacing: 2px; text-align: center;"
        )
        self._code_input.setMinimumHeight(36)
        lay.addWidget(self._code_input)

        self._code_status = QLabel("")
        self._code_status.setStyleSheet(f"font-size: {FONT_SM}px;")
        self._code_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._code_status.setWordWrap(True)
        lay.addWidget(self._code_status)

        # Resend / back row
        link_row = QHBoxLayout()
        self._back_btn = QPushButton("← Change email")
        self._back_btn.setFlat(True)
        self._back_btn.setStyleSheet(
            f"font-size: {FONT_SM}px; color: {ACCENT}; border: none; text-decoration: underline;"
        )
        self._back_btn.clicked.connect(self._go_to_email_page)
        link_row.addWidget(self._back_btn)

        link_row.addStretch()

        self._resend_btn = QPushButton("Resend code")
        self._resend_btn.setFlat(True)
        self._resend_btn.setStyleSheet(
            f"font-size: {FONT_SM}px; color: {ACCENT}; border: none; text-decoration: underline;"
        )
        self._resend_btn.clicked.connect(self._on_resend)
        link_row.addWidget(self._resend_btn)

        lay.addLayout(link_row)

        self._stack.addWidget(page)

    def _on_action(self) -> None:
        if self._stack.currentIndex() == 0:
            self._on_send_code()
        else:
            self._on_verify()

    def _on_send_code(self) -> None:
        email = self._email_input.text().strip()
        if not email or "@" not in email:
            self._email_status.setText("Enter a valid email address")
            self._email_status.setStyleSheet(f"font-size: {FONT_SM}px; color: {ERROR};")
            return

        self._email = email
        self._email_status.setText("Sending code...")
        self._email_status.setStyleSheet(f"font-size: {FONT_SM}px; color: {TEXT_SECONDARY};")
        self._email_status.repaint()
        self._action_btn.setEnabled(False)

        success, error, code = request_activation_code(email)
        self._action_btn.setEnabled(True)

        if success:
            self._go_to_code_page(code)
        else:
            self._email_status.setText(error)
            self._email_status.setStyleSheet(f"font-size: {FONT_SM}px; color: {ERROR};")

    def _on_verify(self) -> None:
        code = self._code_input.text().strip()
        if not code:
            self._code_status.setText("Enter the activation code from your email")
            self._code_status.setStyleSheet(f"font-size: {FONT_SM}px; color: {ERROR};")
            return

        self._code_status.setText("Verifying...")
        self._code_status.setStyleSheet(f"font-size: {FONT_SM}px; color: {TEXT_SECONDARY};")
        self._code_status.repaint()
        self._action_btn.setEnabled(False)

        success, error = verify_activation_code(self._email, code)
        self._action_btn.setEnabled(True)

        if success:
            self._activated = True
            self._code_status.setText("Activated!")
            self._code_status.setStyleSheet(f"font-size: {FONT_SM}px; color: {SUCCESS};")
            self.accept()
        else:
            self._code_status.setText(error)
            self._code_status.setStyleSheet(f"font-size: {FONT_SM}px; color: {ERROR};")

    def _on_resend(self) -> None:
        if self._resend_cooldown > 0:
            return
        self._code_status.setText("Generating new code...")
        self._code_status.setStyleSheet(f"font-size: {FONT_SM}px; color: {TEXT_SECONDARY};")
        self._code_status.repaint()

        success, error, code = request_activation_code(self._email)
        if success:
            if code:
                self._code_input.setText(code)
            self._code_status.setText("New code ready!")
            self._code_status.setStyleSheet(f"font-size: {FONT_SM}px; color: {SUCCESS};")
            self._start_resend_cooldown()
        else:
            self._code_status.setText(error)
            self._code_status.setStyleSheet(f"font-size: {FONT_SM}px; color: {ERROR};")

    def _go_to_code_page(self, code: str = "") -> None:
        self._sent_to_label.setText(f"Registered: {self._email}")
        self._code_input.clear()
        if code:
            self._code_input.setText(code)
            self._code_status.setText("Your activation code is ready. Click Activate!")
            self._code_status.setStyleSheet(f"font-size: {FONT_SM}px; color: {SUCCESS};")
        else:
            self._code_status.clear()
        self._stack.setCurrentIndex(1)
        self._action_btn.setText("Activate")
        self._code_input.setFocus()
        self._start_resend_cooldown()

    def _go_to_email_page(self) -> None:
        self._stack.setCurrentIndex(0)
        self._action_btn.setText("Send Code")
        self._email_status.clear()
        self._email_input.setFocus()

    def _start_resend_cooldown(self) -> None:
        self._resend_cooldown = 60
        self._resend_btn.setEnabled(False)
        self._resend_btn.setText(f"Resend ({self._resend_cooldown}s)")
        self._cooldown_timer.start(1000)

    def _tick_cooldown(self) -> None:
        self._resend_cooldown -= 1
        if self._resend_cooldown <= 0:
            self._cooldown_timer.stop()
            self._resend_btn.setEnabled(True)
            self._resend_btn.setText("Resend code")
        else:
            self._resend_btn.setText(f"Resend ({self._resend_cooldown}s)")

    @property
    def activated(self) -> bool:
        return self._activated
