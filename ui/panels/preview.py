"""Metadata preview panel showing per-file results."""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QTextEdit, QTableWidget, QTableWidgetItem,
    QHeaderView, QSplitter, QGroupBox, QTabWidget
)
from PySide6.QtCore import Qt
from core.orchestrator import FileResult


class PreviewPanel(QWidget):
    """Shows per-file metadata preview in a table."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._results: list[FileResult] = []
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)

        # Instructions
        info_label = QLabel("Process a batch first. Per-file results will appear here.")
        info_label.setAlignment(Qt.AlignCenter)
        info_label.setStyleSheet("padding: 20px;")
        self._info_label = info_label
        layout.addWidget(self._info_label)

        # Results table
        self._table = QTableWidget()
        self._table.setColumnCount(7)
        self._table.setHorizontalHeaderLabels([
            "File", "Status", "Quality", "Title", "Description", "Keywords", "Warnings"
        ])

        header = self._table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(6, QHeaderView.ResizeMode.Stretch)

        self._table.setColumnWidth(1, 70)
        self._table.setColumnWidth(2, 70)
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.verticalHeader().setVisible(False)
        layout.addWidget(self._table)

        # Detail view for selected row
        detail_group = QGroupBox("Selected File Details")
        detail_layout = QVBoxLayout(detail_group)

        self._detail_title = QLabel()
        self._detail_title.setStyleSheet("font-weight: bold; font-size: 13px;")
        detail_layout.addWidget(self._detail_title)

        self._detail_desc = QLabel()
        self._detail_desc.setWordWrap(True)
        self._detail_desc.setStyleSheet("")
        detail_layout.addWidget(self._detail_desc)

        self._detail_keywords = QTextEdit()
        self._detail_keywords.setReadOnly(True)
        self._detail_keywords.setMaximumHeight(120)
        self._detail_keywords.setStyleSheet("font-size: 11px;")
        detail_layout.addWidget(self._detail_keywords)

        layout.addWidget(detail_group)

        self._table.itemSelectionChanged.connect(self._on_selection_changed)

    def add_result(self, result: FileResult) -> None:
        """Add a processed file result to the table."""
        self._info_label.setVisible(False)

        row = self._table.rowCount()
        self._table.insertRow(row)

        # File name
        import os
        file_item = QTableWidgetItem(os.path.basename(result.file_path))
        file_item.setData(Qt.UserRole, result.file_path)
        self._table.setItem(row, 0, file_item)

        # Status
        status = QTableWidgetItem("OK" if result.success else "FAIL")
        status.setForeground(Qt.GlobalColor.green if result.success else Qt.GlobalColor.red)
        status.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        self._table.setItem(row, 1, status)

        # Quality
        quality = QTableWidgetItem(f"{result.quality_score}/100")
        quality.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        if result.quality_score >= 80:
            quality.setForeground(Qt.GlobalColor.green)
        elif result.quality_score >= 60:
            quality.setForeground(Qt.GlobalColor.darkYellow)
        else:
            quality.setForeground(Qt.GlobalColor.red)
        self._table.setItem(row, 2, quality)

        # Title
        title_item = QTableWidgetItem(result.title[:80] + ('...' if len(result.title) > 80 else ''))
        self._table.setItem(row, 3, title_item)

        # Description
        desc_item = QTableWidgetItem(result.description[:80] + ('...' if len(result.description) > 80 else ''))
        self._table.setItem(row, 4, desc_item)

        # Keywords (preview)
        kw_preview = ', '.join(result.keywords[:5]) + ('...' if len(result.keywords) > 5 else '')
        kw_item = QTableWidgetItem(kw_preview)
        self._table.setItem(row, 5, kw_item)

        # Warnings
        warning_text = '; '.join(result.warnings[:2]) if result.warnings else ''
        warn_item = QTableWidgetItem(warning_text)
        if result.warnings:
            warn_item.setForeground(Qt.GlobalColor.darkYellow)
        self._table.setItem(row, 6, warn_item)

        self._results.append(result)

    def _on_selection_changed(self) -> None:
        """Show details for selected row."""
        selected = self._table.selectedItems()
        if not selected:
            return

        row = selected[0].row()
        if row < 0 or row >= len(self._results):
            return

        result = self._results[row]
        import os
        self._detail_title.setText(os.path.basename(result.file_path))
        self._detail_desc.setText(result.description)
        self._detail_keywords.setText(', '.join(result.keywords))

    def set_results(self, results: list[FileResult]) -> None:
        """Replace all results."""
        self._results = results
        self._table.setRowCount(0)
        for result in results:
            self.add_result(result)
