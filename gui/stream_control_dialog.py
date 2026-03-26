"""Stream Control dialog — schedule streams with automatic switching."""

from datetime import datetime

from PyQt6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QTableWidget, QTableWidgetItem, QCheckBox,
    QComboBox, QTimeEdit, QWidget, QHeaderView,
)
from PyQt6.QtCore import Qt, QTime, QTimer
from PyQt6.QtGui import QColor, QPalette

from models.config import ScheduleConfig, ScheduleEntry
from models.source import SourceManager
from gui.theme import (
    ACCENT, SUCCESS, ERROR, WARNING,
    TEXT_PRIMARY, TEXT_SECONDARY, TEXT_MUTED,
    FONT_SM, FONT_MD, FONT_LG, FONT_XL, SPACING_MD, SPACING_SM,
    BG_SECONDARY, CARD_BG, CARD_BORDER, INPUT_BG, INPUT_BORDER,
    SELECTION_BG,
)
from gui.frameless import FramelessDialog

MANUAL_URL = "-- Manual URL --"

DAY_NAMES = ["M", "T", "W", "T", "F", "S", "S"]
DAY_FULL = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

# Compact style overrides for widgets inside table cells
CELL_TIME_STYLE = (
    f"QTimeEdit {{ background-color: {INPUT_BG}; border: 1px solid {INPUT_BORDER}; "
    f"border-radius: 6px; padding: 2px 6px; color: {TEXT_PRIMARY}; "
    f"font-size: {FONT_MD}px; }}"
)
CELL_COMBO_STYLE = (
    f"QComboBox {{ background-color: {INPUT_BG}; border: 1px solid {INPUT_BORDER}; "
    f"border-radius: 6px; padding: 2px 6px; color: {TEXT_PRIMARY}; "
    f"font-size: {FONT_SM}px; min-height: 0px; }}"
    f"QComboBox::drop-down {{ border: none; width: 18px; }}"
    f"QComboBox::down-arrow {{ border-left: 3px solid transparent; "
    f"border-right: 3px solid transparent; border-top: 4px solid {TEXT_SECONDARY}; "
    f"width: 0; height: 0; margin-right: 6px; }}"
)


def _days_summary(days: list) -> str:
    """Return a short summary string for a days list."""
    if not days or len(days) == 7:
        return "All"
    weekdays = {0, 1, 2, 3, 4}
    weekend = {5, 6}
    s = set(days)
    if s == weekdays:
        return "M-F"
    if s == weekend:
        return "S,S"
    return ",".join(DAY_NAMES[d] for d in sorted(days) if 0 <= d <= 6)


class DaySelectorDialog(FramelessDialog):
    """Small popup with 7 checkboxes for day selection."""

    def __init__(self, days: list, parent=None) -> None:
        super().__init__(parent, title="Days")
        self.setFixedSize(260, 250)

        layout = self.content_layout
        layout.setSpacing(SPACING_SM)

        self._checks: list[QCheckBox] = []
        for i, name in enumerate(DAY_FULL):
            cb = QCheckBox(name)
            cb.setChecked(i in days)
            self._checks.append(cb)
            layout.addWidget(cb)

        btn_row = QHBoxLayout()
        all_btn = QPushButton("All")
        all_btn.setObjectName("smallBtn")
        all_btn.clicked.connect(self._select_all)
        btn_row.addWidget(all_btn)
        none_btn = QPushButton("None")
        none_btn.setObjectName("smallBtn")
        none_btn.clicked.connect(self._select_none)
        btn_row.addWidget(none_btn)
        btn_row.addStretch()
        ok_btn = QPushButton("OK")
        ok_btn.setObjectName("accentBtn")
        ok_btn.clicked.connect(self.accept)
        btn_row.addWidget(ok_btn)
        layout.addLayout(btn_row)

    def _select_all(self) -> None:
        for cb in self._checks:
            cb.setChecked(True)

    def _select_none(self) -> None:
        for cb in self._checks:
            cb.setChecked(False)

    def get_days(self) -> list:
        return [i for i, cb in enumerate(self._checks) if cb.isChecked()]


