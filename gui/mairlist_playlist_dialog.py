from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QSpinBox,
    QFrame, QAbstractItemView, QComboBox, QWidget,
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QColor, QFont

from core.mairlist_api import MairListAPI, PlaylistItem
from models.config import MairListConfig


PLAYLIST_STYLE = """
QDialog {
    background-color: #1a1a2e;
    color: #e0e0e0;
}
QLabel {
    background: transparent;
    color: #e0e0e0;
}
QTableWidget {
    background-color: #0d1b2a;
    gridline-color: #1b2838;
    border: 1px solid #252545;
    border-radius: 4px;
    color: #e0e0e0;
    font-family: 'Consolas', 'SF Mono', monospace;
    font-size: 11px;
    selection-background-color: #0f3460;
    selection-color: #ffffff;
}
QTableWidget::item {
    padding: 4px 6px;
    border-bottom: 1px solid #1b2838;
}
QTableWidget::item:selected {
    background-color: #0f3460;
}
QHeaderView::section {
    background-color: #16213e;
    color: #7f8fa6;
    border: none;
    border-right: 1px solid #1b2838;
    border-bottom: 2px solid #252545;
    padding: 6px 4px;
    font-size: 10px;
    font-weight: bold;
    text-transform: uppercase;
}
QPushButton {
    background-color: #0f3460;
    color: #e0e0e0;
    border: none;
    border-radius: 4px;
    padding: 8px 14px;
    font-size: 12px;
    font-weight: bold;
}
QPushButton:hover {
    background-color: #1a5276;
}
QPushButton:disabled {
    background-color: #1a1a2e;
    color: #444;
}
QPushButton#playBtn {
    background-color: #27ae60;
    color: white;
    font-size: 14px;
    padding: 8px 16px;
}
QPushButton#playBtn:hover {
    background-color: #2ecc71;
}
QPushButton#stopBtn {
    background-color: #c0392b;
    color: white;
    font-size: 14px;
    padding: 8px 16px;
}
QPushButton#stopBtn:hover {
    background-color: #e74c3c;
}
QPushButton#applyBtn {
    background-color: #27ae60;
    color: white;
}
QPushButton#applyBtn:hover {
    background-color: #2ecc71;
}
QSpinBox, QComboBox {
    background-color: #16213e;
    border: 1px solid #252545;
    border-radius: 4px;
    padding: 4px 8px;
    color: #e0e0e0;
    font-size: 12px;
}
QFrame#transportPanel {
    background-color: #16213e;
    border-radius: 6px;
}
QFrame#statusBar {
    background-color: #0d1b2a;
    border-radius: 4px;
}
"""

# Column definitions: (header, width, editable, tooltip)
COLUMNS = [
    ("#", 30, False, "Track number"),
    ("Title", 160, False, "Track title"),
    ("Artist", 100, False, "Artist name"),
    ("Duration", 90, False, "Total duration"),
    ("Cue In", 90, True, "Audio start point (skip silence at beginning)"),
    ("Cue Out", 90, True, "Audio end point (skip silence/tail at end)"),
    ("Fade In", 80, True, "Fade in duration"),
    ("Fade Out", 80, True, "Fade out duration"),
    ("Start Next", 90, True, "When to start the next item (crossfade point)"),
    ("Hard Fix", 90, True, "Fixed start time — item MUST start at this time"),
    ("Soft Fix", 90, True, "Preferred start time — can be adjusted"),
    ("Type", 60, False, "Item type"),
]

# Map column index to PlaylistItem property and mAirList command keyword
COL_PROP_MAP = {
    4: ("cue_in", "CUEIN"),
    5: ("cue_out", "CUEOUT"),
    6: ("fade_in", "FADEIN"),
    7: ("fade_out", "FADEOUT"),
    8: ("start_next", "STARTNEXT"),
    9: ("hard_fix_time", "HARDFIX"),
    10: ("soft_fix_time", "SOFTFIX"),
}


