import functools
import os
import sys
from PySide6.QtWidgets import (
    QMainWindow, QVBoxLayout, QHBoxLayout,
    QProgressBar, QLabel, QFileDialog, QMessageBox,
    QSplitter, QStatusBar, QWidget, QFrame, QTableWidget, QTableWidgetItem,
    QLineEdit, QPushButton, QSpinBox, QComboBox, QHeaderView, QDialog, QCheckBox
)
from PySide6.QtCore import Qt, QThread, Signal, QTimer, QObject, QSize, QByteArray, Property, QRect, QRunnable, QThreadPool
from PySide6.QtGui import QFont, QPixmap, QImage, QIcon, QPainter

from config.settings import Settings
from core.orchestrator import BatchOrchestrator, BatchReport, FileResult
from core.scanner import Scanner
from export.csv import CsvExporter
from ui.panels.settings import SettingsPanel


class MainWindow(QMainWindow):
    """Main application window."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("AI Stock Metadata Agent")
        self.resize(1100, 700)

        self.settings = Settings()
        self._orchestrator = None
        self._current_report = None
        self._is_processing = False
        self._worker_thread = None
        self._worker = None

        self._setup_ui()

    def _setup_ui(self):
        """Set up the main UI layout."""
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Process panel (main content, spans full height)
        self._process_panel = ProcessPage(self)
        layout.addWidget(self._process_panel)

        # Status bar at bottom: progress bar spans full width with centered text
        self._progress_bar = QProgressBar()
        self._progress_bar.setFixedHeight(28)
        self._progress_bar.setRange(0, 100)
        self._progress_bar.setValue(0)
        self._progress_bar.setAlignment(Qt.AlignCenter)
        self._progress_bar.setFormat("Ready")
        self._update_progress_style()
        layout.addWidget(self._progress_bar)

        # Wire up batch panel actions
        self._process_panel.start_signal.connect(self._on_batch_start)
        self._process_panel.cancel_signal.connect(self._on_batch_cancel)

    def _update_progress_style(self):
        dark = _is_dark()
        if dark:
            bg = '#18181b'
            text = '#ffffff'
            chunk = '#6366f1'
        else:
            bg = '#ffffff'
            text = '#111827'
            chunk = '#6366f1'
        self._progress_bar.setStyleSheet(f"""
            QProgressBar {{
                border: none;
                text-align: center;
                font-size: 13px;
                font-weight: 500;
                color: {text};
                background: {bg};
            }}
            QProgressBar::chunk {{
                background: {chunk};
            }}
        """)

    @staticmethod
    def _gear_icon_svg():
        import math
        from PySide6.QtGui import QPainter, QBrush
        from PySide6.QtCore import QPointF
        from PySide6.QtGui import QPainterPath
        size = 24
        img = QImage(size, size, QImage.Format.Format_ARGB32)
        img.fill(0)
        painter = QPainter(img)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        teeth = 8
        outer_r = size * 0.42
        inner_r = size * 0.34
        hole_r = size * 0.14
        cx = cy = size / 2
        # Gear body + center hole as single path with OddEvenEdit fill rule
        path = QPainterPath()
        path.setFillRule(Qt.FillRule.OddEvenFill)
        # Outer shape
        first = True
        for i in range(teeth * 2):
            angle = math.pi * 2 * i / (teeth * 2) - math.pi / 2
            r = outer_r if i % 2 == 0 else inner_r
            if first:
                path.moveTo(cx + r * math.cos(angle), cy + r * math.sin(angle))
                first = False
            else:
                path.lineTo(cx + r * math.cos(angle), cy + r * math.sin(angle))
        path.closeSubpath()
        # Inner hole subpath
        path.addEllipse(QPointF(cx, cy), hole_r, hole_r)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush("#18181b"))
        painter.drawPath(path)
        painter.end()
        return QIcon(QPixmap.fromImage(img))

    def _open_settings(self):
        from PySide6.QtWidgets import QDialog
        from PySide6.QtCore import Qt as QtCore
        dialog = QDialog(self)
        dialog.setWindowTitle("Settings")
        dialog.setWindowFlags(QtCore.Window | QtCore.WindowCloseButtonHint)
        dialog.setModal(True)

        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(16, 16, 16, 16)
        self._settings_panel = SettingsPanel(self)
        layout.addWidget(self._settings_panel)
        self._settings_panel.settings_saved.connect(dialog.accept)

        # Size dialog for all fields: show text section, measure, fix size, restore state
        self._settings_panel._text_section.setVisible(True)
        dialog.show()
        dialog.adjustSize()
        full_size = dialog.size()
        # Restore the correct visibility from settings
        self._settings_panel._load_settings()
        dialog.setFixedSize(full_size)
        dialog.exec()

    def _on_batch_start(self, folder_path):
        """Start batch processing."""
        if self._is_processing:
            return

        self._cleanup_worker()
        self.settings.load()

        missing = self.settings.validate_endpoints()
        if missing:
            QMessageBox.warning(
                self, "Configuration Error",
                f"Missing required settings:\n" + "\n".join(f"• {m}" for m in missing) +
                "\n\nPlease configure endpoints in Settings."
            )
            self._tabs.setCurrentIndex(1)
            return

        # Health check endpoints before starting
        from ai.client import AIClient
        vision_client = AIClient(
            base_url=self.settings.vision_endpoint,
            api_key=self.settings.vision_api_key,
            timeout=10,
        )
        text_client = AIClient(
            base_url=self.settings.text_endpoint,
            api_key=self.settings.text_api_key,
            timeout=10,
        )
        if not vision_client.health_check():
            QMessageBox.warning(
                self, "Connection Error",
                f"Cannot connect to vision model at:\n{self.settings.vision_endpoint}\n\n"
                f"Make sure your local AI server (OMLX/Ollama) is running and the endpoint is correct."
            )
            vision_client.close()
            text_client.close()
            return
        if not text_client.health_check():
            QMessageBox.warning(
                self, "Connection Error",
                f"Cannot connect to text model at:\n{self.settings.text_endpoint}\n\n"
                f"Make sure your local AI server (OMLX/Ollama) is running and the endpoint is correct."
            )
            vision_client.close()
            text_client.close()
            return
        vision_client.close()
        text_client.close()

        self._is_processing = True
        self._current_folder = folder_path
        # Clear old results and stats for a clean slate
        self._process_panel._stats_card.setVisible(False)
        self._process_panel._results_view._table.setRowCount(0)
        self._process_panel._results_view._placeholder.setVisible(False)
        self._process_panel._results_view._detail.setVisible(False)
        self._process_panel._results_view._results = []
        self._process_panel._results_view._file_paths = []
        self._process_panel._results_view._row_spinning = {}
        self._process_panel.set_processing_state(True)
        self._progress_bar.setRange(0, 100)
        self._progress_bar.setValue(0)
        self._progress_bar.setFormat("Scanning files...")
        # Pre-populate table with file names
        scanner = Scanner(folder_path)
        files = scanner.scan()
        if files:
            self._process_panel._results_view._placeholder.setVisible(False)
            self._process_panel._results_view._table.setVisible(True)
            for f in files:
                self._process_panel._results_view.add_pending_file(f)
            self._progress_bar.setFormat(f"Found {len(files)} files — starting...")

        self._orchestrator = BatchOrchestrator(
            self.settings,
            content_type_override=self._process_panel._options_card.get_content_type_override(),
        )
        self._orchestrator.set_progress_callback(self._on_progress)
        self._orchestrator.set_file_callback(self._on_file_result)
        # Connect spinner signal (queued for thread safety)
        self._orchestrator.signals.file_processing.connect(self._on_file_processing, Qt.ConnectionType.QueuedConnection)

        self._worker_thread = QThread()
        self._worker = _BatchWorker(self._orchestrator, folder_path)
        self._worker.moveToThread(self._worker_thread)

        self._worker_thread.started.connect(self._worker.run)
        self._worker.finished.connect(self._on_batch_finished, Qt.ConnectionType.QueuedConnection)
        self._worker.error.connect(self._on_batch_error, Qt.ConnectionType.QueuedConnection)
        self._worker_thread.finished.connect(self._worker_thread.deleteLater)
        self._worker_thread.start()

    def _on_batch_cancel(self):
        """Cancel batch processing."""
        self._progress_bar.setFormat("Cancelling...")
        self._process_panel._results_view._placeholder.setText("Cancelling...")
        # Stop all spinning timers immediately
        self._process_panel._results_view.stop_all_spinners()
        if self._orchestrator:
            self._orchestrator.cancel()

    def _on_progress(self, current, total, message):
        """Update progress bar."""
        if not self.isVisible():
            return
        if total > 0:
            self._progress_bar.setRange(0, total)
            self._progress_bar.setValue(current)
            self._progress_bar.setFormat(f"{current}/{total} — {message}")
        else:
            self._progress_bar.setFormat(message)

    def _on_file_processing(self, file_path):
        """Show spinner for a file that just started processing."""
        if not self.isVisible():
            return
        import logging
        logging.getLogger(__name__).info(f"Starting spinner for: {file_path}")
        self._process_panel._results_view.start_spinner(file_path)

    def _on_file_result(self, result):
        """Handle per-file result."""
        if not self.isVisible():
            return
        self._process_panel.add_result(result)

    def _on_batch_finished(self, report):
        """Handle batch completion."""
        QTimer.singleShot(0, lambda: self._finalize_batch(report))

    def _finalize_batch(self, report):
        """Finalize batch processing."""
        if not self.isVisible():
            return

        self._is_processing = False
        self._current_report = report
        self._progress_bar.setRange(0, 100)
        self._progress_bar.setValue(100)
        # Stop all spinning timers and hide spinners
        self._process_panel._results_view.stop_all_spinners()

        if report.cancelled > 0:
            self._progress_bar.setFormat(f"Cancelled: {report.successful} processed, {report.cancelled} skipped — {report.format_total_time()}")
            self._process_panel._results_view._placeholder.setText("Cancelled")
        else:
            self._progress_bar.setFormat(f"Done: {report.successful}/{report.total_files} — {report.format_total_time()}")
            self._process_panel._results_view._placeholder.setText("Select a folder and click Process to get started.")

        # Update process panel summary
        self._process_panel.display_report(report)

        # CSV export — always in the root source folder
        if self._process_panel._options_card.get_export_csv() and report.successful > 0:
            exporter = CsvExporter()
            csv_dir = self._current_folder if hasattr(self, '_current_folder') else '.'
            csv_path = os.path.join(csv_dir, 'metadata_export.csv')
            exporter.export_batch(report.results, csv_path)

        self._cleanup_worker()
        self._process_panel.set_processing_state(False)

    def _on_batch_error(self, error):
        """Handle batch error."""
        if not self.isVisible():
            return

        self._is_processing = False
        self._progress_bar.setRange(0, 100)
        self._progress_bar.setValue(0)
        self._progress_bar.setFormat("Error")
        QMessageBox.critical(self, "Batch Error", error)
        self._process_panel.set_processing_state(False)
        self._cleanup_worker()

    def _cleanup_worker(self):
        """Safely clean up the worker thread."""
        if self._worker:
            try:
                self._worker.finished.disconnect(self._on_batch_finished)
            except RuntimeError:
                pass
            try:
                self._worker.error.disconnect(self._on_batch_error)
            except RuntimeError:
                pass

        if self._worker_thread and self._worker_thread.isRunning():
            self._worker_thread.quit()
            self._worker_thread.wait(3000)
            if self._worker_thread.isRunning():
                self._worker_thread.terminate()
                self._worker_thread.wait(2000)

        if self._worker:
            self._worker.deleteLater()
            self._worker = None
        if self._worker_thread:
            self._worker_thread.deleteLater()
            self._worker_thread = None

    def closeEvent(self, event):
        """Handle window close."""
        if self._is_processing and self._orchestrator:
            self._orchestrator.cancel()
        self._cleanup_worker()
        if self._orchestrator:
            self._orchestrator.cleanup()
        event.accept()


class ProcessPage(QWidget):
    """Single-page process view: left controls + right results."""

    start_signal = Signal(str)
    cancel_signal = Signal()

    def __init__(self, parent):
        super().__init__(parent)
        self.main_window = parent
        self.settings = parent.settings

        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(16)

        # Left panel: title + folder + buttons (fixed width)
        left = QFrame()
        left.setObjectName('card')
        left.setFixedWidth(280)
        left_layout = QVBoxLayout(left)
        left_layout.setSpacing(16)
        left_layout.setContentsMargins(16, 16, 16, 16)

        # Title row with settings gear
        title_row = QHBoxLayout()
        title_row.setSpacing(8)
        title_row.setContentsMargins(0, 0, 0, 0)
        title_label = QLabel("AI Stock Metadata Agent")
        title_label.setStyleSheet("font-size: 16px; font-weight: 700;")
        title_row.addWidget(title_label, 0)
        title_row.addStretch()
        gear_btn = QPushButton()
        gear_btn.setIcon(self.main_window._gear_icon_svg())
        gear_btn.setFixedSize(28, 28)
        gear_btn.setToolTip("Settings")
        gear_btn.clicked.connect(self.main_window._open_settings)
        title_row.addWidget(gear_btn, 0)
        left_layout.addLayout(title_row)

        # Folder input
        self._folder_row = QHBoxLayout()
        self._folder_input = QLineEdit()
        self._folder_input.setPlaceholderText("Select folder with photos & videos...")
        self._folder_row.addWidget(self._folder_input)
        browse_btn = QPushButton("Browse")
        browse_btn.setObjectName('secondary')
        browse_btn.clicked.connect(self._on_browse)
        self._folder_row.addWidget(browse_btn)
        left_layout.addLayout(self._folder_row)
        self._folder_input.textChanged.connect(self._on_folder_changed)

        self._folder_info = QLabel("No folder selected")
        self._folder_info.setStyleSheet("font-size: 12px; color: " + ('#a1a1aa' if _is_dark() else '#6b7280') + ";")
        left_layout.addWidget(self._folder_info)

        # ── Batch Options (expandable card) ──
        self._options_card = _BatchOptionsCard(self)
        left_layout.addWidget(self._options_card)

        left_layout.addStretch()

        # Buttons
        btn_layout = QVBoxLayout()
        btn_layout.setSpacing(8)

        self._start_btn = QPushButton("Process")
        self._start_btn.setObjectName('primary')
        self._start_btn.setFixedHeight(40)
        self._start_btn.setEnabled(False)
        self._start_btn.clicked.connect(self._on_start)
        btn_layout.addWidget(self._start_btn)

        self._cancel_btn = QPushButton("Cancel")
        self._cancel_btn.setObjectName('danger')
        self._cancel_btn.setFixedHeight(40)
        self._cancel_btn.setEnabled(False)
        self._cancel_btn.clicked.connect(self._on_cancel)
        btn_layout.addWidget(self._cancel_btn)

        left_layout.addLayout(btn_layout)
        layout.addWidget(left)

        # Right panel: results — margins match left card's content area
        right = QVBoxLayout()
        right.setSpacing(12)
        right.setContentsMargins(0, 0, 0, 0)

        # Results table (stretches to fill available height)
        self._results_view = ResultsView(self, self.main_window)
        right.addWidget(self._results_view, 1)

        # Stats card (single row, shown after batch)
        self._stats_card = QFrame()
        self._stats_card.setObjectName('card')
        self._stats_card.setVisible(False)
        stats_layout = QHBoxLayout(self._stats_card)
        stats_layout.setContentsMargins(16, 0, 16, 10)
        stats_layout.setSpacing(24)

        self._stat_items = []
        for label, key in [("Processed", "processed"), ("Total", "total_time"), ("Per File", "avg_time")]:
            col = QVBoxLayout()
            lbl = QLabel(label)
            lbl.setStyleSheet("font-size: 11px; font-weight: 600;")
            col.addWidget(lbl)
            col.setSpacing(2)
            val = QLabel("—")
            val.setStyleSheet("font-size: 14px; font-weight: 700;")
            col.addWidget(val)
            self._stat_items.append((key, val))
            stats_layout.addLayout(col, 0)

        right.addWidget(self._stats_card)
        layout.addLayout(right, 1)

    def _on_browse(self):
        folder = QFileDialog.getExistingDirectory(
            self, "Select Source Folder", "",
            QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks
        )
        if folder:
            self._folder_input.setText(folder)
            self._update_folder_info(folder)

    def _on_folder_changed(self, text):
        is_valid = bool(text.strip() and os.path.isdir(text.strip()))
        self._start_btn.setEnabled(is_valid)
        self._cancel_btn.setEnabled(False)

    def _update_folder_info(self, folder):
        from config.constants import SUPPORTED_EXTENSIONS
        count = 0
        for dirpath, dirnames, filenames in os.walk(folder):
            # Don't descend into hidden dirs, .git, node_modules, etc.
            dirnames[:] = [d for d in dirnames if not d.startswith('.') and d not in ('node_modules', '__pycache__', '.venv')]
            for f in filenames:
                if os.path.splitext(f)[1].lower() in SUPPORTED_EXTENSIONS:
                    count += 1
            # Cap at 1000 to avoid slow scans of huge directories
            if count > 1000:
                self._folder_info.setText("1000+ supported files")
                return
        self._folder_info.setText(f"{count} supported files")

    def _on_start(self):
        folder = self._folder_input.text().strip()
        if not folder:
            self._on_browse()
            folder = self._folder_input.text().strip()
            if not folder:
                return

        if not os.path.isdir(folder):
            return

        self._stats_card.setVisible(False)
        self._start_btn.setEnabled(False)
        self._cancel_btn.setEnabled(True)
        self.start_signal.emit(folder)

    def _on_cancel(self):
        self.cancel_signal.emit()


    def set_processing_state(self, processing):
        if processing:
            self._cancel_btn.setEnabled(True)
            self._start_btn.setEnabled(False)
            self._folder_input.setEnabled(False)
            self._results_view._placeholder.setText("Processing...")
        else:
            self._cancel_btn.setEnabled(False)
            # Re-enable Process if a valid folder is still selected
            folder = self._folder_input.text().strip()
            self._start_btn.setEnabled(bool(folder and os.path.isdir(folder)))
            self._folder_input.setEnabled(True)
            self._results_view._placeholder.setText("Select a folder and click Process to get started.")

    def add_result(self, result):
        self._results_view.add_result(result)

    def display_report(self, report):
        self._stats_card.setVisible(True)
        total = report.successful + report.failed
        self._stat_items[0][1].setText(str(total))
        self._stat_items[1][1].setText(report.format_total_time())
        if report.successful + report.failed > 0:
            m, s = divmod(round(report.avg_time_per_file), 60)
            self._stat_items[2][1].setText(f"{m}m {s}s" if m else f"{s}s")
        self._results_view.display_report(report)


class ResultsView(QWidget):
    """Results table with thumbnail preview and detail panel."""

    def __init__(self, parent, main_window):
        super().__init__(parent)
        self.main_window = main_window
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        # Placeholder
        self._placeholder = QLabel("Select a folder and click Process to get started.")
        self._placeholder.setAlignment(Qt.AlignCenter)
        self._placeholder.setStyleSheet("font-size: 14px; padding: 60px; color: " + ('#71717a' if _is_dark() else '#9ca3af'))
        layout.addWidget(self._placeholder, 1)

        # Table — 2 columns: File (with rerun button), Title
        self._table = QTableWidget()
        self._table.setColumnCount(2)
        self._table.setHorizontalHeaderLabels(["File", "Title"])
        self._table.setFrameShape(QFrame.NoFrame)
        self._table.setCornerButtonEnabled(False)
        header = self._table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self._table.setSelectionBehavior(QTableWidget.SelectRows)
        self._table.setEditTriggers(QTableWidget.NoEditTriggers)
        self._table.verticalHeader().setVisible(False)
        self._table.setAlternatingRowColors(True)
        self._table.setVisible(False)
        self._table.cellDoubleClicked.connect(self._on_double_click)
        layout.addWidget(self._table, 1)
        self._rerun_busy = {}
        self._rerun_worker = None
        self._rerun_thread = None

        # Detail + preview panel
        self._detail = QFrame()
        self._detail.setObjectName('card')
        detail_layout = QHBoxLayout(self._detail)
        detail_layout.setSpacing(16)
        detail_layout.setContentsMargins(16, 10, 16, 10)
        self._detail.setVisible(False)

        # Left: thumbnail
        self._preview_label = QLabel()
        self._preview_label.setAlignment(Qt.AlignCenter)
        self._preview_label.setFixedSize(180, 120)
        dark_bg = '#27272a' if _is_dark() else '#f4f4f5'
        self._preview_label.setStyleSheet(f"background: {dark_bg}; border-radius: 8px;")
        self._preview_label.setVisible(False)
        detail_layout.addWidget(self._preview_label)

        # Right: metadata details
        meta_layout = QVBoxLayout()
        meta_layout.setSpacing(6)

        self._detail_name = QLabel()
        self._detail_name.setStyleSheet("font-weight: 600; font-size: 13px;")
        meta_layout.addWidget(self._detail_name)

        # Content type and category row
        type_cat_row = QHBoxLayout()
        type_cat_row.setSpacing(12)
        self._detail_type = QLabel()
        self._detail_type.setStyleSheet("font-size: 11px; font-weight: 600; padding: 2px 8px; background: rgba(99, 102, 241, 0.15); border-radius: 4px;")
        type_cat_row.addWidget(self._detail_type)
        self._detail_category = QLabel()
        self._detail_category.setStyleSheet("font-size: 11px; color: " + ('#a1a1aa' if _is_dark() else '#6b7280'))
        type_cat_row.addWidget(self._detail_category)
        type_cat_row.addStretch()
        meta_layout.addLayout(type_cat_row)

        # Title row with copy button
        title_row = QHBoxLayout()
        title_row.setSpacing(6)
        self._detail_title = QLabel()
        self._detail_title.setWordWrap(True)
        self._detail_title.setTextInteractionFlags(
            Qt.TextSelectableByMouse | Qt.TextSelectableByKeyboard
        )
        title_row.addWidget(self._detail_title, 1)
        self._copy_title_btn = QPushButton()
        self._copy_title_btn.setIcon(self._copy_icon_svg())
        self._copy_title_btn.setFixedSize(28, 28)
        self._copy_title_btn.setToolTip("Copy title")
        title_row.addWidget(self._copy_title_btn)
        meta_layout.addLayout(title_row)

        # Keywords row with copy button
        self._detail_kw_label = QLabel("Keywords")
        self._detail_kw_label.setStyleSheet("font-size: 11px; font-weight: 600; color: " + ('#a1a1aa' if _is_dark() else '#6b7280'))
        meta_layout.addWidget(self._detail_kw_label)

        kw_row = QHBoxLayout()
        kw_row.setSpacing(6)
        self._detail_keywords = QLabel()
        self._detail_keywords.setWordWrap(True)
        self._detail_keywords.setStyleSheet("font-size: 12px;")
        self._detail_keywords.setTextInteractionFlags(
            Qt.TextSelectableByMouse | Qt.TextSelectableByKeyboard
        )
        kw_row.addWidget(self._detail_keywords, 1)
        self._copy_kw_btn = QPushButton()
        self._copy_kw_btn.setIcon(self._copy_icon_svg())
        self._copy_kw_btn.setFixedSize(28, 28)
        self._copy_kw_btn.setToolTip("Copy keywords")
        kw_row.addWidget(self._copy_kw_btn)
        meta_layout.addLayout(kw_row)

        detail_layout.addLayout(meta_layout, 1)
        layout.addWidget(self._detail)

        self._results = []
        self._file_paths = []
        self._current_result = None
        self._row_spinning = {}  # row -> QTimer
        self._copy_title_btn.clicked.connect(self._copy_selected_title)
        self._copy_kw_btn.clicked.connect(self._copy_selected_keywords)
        self._table.itemSelectionChanged.connect(self._on_selection)

    @staticmethod
    def _rerun_icon_svg():
        from PySide6.QtGui import QPainter
        from PySide6.QtSvg import QSvgRenderer
        from PySide6.QtCore import QByteArray, QSize
        stroke = '#a1a1aa' if _is_dark() else '#374151'
        svg = (
            f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="{stroke}" '
            'stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
            '<path d="M21 2v6h-6"/>'
            '<path d="M3 12a9 9 0 0 1 15-6.7L21 8"/>'
            '<path d="M3 22v-6h6"/>'
            '<path d="M21 12a9 9 0 0 1-15 6.7L3 16"/>'
            '</svg>'
        )
        renderer = QSvgRenderer(QByteArray(svg.encode()))
        img = QImage(24, 24, QImage.Format.Format_ARGB32)
        img.fill(0)
        painter = QPainter(img)
        renderer.render(painter)
        painter.end()
        return QIcon(QPixmap.fromImage(img))

    @staticmethod
    def _copy_icon_svg():
        from PySide6.QtGui import QPainter
        from PySide6.QtSvg import QSvgRenderer
        from PySide6.QtCore import QByteArray, QSize
        svg = (
            '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="black" '
            'stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
            '<rect x="9" y="9" width="13" height="13" rx="2" ry="2"/>'
            '<path d="M5 15H4a2 2 0 01-2-2V4a2 2 0 012-2h9a2 2 0 012 2v1"/>'
            '</svg>'
        )
        renderer = QSvgRenderer(QByteArray(svg.encode()))
        img = QImage(24, 24, QImage.Format.Format_ARGB32)
        img.fill(0)
        painter = QPainter(img)
        renderer.render(painter)
        painter.end()
        return QIcon(QPixmap.fromImage(img))

    def _create_row(self, file_path, title='', show_spinner=False, spinner_frames=0):
        """Create a table row with file label, spinner, and rerun button."""
        from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton
        row = self._table.rowCount()
        self._table.insertRow(row)

        # File name with rerun button in a container
        file_container = QWidget()
        main_layout = QVBoxLayout(file_container)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        top_layout = QHBoxLayout()
        top_layout.setSpacing(6)
        file_label = QLabel(os.path.basename(file_path))
        file_label.setStyleSheet("font-size: 13px;")
        top_layout.addWidget(file_label, 1)
        # Spinner label (hidden until processing)
        spinner_label = QLabel()
        spinner_label.setFixedSize(16, 16)
        spinner_label.setAlignment(Qt.AlignCenter)
        spinner_label.setStyleSheet("color: #3b82f6; font-size: 14px; font-weight: bold;")
        spinner_label.setVisible(False)
        top_layout.addWidget(spinner_label)
        rerun_btn = QPushButton()
        rerun_btn.setIcon(self._rerun_icon_svg())
        rerun_btn.setIconSize(QSize(12, 12))
        rerun_btn.setFixedSize(16, 16)
        rerun_btn.setToolTip("Regenerate vision + text for this file")
        rerun_btn.clicked.connect(lambda checked, r=row: self._on_rerun_row(r))
        top_layout.addWidget(rerun_btn)
        main_layout.addLayout(top_layout)

        # Store refs for animation
        file_container.setProperty('spinner_label', spinner_label)
        file_container.setProperty('rerun_btn', rerun_btn)
        file_container.setProperty('file_path', file_path)
        self._table.setCellWidget(row, 0, file_container)
        hidden_item = QTableWidgetItem("")
        hidden_item.setData(Qt.UserRole, file_path)
        self._table.setItem(row, 0, hidden_item)

        title_text = title[:80] + ('…' if len(title) > 80 else '')
        self._table.setItem(row, 1, QTableWidgetItem(title_text))

        if show_spinner:
            spinner_label.setVisible(True)
            spinner_label.setText(spinner_frames[spinner_label] if spinner_frames else '⠋')

        return row

    def add_pending_file(self, file_info):
        """Add a row for a file waiting to be processed."""
        self._placeholder.setVisible(False)
        self._table.setVisible(True)
        row = self._create_row(file_info.path)
        # Hide rerun button until file is processed
        container = self._table.cellWidget(row, 0)
        if container:
            btn = container.property('rerun_btn')
            if btn:
                btn.hide()
        self._results.append(None)  # placeholder for result
        self._file_paths.append(file_info.path)
        self._row_spinning[row] = False  # track spinner state

    def start_spinner(self, file_path):
        """Start spinner animation for a file that is being processed."""
        for i, fp in enumerate(self._file_paths):
            if fp == file_path:
                container = self._table.cellWidget(i, 0)
                if container:
                    spinner = container.property('spinner_label')
                    btn = container.property('rerun_btn')
                    if spinner:
                        spinner.show()
                        spinner.setText('⠋')
                    if btn:
                        btn.hide()
                    # Start spinner animation timer
                    timer = QTimer(self)
                    frames = ['⠋', '⠙', '⠹', '⠸', '⠼', '⠴', '⠦', '⠧', '⠇', '⠏']
                    frame_idx = [0]
                    # Capture i in closure correctly
                    row_capture = i
                    timer.timeout.connect(lambda: self._cycle_spinner(row_capture, frames, frame_idx))
                    timer.start(80)
                    self._row_spinning[i] = timer
                return

    def stop_all_spinners(self):
        """Stop all spinning timers and hide spinners (called on batch end/cancel)."""
        # Stop batch processing spinners
        for row, timer in self._row_spinning.items():
            if isinstance(timer, QTimer):
                try:
                    timer.stop()
                    timer.deleteLater()
                except Exception:
                    pass
            container = self._table.cellWidget(row, 0)
            if container:
                try:
                    spinner = container.property('spinner_label')
                    if spinner:
                        spinner.hide()
                except Exception:
                    pass
                try:
                    btn = container.property('rerun_btn')
                    if btn:
                        btn.show()
                except Exception:
                    pass
        self._row_spinning.clear()
        # Stop rerun spinners
        for row, busy in list(self._rerun_busy.items()):
            if isinstance(busy, dict) and 'timer' in busy:
                timer = busy['timer']
                try:
                    timer.stop()
                    timer.deleteLater()
                except Exception:
                    pass
            container = self._table.cellWidget(row, 0)
            if container:
                try:
                    spinner = container.property('spinner_label')
                    if spinner:
                        spinner.hide()
                except Exception:
                    pass
                try:
                    btn = container.property('rerun_btn')
                    if btn:
                        btn.show()
                except Exception:
                    pass
        self._rerun_busy.clear()

    def _cycle_spinner(self, row, frames, frame_idx):
        """Cycle through spinner frames for a given row."""
        try:
            container = self._table.cellWidget(row, 0)
            if not container:
                return
            spinner = container.property('spinner_label')
            if spinner and spinner.isVisible():
                frame_idx[0] = (frame_idx[0] + 1) % len(frames)
                spinner.setText(frames[frame_idx[0]])
        except RuntimeError:
            # Widget already deleted, do nothing
            pass

    def add_result(self, result):
        """Add or update a row when processing a file completes."""
        self._placeholder.setVisible(False)
        self._table.setVisible(True)
        # Check if this file already has a row (from pre-population)
        for i, fp in enumerate(self._file_paths):
            if fp == result.file_path:
                # Stop spinner timer
                timer = self._row_spinning.pop(i, None)
                if isinstance(timer, QTimer):
                    timer.stop()
                    timer.deleteLater()
                # Update existing row
                container = self._table.cellWidget(i, 0)
                if container:
                    spinner = container.property('spinner_label')
                    btn = container.property('rerun_btn')
                    if spinner:
                        spinner.hide()
                    if btn:
                        btn.show()
                    # Show rerun button now that file is processed
                    if btn:
                        btn.show()
                title_text = result.title[:80] + ('…' if len(result.title) > 80 else '')
                self._table.setItem(i, 1, QTableWidgetItem(title_text))
                self._results[i] = result
                # If this row is currently selected, refresh detail panel + thumbnail
                selected = self._table.selectedItems()
                if selected and selected[0].row() == i:
                    self._current_result = result
                    self._detail_name.setText(os.path.basename(result.file_path))
                    self._detail_type.setText(getattr(result, 'content_type', 'Commercial') or 'Commercial')
                    self._detail_category.setText(getattr(result, 'category', '') or '—')
                    self._detail_title.setText(result.title)
                    self._detail_keywords.setText(', '.join(result.keywords))
                    # Refresh thumbnail
                    QTimer.singleShot(50, lambda: self._load_thumbnail(result.file_path))
                return

        # New row (shouldn't happen with pre-population, but keep as fallback)
        row = self._create_row(result.file_path, result.title)
        self._results.append(result)
        self._file_paths.append(result.file_path)

        # File name with rerun button in a container
        file_container = QWidget()
        main_layout = QVBoxLayout(file_container)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        top_layout = QHBoxLayout()
        top_layout.setSpacing(6)
        file_label = QLabel(os.path.basename(result.file_path))
        file_label.setStyleSheet("font-size: 13px;")
        top_layout.addWidget(file_label, 1)
        # Spinner label (hidden until processing)
        spinner_label = QLabel()
        spinner_label.setFixedSize(16, 16)
        spinner_label.setAlignment(Qt.AlignCenter)
        spinner_label.setStyleSheet("color: #3b82f6; font-size: 14px; font-weight: bold;")
        spinner_label.setVisible(False)
        top_layout.addWidget(spinner_label)
        rerun_btn = QPushButton()
        rerun_btn.setIcon(self._rerun_icon_svg())
        rerun_btn.setIconSize(QSize(12, 12))
        rerun_btn.setFixedSize(16, 16)
        rerun_btn.setToolTip("Regenerate vision + text for this file")
        rerun_btn.clicked.connect(lambda checked, r=row: self._on_rerun_row(r))
        top_layout.addWidget(rerun_btn)
        main_layout.addLayout(top_layout)

        # Store refs for animation
        file_container.setProperty('spinner_label', spinner_label)
        file_container.setProperty('rerun_btn', rerun_btn)
        file_container.setProperty('file_path', result.file_path)
        self._table.setCellWidget(row, 0, file_container)
        hidden_item = QTableWidgetItem("")
        hidden_item.setData(Qt.UserRole, result.file_path)
        self._table.setItem(row, 0, hidden_item)

        title_text = result.title[:80] + ('…' if len(result.title) > 80 else '')
        self._table.setItem(row, 1, QTableWidgetItem(title_text))

        self._results.append(result)
        self._file_paths.append(result.file_path)

    def _on_selection(self):
        selected = self._table.selectedItems()
        if not selected:
            return

        row = selected[0].row()
        if row < 0 or row >= len(self._results):
            return

        result = self._results[row]
        file_path = self._file_paths[row]
        self._detail.setVisible(True)
        self._preview_label.setVisible(True)

        self._detail_name.setText(os.path.basename(file_path))

        if result is None:
            # File not yet processed
            self._detail_type.setText('Queued')
            self._detail_category.setText('—')
            self._detail_title.setText('Waiting for processing...')
            self._detail_keywords.setText('')
            self._current_result = None
            self._show_no_preview()
            return

        self._detail_type.setText(getattr(result, 'content_type', 'Commercial') or 'Commercial')
        self._detail_category.setText(getattr(result, 'category', '') or '—')
        self._detail_title.setText(result.title)

        if self._current_result is result:
            return
        self._current_result = result
        # Show all keywords comma-separated
        self._detail_keywords.setText(', '.join(result.keywords))

        # Load thumbnail in background to avoid UI freeze
        QTimer.singleShot(50, lambda: self._load_thumbnail(file_path))

    def _copy_selected_title(self):
        from PySide6.QtWidgets import QApplication
        if self._current_result and self._current_result.title:
            QApplication.clipboard().setText(self._current_result.title)

    def _copy_selected_keywords(self):
        from PySide6.QtWidgets import QApplication
        if self._current_result and self._current_result.keywords:
            QApplication.clipboard().setText(', '.join(self._current_result.keywords))

    def _copy_to_clipboard(self, text):
        from PySide6.QtWidgets import QApplication
        QApplication.clipboard().setText(text)

    def _on_rerun_row(self, row):
        """Rerun vision and text generation for a specific row."""
        if row < 0 or row >= len(self._results):
            return
        if self._rerun_busy.get(row):
            return
        self._rerun_busy[row] = True
        result = self._results[row]
        vision = getattr(result, 'vision_analysis', None)
        if not vision:
            self._rerun_busy[row] = False
            return
        # Hide button, show spinner, start animation
        container = self._table.cellWidget(row, 0)
        if container:
            btn = container.property('rerun_btn')
            spinner = container.property('spinner_label')
            if btn:
                btn.hide()
            if spinner:
                spinner.show()
        # Store refs for animation
        self._rerun_busy[row] = {'spinner': container.property('spinner_label'), 'frame': 0}
        # Start spin timer: cycle spinner frames every 80ms
        timer = QTimer(self)
        timer.timeout.connect(lambda: self._spin_rerun_icon(row))
        timer.start(80)
        self._rerun_busy[row]['timer'] = timer
        # Run in background thread using QRunnable (Qt-native, safe lifecycle)
        from PySide6.QtCore import QRunnable, QThreadPool
        runnable = _RerunRunnable(
            self.main_window._orchestrator,
            result.file_path,
            vision,
            self.main_window._process_panel._options_card.get_content_type_override(),
            self, row,
        )
        runnable.setAutoDelete(True)
        QThreadPool.globalInstance().start(runnable)

    def _spin_rerun_icon(self, row):
        """Cycle spinner frames for a spinning animation."""
        busy = self._rerun_busy.get(row)
        if not busy or 'spinner' not in busy:
            return
        spinner = busy['spinner']
        if not spinner:
            return
        try:
            frames = ['⠋', '⠙', '⠹', '⠸', '⠼', '⠴', '⠦', '⠧', '⠇', '⠏']
            busy['frame'] = (busy['frame'] + 1) % len(frames)
            spinner.setText(frames[busy['frame']])
        except RuntimeError:
            # Widget already deleted, stop the timer
            if 'timer' in busy:
                timer = busy['timer']
                try:
                    timer.stop()
                    timer.deleteLater()
                except Exception:
                    pass
            self._rerun_busy.pop(row, None)

    def _on_rerun_finished(self, result, row):
        """Handle rerun completion: update table, detail, CSV, and re-embed metadata."""
        if not result:
            return
        # Stop spinning timer, hide spinner, show button
        busy = self._rerun_busy.pop(row, None)
        if busy and 'timer' in busy:
            timer = busy['timer']
            timer.stop()
            timer.deleteLater()
        container = self._table.cellWidget(row, 0)
        if container:
            spinner = container.property('spinner_label')
            btn = container.property('rerun_btn')
            if spinner:
                spinner.hide()
                spinner.setText('')
            if btn:
                btn.show()
        # Update the result in the list
        self._results[row] = result
        # Update table row - update file name label and title
        container = self._table.cellWidget(row, 0)
        if container:
            for i in range(container.layout().count()):
                w = container.layout().itemAt(i).widget()
                if isinstance(w, QLabel):
                    w.setText(os.path.basename(result.file_path))
        title_text = result.title[:80] + ('…' if len(result.title) > 80 else '')
        self._table.setItem(row, 1, QTableWidgetItem(title_text))
        # Update detail panel if this row is currently selected
        selected = self._table.selectedItems()
        if selected and selected[0].row() == row:
            self._current_result = result
            self._detail_name.setText(os.path.basename(result.file_path))
            self._detail_type.setText(getattr(result, 'content_type', 'Commercial') or 'Commercial')
            self._detail_category.setText(getattr(result, 'category', '') or '—')
            self._detail_title.setText(result.title)
            self._detail_keywords.setText(', '.join(result.keywords))
        # Re-export CSV if it exists
        self._update_csv()

    def _update_csv(self):
        """Update the CSV export with all current results."""
        if not hasattr(self.main_window, '_current_folder'):
            return
        if not self.main_window._process_panel._options_card.get_export_csv():
            return
        if not self._results:
            return
        from export.csv import CsvExporter
        exporter = CsvExporter()
        csv_path = os.path.join(self.main_window._current_folder, 'metadata_export.csv')
        # Filter out None (unprocessed) results
        exporter.export_batch([r for r in self._results if r is not None], csv_path)

    def _on_double_click(self, row, col):
        if col != 0:
            return
        if row < 0 or row >= len(self._file_paths):
            return
        # Get file path from the hidden item in the file column
        hidden_item = self._table.item(row, 0)
        if hidden_item:
            file_path = hidden_item.data(Qt.UserRole)
        else:
            file_path = self._file_paths[row]
        if not file_path or not os.path.exists(file_path):
            return
        # Open file with default application
        try:
            import subprocess
            if os.name == 'nt':
                # 'start' command with empty string before path handles spaces correctly
                subprocess.Popen(['start', '', file_path], shell=True)
            else:
                subprocess.Popen(['open', file_path])
        except Exception:
            pass

    def _load_thumbnail(self, file_path):
        if not os.path.exists(file_path):
            self._show_no_preview("File not found")
            return

        ext = os.path.splitext(file_path)[1].lower()
        if ext in ('.mp4', '.mov', '.avi', '.mkv', '.webm', '.m4v', '.wmv'):
            self._load_video_thumbnail(file_path)
        else:
            self._load_image_thumbnail(file_path)

    def _show_no_preview(self, reason="No preview"):
        self._preview_label.setPixmap(QPixmap())
        self._preview_label.setText(reason)
        self._preview_label.setStyleSheet(
            self._preview_label.styleSheet().rsplit(';')[-1] +
            "color: #71717a; font-size: 11px;"
        )

    def _load_image_thumbnail(self, file_path):
        # Try QPixmap first
        try:
            pixmap = QPixmap(file_path)
            if not pixmap.isNull():
                scaled = pixmap.scaled(160, 100, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                self._preview_label.setPixmap(scaled)
                return
        except Exception:
            pass

        # Fallback: use PIL to resize then convert to QPixmap
        try:
            from PIL import Image
            from io import BytesIO
            img = Image.open(file_path)
            img.thumbnail((256, 256))
            buf = BytesIO()
            img.save(buf, format='JPEG', quality=60)
            buf.seek(0)
            pixmap = QPixmap()
            pixmap.loadFromData(buf.getvalue(), 'JPEG')
            if not pixmap.isNull():
                scaled = pixmap.scaled(160, 100, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                self._preview_label.setPixmap(scaled)
                return
        except Exception:
            pass

        self._show_no_preview("Preview error")

    def _load_video_thumbnail(self, file_path):
        try:
            from core.video.extractor import VideoFrameExtractor
            extractor = VideoFrameExtractor()
            thumb_data = extractor.extract_thumbnail(file_path, max_size=256)
            if thumb_data:
                img = QImage.fromData(thumb_data)
                if not img.isNull():
                    pixmap = QPixmap.fromImage(img)
                    scaled = pixmap.scaled(160, 100, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                    self._preview_label.setPixmap(scaled)
                    return
        except Exception:
            pass
        self._show_no_preview("Video preview error")

    def display_report(self, report):
        pass


class _ExpandableHeader(QFrame):
    """Clickable header row for an expandable card."""

    toggled = Signal(bool)

    def __init__(self, text, parent=None):
        super().__init__(parent)
        self._expanded = False
        self._text = text
        self.setFixedHeight(32)
        self.setCursor(Qt.PointingHandCursor)
        self.setStyleSheet("""
            _ExpandableHeader {
                background: transparent;
                border: none;
            }
        """)

    @property
    def expanded(self):
        return self._expanded

    def paintEvent(self, event):
        painter = QPainter(self)
        try:
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            text_color = '#e4e4e7' if _is_dark() else '#3f3f46'
            arrow_color = '#a1a1aa' if _is_dark() else '#71717a'

            # Chevron arrow
            painter.setPen(arrow_color)
            painter.setBrush(arrow_color)
            cx = 14
            cy = 16
            if self._expanded:
                painter.drawLine(cx - 5, cy - 4, cx, cy + 2)
                painter.drawLine(cx, cy + 2, cx + 5, cy - 4)
            else:
                painter.drawLine(cx - 5, cy - 4, cx, cy + 2)
                painter.drawLine(cx, cy + 2, cx - 5, cy + 8)

            # Text
            painter.setPen(text_color)
            font = QFont('Helvetica Neue' if sys.platform == 'darwin' else 'Segoe UI', 12, QFont.Weight.Bold)
            painter.setFont(font)
            painter.drawText(QRect(28, 0, self.width(), 32), Qt.AlignVCenter, self._text)
        finally:
            painter.end()

    def mousePressEvent(self, event):
        self._expanded = not self._expanded
        self.update()
        self.toggled.emit(self._expanded)
        super().mousePressEvent(event)


class _BatchOptionsCard(QFrame):
    """Expandable card with batch-level options."""

    def __init__(self, parent):
        super().__init__(parent)
        self.setObjectName('card')
        self._parent = parent
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._header = _ExpandableHeader('Batch Options')
        self._header.toggled.connect(self._on_toggle)
        layout.addWidget(self._header)

        # Collapsible content
        self._content = QFrame()
        self._content_layout = QVBoxLayout(self._content)
        self._content_layout.setContentsMargins(16, 8, 16, 14)
        self._content_layout.setSpacing(12)

        # Content Type Override
        ct_row = QHBoxLayout()
        ct_row.setSpacing(10)
        ct_label = QLabel('Content Type')
        ct_label.setStyleSheet('font-size: 12px; font-weight: 600;')
        ct_row.addWidget(ct_label, 0)
        ct_row.addStretch()
        self._content_type_combo = QComboBox()
        self._content_type_combo.addItems(['Auto (Detect)', 'Force Editorial', 'Force Commercial'])
        self._content_type_combo.setCurrentIndex(0)
        self._content_type_combo.setStyleSheet('''
            QComboBox {
                font-size: 12px;
                padding: 4px 8px;
                border-radius: 6px;
            }
        ''')
        ct_row.addWidget(self._content_type_combo, 0)
        self._content_layout.addLayout(ct_row)

        # Export CSV checkbox
        self._export_csv_cb = QCheckBox("Export CSV after batch")
        self._export_csv_cb.setChecked(True)
        self._export_csv_cb.setStyleSheet('font-size: 12px;')
        self._content_layout.addWidget(self._export_csv_cb)

        layout.addWidget(self._content)
        self._content.setVisible(False)

    def _on_toggle(self):
        self._content.setVisible(self._header.expanded)

    def get_export_csv(self) -> bool:
        return self._export_csv_cb.isChecked()

    def get_content_type_override(self) -> str:
        """Return 'editorial', 'commercial', or '' (auto)."""
        idx = self._content_type_combo.currentIndex()
        if idx == 1:
            return 'editorial'
        elif idx == 2:
            return 'commercial'
        return ''


def _is_dark():
    try:
        from PySide6.QtWidgets import QApplication
        from PySide6.QtGui import QPalette
        p = QApplication.palette()
        return p.color(QPalette.ColorRole.Window).lightness() < 128
    except Exception:
        return False


class _BatchWorker(QObject):
    """Background worker for batch processing."""
    finished = Signal(BatchReport)
    error = Signal(str)

    def __init__(self, orchestrator, folder_path):
        super().__init__()
        self.orchestrator = orchestrator
        self.folder_path = folder_path

    def run(self):
        try:
            report = self.orchestrator.run(self.folder_path)
            self.finished.emit(report)
        except Exception as e:
            self.error.emit(str(e))


class _RerunWorker(QObject):
    """Background worker for rerunning vision + text on a single file."""
    finished = Signal(object)  # FileResult
    progress = Signal(int)  # 0-100

    def __init__(self, orchestrator, file_path, vision_analysis, content_type_override):
        super().__init__()
        self.orchestrator = orchestrator
        self.file_path = file_path
        self.vision_analysis = vision_analysis
        self.content_type_override = content_type_override

    def run(self):
        result = self.orchestrator.rerun_file(
            self.file_path, self.vision_analysis, self.content_type_override,
            progress_callback=self.progress.emit
        )
        self.finished.emit(result)


class _RerunSignalEmitter(QObject):
    """Signal emitter for rerun results (lives on main thread)."""
    finished = Signal(object, int)  # result, row


class _RerunRunnable(QRunnable):
    """Qt-native rerun worker using QThreadPool."""

    def __init__(self, orchestrator, file_path, vision_analysis, content_type_override,
                 results_view, row):
        super().__init__()
        self.orchestrator = orchestrator
        self.file_path = file_path
        self.vision_analysis = vision_analysis
        self.content_type_override = content_type_override
        self.results_view = results_view
        self.row = row
        # Signal emitter lives on main thread, safe to emit from worker
        self.emitter = _RerunSignalEmitter()
        self.emitter.finished.connect(self.results_view._on_rerun_finished)

    def run(self):
        try:
            result = self.orchestrator.rerun_file(
                self.file_path, self.vision_analysis, self.content_type_override
            )
            self.emitter.finished.emit(result, self.row)
        except Exception as e:
            import logging
            logging.getLogger(__name__).error(f"Rerun failed: {e}", exc_info=True)