class StreamControlDialog(FramelessDialog):
    """Schedule streams with start/end times and automatic switching."""

    COL_NUM = 0
    COL_START = 1
    COL_END = 2
    COL_SOURCE = 3
    COL_URL = 4
    COL_DAYS = 5
    COL_ON = 6

    def __init__(self, config: ScheduleConfig, source_manager: SourceManager,
                 parent=None) -> None:
        super().__init__(parent, title="Stream Control")
        self._config = ScheduleConfig(
            enabled=config.enabled,
            entries=list(config.entries),
            keep_playing_on_gap=config.keep_playing_on_gap,
        )
        self._source_manager = source_manager
        self._row_days: dict[int, list] = {}  # row -> days list

        self.setMinimumSize(780, 580)

        layout = self.content_layout
        layout.setSpacing(SPACING_MD)
        layout.setContentsMargins(20, 0, 20, 20)

        # --- Header ---
        header = QHBoxLayout()
        title = QLabel("STREAM CONTROL")
        title.setStyleSheet(
            f"font-size: {FONT_XL}px; font-weight: 800; color: {ACCENT}; "
            "letter-spacing: 1px;"
        )
        header.addWidget(title)
        header.addStretch()
        self._clock_label = QLabel()
        self._clock_label.setStyleSheet(
            f"font-size: {FONT_MD}px; color: {TEXT_SECONDARY};"
        )
        header.addWidget(self._clock_label)
        layout.addLayout(header)

        # --- Options row ---
        opts = QHBoxLayout()
        self._enabled_check = QCheckBox("Enable schedule")
        self._enabled_check.setChecked(config.enabled)
        opts.addWidget(self._enabled_check)
        opts.addSpacing(20)
        self._keep_playing_check = QCheckBox("Keep stream when no next entry")
        self._keep_playing_check.setChecked(config.keep_playing_on_gap)
        opts.addWidget(self._keep_playing_check)
        opts.addStretch()
        layout.addLayout(opts)

        # --- Table ---
        self._table = QTableWidget(0, 7)
        self._table.setHorizontalHeaderLabels(
            ["#", "Start", "End", "Source", "URL", "Days", "On"]
        )
        hdr = self._table.horizontalHeader()
        hdr.setSectionResizeMode(self.COL_NUM, QHeaderView.ResizeMode.Fixed)
        hdr.setSectionResizeMode(self.COL_START, QHeaderView.ResizeMode.Fixed)
        hdr.setSectionResizeMode(self.COL_END, QHeaderView.ResizeMode.Fixed)
        hdr.setSectionResizeMode(self.COL_SOURCE, QHeaderView.ResizeMode.Fixed)
        hdr.setSectionResizeMode(self.COL_URL, QHeaderView.ResizeMode.Stretch)
        hdr.setSectionResizeMode(self.COL_DAYS, QHeaderView.ResizeMode.Fixed)
        hdr.setSectionResizeMode(self.COL_ON, QHeaderView.ResizeMode.Fixed)
        self._table.setColumnWidth(self.COL_NUM, 32)
        self._table.setColumnWidth(self.COL_START, 100)
        self._table.setColumnWidth(self.COL_END, 100)
        self._table.setColumnWidth(self.COL_SOURCE, 160)
        self._table.setColumnWidth(self.COL_DAYS, 70)
        self._table.setColumnWidth(self.COL_ON, 40)
        self._table.verticalHeader().setVisible(False)
        self._table.verticalHeader().setDefaultSectionSize(36)
        # Override palette selection colors to match dark theme
        pal = self._table.palette()
        pal.setColor(QPalette.ColorRole.Highlight, QColor(34, 211, 238, 20))
        pal.setColor(QPalette.ColorRole.HighlightedText, QColor(TEXT_PRIMARY))
        self._table.setPalette(pal)
        self._table.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows
        )
        self._table.setSelectionMode(
            QTableWidget.SelectionMode.SingleSelection
        )
        layout.addWidget(self._table, 1)

        # --- Action buttons ---
        actions = QHBoxLayout()
        add_btn = QPushButton("+ Add")
        add_btn.setObjectName("accentBtn")
        add_btn.clicked.connect(self._on_add)
        actions.addWidget(add_btn)
        remove_btn = QPushButton("- Remove")
        remove_btn.setObjectName("dangerBtn")
        remove_btn.clicked.connect(self._on_remove)
        actions.addWidget(remove_btn)
        dup_btn = QPushButton("Duplicate")
        dup_btn.clicked.connect(self._on_duplicate)
        actions.addWidget(dup_btn)
        actions.addStretch()
        up_btn = QPushButton("Move Up")
        up_btn.clicked.connect(self._on_move_up)
        actions.addWidget(up_btn)
        down_btn = QPushButton("Move Down")
        down_btn.clicked.connect(self._on_move_down)
        actions.addWidget(down_btn)
        layout.addLayout(actions)

        # --- Now playing panel ---
        now_frame = QWidget()
        now_frame.setStyleSheet(
            f"background-color: {CARD_BG}; border: 1px solid {CARD_BORDER}; "
            "border-radius: 10px;"
        )
        now_layout = QVBoxLayout(now_frame)
        now_layout.setContentsMargins(14, 10, 14, 10)
        now_layout.setSpacing(4)
        self._now_label = QLabel("No active schedule")
        self._now_label.setStyleSheet(
            f"font-size: {FONT_MD}px; color: {TEXT_PRIMARY}; border: none;"
        )
        now_layout.addWidget(self._now_label)
        self._next_label = QLabel("")
        self._next_label.setStyleSheet(
            f"font-size: {FONT_SM}px; color: {TEXT_SECONDARY}; border: none;"
        )
        now_layout.addWidget(self._next_label)
        layout.addWidget(now_frame)

        # --- Bottom buttons ---
        bottom = QHBoxLayout()
        bottom.addStretch()
        save_btn = QPushButton("Save & Apply")
        save_btn.setObjectName("saveBtn")
        save_btn.clicked.connect(self.accept)
        bottom.addWidget(save_btn)
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.reject)
        bottom.addWidget(close_btn)
        layout.addLayout(bottom)

        # --- Load existing entries ---
        self._populate_entries()

        # --- Timer for clock + active row highlight ---
        self._tick_timer = QTimer(self)
        self._tick_timer.setInterval(1000)
        self._tick_timer.timeout.connect(self._on_tick)
        self._tick_timer.start()
        self._on_tick()

    # ── Populate table from config ──────────────────────────────────────

    def _populate_entries(self) -> None:
        self._table.setRowCount(0)
        self._row_days.clear()
        for entry in self._config.entries:
            if isinstance(entry, dict):
                e = ScheduleEntry(**{
                    k: v for k, v in entry.items()
                    if k in ScheduleEntry.__dataclass_fields__
                })
            else:
                e = entry
            self._add_row(e)

    def _make_time_edit(self, time_str: str = "") -> QTimeEdit:
        """Create a compact QTimeEdit for table cells."""
        te = QTimeEdit()
        te.setDisplayFormat("HH:mm")
        te.setStyleSheet(CELL_TIME_STYLE)
        te.setButtonSymbols(QTimeEdit.ButtonSymbols.NoButtons)
        if time_str:
            parts = time_str.split(":")
            if len(parts) == 2:
                te.setTime(QTime(int(parts[0]), int(parts[1])))
        return te

    def _make_source_combo(self, source_name: str, row: int) -> QComboBox:
        """Create a compact QComboBox for source selection in table cells."""
        combo = QComboBox()
        combo.setStyleSheet(CELL_COMBO_STYLE)
        combo.addItem(MANUAL_URL)
        for src in self._source_manager.sources:
            combo.addItem(src.name)
        if source_name:
            idx = combo.findText(source_name)
            if idx >= 0:
                combo.setCurrentIndex(idx)
        combo.currentTextChanged.connect(
            lambda text, r=row: self._on_source_changed(r, text)
        )
        return combo

    def _make_check_widget(self, checked: bool) -> QWidget:
        """Create a centered checkbox widget for table cells."""
        w = QWidget()
        lay = QHBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setAlignment(Qt.AlignmentFlag.AlignCenter)
        cb = QCheckBox()
        cb.setChecked(checked)
        lay.addWidget(cb)
        return w

    def _add_row(self, entry: ScheduleEntry | None = None) -> int:
        row = self._table.rowCount()
        self._table.insertRow(row)

        # Col 0: row number
        num_item = QTableWidgetItem(str(row + 1))
        num_item.setFlags(Qt.ItemFlag.ItemIsEnabled)
        num_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        self._table.setItem(row, self.COL_NUM, num_item)

        # Col 1: Start time
        self._table.setCellWidget(
            row, self.COL_START,
            self._make_time_edit(entry.time if entry else "")
        )

        # Col 2: End time
        self._table.setCellWidget(
            row, self.COL_END,
            self._make_time_edit(entry.stop_time if entry else "")
        )

        # Col 3: Source combo
        source_name = getattr(entry, "source_name", "") if entry else ""
        self._table.setCellWidget(
            row, self.COL_SOURCE,
            self._make_source_combo(source_name, row)
        )

        # Col 4: URL
        url_item = QTableWidgetItem(entry.url if entry else "")
        if source_name:
            url_item.setFlags(Qt.ItemFlag.ItemIsEnabled)
            src = self._source_manager.get_by_name(source_name)
            if src:
                url_item.setText(src.url)
        self._table.setItem(row, self.COL_URL, url_item)

        # Col 5: Days button
        days = list(getattr(entry, "days", []) if entry else [])
        self._row_days[row] = days
        days_btn = QPushButton(_days_summary(days))
        days_btn.setObjectName("smallBtn")
        days_btn.setStyleSheet(
            f"QPushButton {{ padding: 2px 6px; font-size: {FONT_SM}px; "
            f"border-radius: 4px; }}"
        )
        days_btn.clicked.connect(lambda _, r=row: self._on_days_clicked(r))
        self._table.setCellWidget(row, self.COL_DAYS, days_btn)

        # Col 6: Enabled checkbox
        self._table.setCellWidget(
            row, self.COL_ON,
            self._make_check_widget(entry.enabled if entry else True)
        )

        return row

    # ── Source combo change ──────────────────────────────────────────────

    def _on_source_changed(self, row: int, text: str) -> None:
        url_item = self._table.item(row, self.COL_URL)
        if not url_item:
            return
        if text == MANUAL_URL:
            url_item.setFlags(
                Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsEditable |
                Qt.ItemFlag.ItemIsSelectable
            )
        else:
            src = self._source_manager.get_by_name(text)
            if src:
                url_item.setText(src.url)
            url_item.setFlags(Qt.ItemFlag.ItemIsEnabled)

    # ── Days popup ───────────────────────────────────────────────────────

    def _on_days_clicked(self, row: int) -> None:
        days = self._row_days.get(row, [])
        dlg = DaySelectorDialog(days, self)
        if dlg.exec():
            new_days = dlg.get_days()
            self._row_days[row] = new_days
            btn = self._table.cellWidget(row, self.COL_DAYS)
            if btn:
                btn.setText(_days_summary(new_days))

    # ── Add / Remove / Duplicate / Move ──────────────────────────────────

    def _on_add(self) -> None:
        self._add_row()
        self._renumber()

    def _on_remove(self) -> None:
        row = self._table.currentRow()
        if row < 0:
            return
        self._table.removeRow(row)
        # Shift days data
        new_days = {}
        for r in sorted(self._row_days):
            if r < row:
                new_days[r] = self._row_days[r]
            elif r > row:
                new_days[r - 1] = self._row_days[r]
        self._row_days = new_days
        self._renumber()

    def _on_duplicate(self) -> None:
        row = self._table.currentRow()
        if row < 0:
            return
        entry = self._read_row(row)
        if entry:
            new_row = self._add_row(entry)
            self._row_days[new_row] = list(self._row_days.get(row, []))
            self._renumber()

    def _on_move_up(self) -> None:
        row = self._table.currentRow()
        if row <= 0:
            return
        self._swap_rows(row, row - 1)
        self._table.selectRow(row - 1)

    def _on_move_down(self) -> None:
        row = self._table.currentRow()
        if row < 0 or row >= self._table.rowCount() - 1:
            return
        self._swap_rows(row, row + 1)
        self._table.selectRow(row + 1)

    def _swap_rows(self, a: int, b: int) -> None:
        entry_a = self._read_row(a)
        entry_b = self._read_row(b)
        days_a = self._row_days.get(a, [])
        days_b = self._row_days.get(b, [])
        # Remove both rows and re-insert
        self._table.removeRow(max(a, b))
        self._table.removeRow(min(a, b))
        # Reinsert in swapped order
        if a < b:
            self._table.insertRow(a)
            self._set_row_data(a, entry_b, days_b)
            self._table.insertRow(b)
            self._set_row_data(b, entry_a, days_a)
        else:
            self._table.insertRow(b)
            self._set_row_data(b, entry_a, days_a)
            self._table.insertRow(a)
            self._set_row_data(a, entry_b, days_b)
        self._renumber()

    def _set_row_data(self, row: int, entry: ScheduleEntry, days: list) -> None:
        """Populate an already-inserted empty row with entry data."""
        # Num
        num_item = QTableWidgetItem(str(row + 1))
        num_item.setFlags(Qt.ItemFlag.ItemIsEnabled)
        num_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        self._table.setItem(row, self.COL_NUM, num_item)

        # Start / End
        self._table.setCellWidget(
            row, self.COL_START, self._make_time_edit(entry.time)
        )
        self._table.setCellWidget(
            row, self.COL_END, self._make_time_edit(entry.stop_time)
        )

        # Source combo
        self._table.setCellWidget(
            row, self.COL_SOURCE,
            self._make_source_combo(entry.source_name, row)
        )

        # URL
        url_item = QTableWidgetItem(entry.url)
        if entry.source_name:
            url_item.setFlags(Qt.ItemFlag.ItemIsEnabled)
        self._table.setItem(row, self.COL_URL, url_item)

        # Days
        self._row_days[row] = list(days)
        days_btn = QPushButton(_days_summary(days))
        days_btn.setObjectName("smallBtn")
        days_btn.setStyleSheet(
            f"QPushButton {{ padding: 2px 6px; font-size: {FONT_SM}px; "
            f"border-radius: 4px; }}"
        )
        days_btn.clicked.connect(lambda _, r=row: self._on_days_clicked(r))
        self._table.setCellWidget(row, self.COL_DAYS, days_btn)

        # Enabled
        self._table.setCellWidget(
            row, self.COL_ON,
            self._make_check_widget(entry.enabled)
        )

    def _renumber(self) -> None:
        for row in range(self._table.rowCount()):
            item = self._table.item(row, self.COL_NUM)
            if item:
                item.setText(str(row + 1))

    # ── Read row data ────────────────────────────────────────────────────

    def _read_row(self, row: int) -> ScheduleEntry | None:
        if row < 0 or row >= self._table.rowCount():
            return None
        start_w = self._table.cellWidget(row, self.COL_START)
        end_w = self._table.cellWidget(row, self.COL_END)
        combo = self._table.cellWidget(row, self.COL_SOURCE)
        url_item = self._table.item(row, self.COL_URL)
        on_widget = self._table.cellWidget(row, self.COL_ON)

        time_str = start_w.time().toString("HH:mm") if start_w else ""
        stop_time = end_w.time().toString("HH:mm") if end_w else ""
        source_text = combo.currentText() if combo else MANUAL_URL
        source_name = "" if source_text == MANUAL_URL else source_text
        url = url_item.text() if url_item else ""
        enabled = True
        if on_widget:
            cb = on_widget.findChild(QCheckBox)
            if cb:
                enabled = cb.isChecked()
        days = self._row_days.get(row, [])

        return ScheduleEntry(
            time=time_str,
            url=url,
            enabled=enabled,
            days=days,
            stop_time=stop_time,
            source_name=source_name,
        )

    # ── Get config (called after accept) ─────────────────────────────────

    def get_config(self) -> ScheduleConfig:
        entries = []
        for row in range(self._table.rowCount()):
            entry = self._read_row(row)
            if entry:
                entries.append(entry)
        return ScheduleConfig(
            enabled=self._enabled_check.isChecked(),
            entries=entries,
            keep_playing_on_gap=self._keep_playing_check.isChecked(),
        )

    # ── Clock tick + active row highlight ─────────────────────────────────

    def _on_tick(self) -> None:
        now = datetime.now()
        self._clock_label.setText(f"Current time: {now.strftime('%H:%M:%S')}")

        now_time = now.strftime("%H:%M")
        now_weekday = now.weekday()
        active_row = -1
        next_entry_text = ""
        next_time = None

        for row in range(self._table.rowCount()):
            entry = self._read_row(row)
            if not entry or not entry.enabled:
                continue
            days = self._row_days.get(row, [])
            if days and now_weekday not in days:
                continue

            # Check if this entry is currently active
            if entry.time and entry.stop_time:
                if entry.time <= now_time < entry.stop_time:
                    active_row = row

            # Find next upcoming entry
            if entry.time and entry.time > now_time:
                if next_time is None or entry.time < next_time:
                    next_time = entry.time
                    name = entry.source_name or entry.url[:40]
                    next_entry_text = f"Next: {name} at {entry.time}"

        # Highlight active row (all cells)
        active_bg = QColor(34, 211, 238, 20)
        clear_bg = QColor(0, 0, 0, 0)
        for row in range(self._table.rowCount()):
            is_active = (row == active_row)
            bg = active_bg if is_active else clear_bg
            for col in (self.COL_NUM, self.COL_URL):
                item = self._table.item(row, col)
                if item:
                    item.setBackground(bg)

        # Update now panel
        if active_row >= 0:
            entry = self._read_row(active_row)
            if entry:
                name = entry.source_name or entry.url[:40]
                self._now_label.setText(
                    f"  {name} ({entry.time} - {entry.stop_time})  ● Active"
                )
                self._now_label.setStyleSheet(
                    f"font-size: {FONT_MD}px; color: {SUCCESS}; "
                    "font-weight: 600; border: none;"
                )
        else:
            self._now_label.setText("No active schedule")
            self._now_label.setStyleSheet(
                f"font-size: {FONT_MD}px; color: {TEXT_MUTED}; border: none;"
            )

        self._next_label.setText(next_entry_text)