class MairListPlaylistDialog(QDialog):
    """mAirList playlist control panel with timing columns."""

    def __init__(self, mairlist_api: MairListAPI, config: MairListConfig,
                 parent=None) -> None:
        super().__init__(parent)
        self._api = mairlist_api
        self._config = config
        self._items: list[PlaylistItem] = []
        self._playlist_num = 1
        self._modified_cells: set[tuple[int, int]] = set()

        self.setWindowTitle("mAirList Playlist Control")
        self.setMinimumSize(980, 520)
        self.setStyleSheet(PLAYLIST_STYLE)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        # --- Header row ---
        header_row = QHBoxLayout()
        title_label = QLabel("MAIRLIST PLAYLIST CONTROL")
        title_label.setStyleSheet(
            "font-size: 13px; font-weight: bold; letter-spacing: 1px; "
            "color: #3498db;"
        )
        header_row.addWidget(title_label)
        header_row.addStretch()

        header_row.addWidget(QLabel("Playlist:"))
        self._playlist_spin = QSpinBox()
        self._playlist_spin.setRange(1, 10)
        self._playlist_spin.setValue(1)
        self._playlist_spin.setFixedWidth(60)
        header_row.addWidget(self._playlist_spin)

        self._refresh_btn = QPushButton("Refresh")
        self._refresh_btn.setToolTip("Load playlist from mAirList")
        self._refresh_btn.clicked.connect(self._on_refresh)
        header_row.addWidget(self._refresh_btn)

        layout.addLayout(header_row)

        # --- Transport controls ---
        transport_frame = QFrame()
        transport_frame.setObjectName("transportPanel")
        transport_layout = QHBoxLayout(transport_frame)
        transport_layout.setContentsMargins(10, 8, 10, 8)
        transport_layout.setSpacing(6)

        # Player selector
        transport_layout.addWidget(QLabel("Player:"))
        self._player_combo = QComboBox()
        self._player_combo.addItems(["A", "B", "C", "D"])
        self._player_combo.setFixedWidth(50)
        transport_layout.addWidget(self._player_combo)

        transport_layout.addSpacing(10)

        # Transport buttons
        self._play_btn = QPushButton("▶ PLAY")
        self._play_btn.setObjectName("playBtn")
        self._play_btn.clicked.connect(lambda: self._player_cmd("START"))
        transport_layout.addWidget(self._play_btn)

        self._pause_btn = QPushButton("⏸ PAUSE")
        self._pause_btn.clicked.connect(lambda: self._player_cmd("PAUSE"))
        transport_layout.addWidget(self._pause_btn)

        self._stop_transport_btn = QPushButton("⏹ STOP")
        self._stop_transport_btn.setObjectName("stopBtn")
        self._stop_transport_btn.clicked.connect(lambda: self._player_cmd("STOP"))
        transport_layout.addWidget(self._stop_transport_btn)

        transport_layout.addSpacing(10)

        self._prev_btn = QPushButton("⏮ PREV")
        self._prev_btn.clicked.connect(lambda: self._player_cmd("PREVIOUS"))
        transport_layout.addWidget(self._prev_btn)

        self._next_btn = QPushButton("⏭ NEXT")
        self._next_btn.clicked.connect(lambda: self._player_cmd("NEXT"))
        transport_layout.addWidget(self._next_btn)

        transport_layout.addStretch()

        # Playlist start button
        self._playlist_start_btn = QPushButton("▶ PLAYLIST START")
        self._playlist_start_btn.setObjectName("playBtn")
        self._playlist_start_btn.clicked.connect(self._on_playlist_start)
        transport_layout.addWidget(self._playlist_start_btn)

        layout.addWidget(transport_frame)

        # --- Playlist table ---
        self._table = QTableWidget()
        self._table.setColumnCount(len(COLUMNS))
        self._table.setHorizontalHeaderLabels([c[0] for c in COLUMNS])
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._table.setAlternatingRowColors(True)
        self._table.setStyleSheet(
            self._table.styleSheet()
            + "QTableWidget { alternate-background-color: #111d2e; }"
        )
        self._table.verticalHeader().setVisible(False)

        # Set column widths
        header = self._table.horizontalHeader()
        for i, (_, width, _, tooltip) in enumerate(COLUMNS):
            self._table.setColumnWidth(i, width)
            self._table.horizontalHeaderItem(i).setToolTip(tooltip)
        header.setStretchLastSection(False)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)

        self._table.cellChanged.connect(self._on_cell_changed)

        layout.addWidget(self._table, 1)

        # --- Bottom bar ---
        bottom_row = QHBoxLayout()

        self._status_label = QLabel("No playlist loaded")
        self._status_label.setStyleSheet("font-size: 11px; color: #7f8fa6;")
        bottom_row.addWidget(self._status_label)
        bottom_row.addStretch()

        self._modified_label = QLabel("")
        self._modified_label.setStyleSheet("font-size: 11px; color: #f1c40f;")
        bottom_row.addWidget(self._modified_label)

        self._apply_btn = QPushButton("Apply Changes")
        self._apply_btn.setObjectName("applyBtn")
        self._apply_btn.setEnabled(False)
        self._apply_btn.clicked.connect(self._on_apply)
        bottom_row.addWidget(self._apply_btn)

        self._close_btn = QPushButton("Close")
        self._close_btn.clicked.connect(self.accept)
        bottom_row.addWidget(self._close_btn)

        layout.addLayout(bottom_row)

        # Connect API signals
        self._api.playlist_loaded.connect(self._on_playlist_loaded)
        self._api.command_sent.connect(self._on_command_ok)
        self._api.command_failed.connect(self._on_command_fail)

    # --- Actions ---

    def _on_refresh(self) -> None:
        self._playlist_num = self._playlist_spin.value()
        self._status_label.setText("Loading playlist...")
        self._refresh_btn.setEnabled(False)
        self._api.load_playlist(self._playlist_num)

    def _on_playlist_start(self) -> None:
        num = self._playlist_spin.value()
        self._api.send_command(f"PLAYLIST {num} START")

    def _player_cmd(self, action: str) -> None:
        player = self._player_combo.currentText()
        self._api.player_command(player, action)

    def _on_apply(self) -> None:
        """Send modified timing values to mAirList."""
        if not self._modified_cells:
            return

        count = 0
        for row, col in sorted(self._modified_cells):
            if col not in COL_PROP_MAP:
                continue
            _, ml_prop = COL_PROP_MAP[col]
            item_widget = self._table.item(row, col)
            if not item_widget:
                continue
            value = item_widget.text().strip()
            if not value:
                continue
            self._api.set_item_property(
                self._playlist_num, row, ml_prop, value
            )
            count += 1

        self._modified_cells.clear()
        self._apply_btn.setEnabled(False)
        self._modified_label.setText("")
        self._status_label.setText(f"Applied {count} changes")

        # Clear highlight on modified cells
        for row in range(self._table.rowCount()):
            for col in range(self._table.columnCount()):
                item = self._table.item(row, col)
                if item:
                    item.setBackground(QColor("transparent"))

    # --- Table population ---

    def _on_playlist_loaded(self, playlist_num: int,
                            items: list[PlaylistItem]) -> None:
        self._items = items
        self._modified_cells.clear()
        self._apply_btn.setEnabled(False)
        self._modified_label.setText("")
        self._refresh_btn.setEnabled(True)

        self._table.blockSignals(True)
        self._table.setRowCount(len(items))

        for row, item in enumerate(items):
            values = [
                str(row + 1),
                item.title,
                item.artist,
                item.duration,
                item.cue_in,
                item.cue_out,
                item.fade_in,
                item.fade_out,
                item.start_next,
                item.hard_fix_time,
                item.soft_fix_time,
                item.item_type,
            ]

            for col, val in enumerate(values):
                cell = QTableWidgetItem(val)
                _, _, editable, _ = COLUMNS[col]
                if not editable:
                    cell.setFlags(cell.flags() & ~Qt.ItemFlag.ItemIsEditable)
                    cell.setForeground(QColor("#7f8fa6"))
                else:
                    cell.setForeground(QColor("#e0e0e0"))

                # Style timing columns
                if col >= 4 and col <= 8 and val and val != "00:00:00.000":
                    cell.setForeground(QColor("#3498db"))
                # Style fix time columns
                if col == 9 and val:
                    cell.setForeground(QColor("#e74c3c"))
                    font = cell.font()
                    font.setBold(True)
                    cell.setFont(font)
                elif col == 10 and val:
                    cell.setForeground(QColor("#f1c40f"))

                self._table.setItem(row, col, cell)

        self._table.blockSignals(False)
        self._status_label.setText(
            f"Playlist {playlist_num}: {len(items)} items"
        )

    def _on_cell_changed(self, row: int, col: int) -> None:
        """Track which cells have been modified."""
        if col not in COL_PROP_MAP:
            return
        self._modified_cells.add((row, col))
        self._apply_btn.setEnabled(True)
        self._modified_label.setText(
            f"{len(self._modified_cells)} change(s) pending"
        )

        # Highlight modified cell
        item = self._table.item(row, col)
        if item:
            item.setBackground(QColor("#1a3a1a"))

    def _on_command_ok(self, command: str) -> None:
        pass

    def _on_command_fail(self, error: str) -> None:
        self._status_label.setText(f"Error: {error}")
        self._status_label.setStyleSheet("font-size: 11px; color: #e74c3c;")
        QTimer.singleShot(
            3000,
            lambda: self._status_label.setStyleSheet(
                "font-size: 11px; color: #7f8fa6;"
            ),
        )
