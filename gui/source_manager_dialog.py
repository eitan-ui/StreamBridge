from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QListWidget, QListWidgetItem, QDialogButtonBox,
    QMessageBox,
)
from PyQt6.QtCore import Qt

from models.source import SourceManager, Source


DIALOG_STYLE = """
QDialog {
    background-color: #1a1a2e;
    color: #e0e0e0;
}
QLabel {
    color: #e0e0e0;
    background: transparent;
}
QLineEdit {
    background-color: #16213e;
    border: 1px solid #0f3460;
    border-radius: 4px;
    padding: 7px 10px;
    color: #e0e0e0;
    font-size: 12px;
}
QListWidget {
    background-color: #16213e;
    border: 1px solid #0f3460;
    border-radius: 4px;
    color: #e0e0e0;
    font-size: 12px;
    padding: 4px;
}
QListWidget::item {
    padding: 6px;
    border-radius: 3px;
}
QListWidget::item:selected {
    background-color: #0f3460;
}
QPushButton {
    background-color: #0f3460;
    color: #e0e0e0;
    border: none;
    border-radius: 4px;
    padding: 8px 16px;
    font-size: 12px;
}
QPushButton:hover {
    background-color: #1a5276;
}
QPushButton#dangerBtn {
    background-color: #7b241c;
}
QPushButton#dangerBtn:hover {
    background-color: #c0392b;
}
"""


class SaveSourceDialog(QDialog):
    """Simple dialog to save a new source with a name."""

    def __init__(self, url: str, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Save Source")
        self.setFixedWidth(350)
        self.setStyleSheet(DIALOG_STYLE)

        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        layout.addWidget(QLabel("URL:"))
        url_label = QLabel(url)
        url_label.setStyleSheet("color: #3498db; font-size: 11px;")
        url_label.setWordWrap(True)
        layout.addWidget(url_label)

        layout.addWidget(QLabel("Name:"))
        self._name_input = QLineEdit()
        self._name_input.setPlaceholderText("e.g. Radio Station 1")
        layout.addWidget(self._name_input)

        btn_row = QHBoxLayout()
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)
        save_btn = QPushButton("Save")
        save_btn.setStyleSheet("background-color: #27ae60; color: white;")
        save_btn.clicked.connect(self._on_save)
        btn_row.addWidget(save_btn)
        layout.addLayout(btn_row)

    def _on_save(self) -> None:
        if self._name_input.text().strip():
            self.accept()

    def get_name(self) -> str:
        return self._name_input.text().strip()


class SourceManagerDialog(QDialog):
    """Dialog to manage saved sources: add, edit, delete, reorder."""

    def __init__(self, source_manager: SourceManager, parent=None) -> None:
        super().__init__(parent)
        self._source_manager = source_manager
        self.setWindowTitle("Manage Sources")
        self.setFixedSize(450, 400)
        self.setStyleSheet(DIALOG_STYLE)

        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        # Source list
        self._list = QListWidget()
        self._refresh_list()
        layout.addWidget(self._list, 1)

        # Edit fields
        form_layout = QVBoxLayout()
        name_row = QHBoxLayout()
        name_row.addWidget(QLabel("Name:"))
        self._name_input = QLineEdit()
        name_row.addWidget(self._name_input, 1)
        form_layout.addLayout(name_row)

        url_row = QHBoxLayout()
        url_row.addWidget(QLabel("URL:"))
        self._url_input = QLineEdit()
        url_row.addWidget(self._url_input, 1)
        form_layout.addLayout(url_row)
        layout.addLayout(form_layout)

        # Action buttons
        action_row = QHBoxLayout()
        self._add_btn = QPushButton("Add New")
        self._add_btn.clicked.connect(self._on_add)
        action_row.addWidget(self._add_btn)

        self._update_btn = QPushButton("Update")
        self._update_btn.clicked.connect(self._on_update)
        action_row.addWidget(self._update_btn)

        self._delete_btn = QPushButton("Delete")
        self._delete_btn.setObjectName("dangerBtn")
        self._delete_btn.clicked.connect(self._on_delete)
        action_row.addWidget(self._delete_btn)
        layout.addLayout(action_row)

        # Move buttons
        move_row = QHBoxLayout()
        self._up_btn = QPushButton("▲ Move Up")
        self._up_btn.clicked.connect(self._on_move_up)
        move_row.addWidget(self._up_btn)
        self._down_btn = QPushButton("▼ Move Down")
        self._down_btn.clicked.connect(self._on_move_down)
        move_row.addWidget(self._down_btn)
        layout.addLayout(move_row)

        # Close button
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn)

        # Connect selection change
        self._list.currentRowChanged.connect(self._on_selection_changed)

    def _refresh_list(self) -> None:
        self._list.clear()
        for source in self._source_manager.sources:
            item = QListWidgetItem(f"{source.name}  —  {source.url}")
            self._list.addItem(item)

    def _on_selection_changed(self, row: int) -> None:
        source = self._source_manager.get(row)
        if source:
            self._name_input.setText(source.name)
            self._url_input.setText(source.url)

    def _on_add(self) -> None:
        name = self._name_input.text().strip()
        url = self._url_input.text().strip()
        if not name or not url:
            return
        self._source_manager.add(Source(name=name, url=url))
        self._refresh_list()
        self._list.setCurrentRow(self._list.count() - 1)

    def _on_update(self) -> None:
        row = self._list.currentRow()
        if row < 0:
            return
        name = self._name_input.text().strip()
        url = self._url_input.text().strip()
        if not name or not url:
            return
        self._source_manager.update(row, Source(name=name, url=url))
        self._refresh_list()
        self._list.setCurrentRow(row)

    def _on_delete(self) -> None:
        row = self._list.currentRow()
        if row < 0:
            return
        source = self._source_manager.get(row)
        if source:
            reply = QMessageBox.question(
                self, "Delete Source",
                f"Delete '{source.name}'?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if reply == QMessageBox.StandardButton.Yes:
                self._source_manager.remove(row)
                self._refresh_list()
                self._name_input.clear()
                self._url_input.clear()

    def _on_move_up(self) -> None:
        row = self._list.currentRow()
        if row > 0:
            self._source_manager.move(row, row - 1)
            self._refresh_list()
            self._list.setCurrentRow(row - 1)

    def _on_move_down(self) -> None:
        row = self._list.currentRow()
        if 0 <= row < self._list.count() - 1:
            self._source_manager.move(row, row + 1)
            self._refresh_list()
            self._list.setCurrentRow(row + 1)
