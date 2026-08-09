"""Batch processing panel with folder selection and controls."""

import os

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QLabel, QLineEdit, QFileDialog, QProgressBar, QFrame,
    QComboBox, QSpinBox
)
from PySide6.QtCore import Qt, Signal


class BatchPanel(QWidget):
    """Main panel for selecting folders and starting batch processing."""

    start_signal = Signal(str)  # folder_path
    cancel_signal = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        # Folder selection
        folder_group = self._create_folder_group()
        layout.addWidget(folder_group)

        # Options
        options_group = self._create_options_group()
        layout.addWidget(options_group)

        # Controls
        control_layout = QHBoxLayout()
        self._start_btn = QPushButton("Run Batch Processing")
        self._start_btn.setObjectName('primaryButton')
        self._start_btn.setStyleSheet("""
            QPushButton#primaryButton {
                background-color: #2563eb;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 10px 24px;
                font-weight: bold;
                font-size: 14px;
            }
            QPushButton#primaryButton:hover {
                background-color: #1d4ed8;
            }
            QPushButton#primaryButton:disabled {
                background-color: #93c5fd;
            }
        """)
        self._start_btn.clicked.connect(self._on_start)
        control_layout.addWidget(self._start_btn)

        self._cancel_btn = QPushButton("Cancel")
        self._cancel_btn.setEnabled(False)
        self._cancel_btn.clicked.connect(self._on_cancel)
        control_layout.addWidget(self._cancel_btn)
        control_layout.addStretch()

        # Workers display
        self._workers_label = QLabel("Workers: 4")
        control_layout.addWidget(self._workers_label)

        layout.addLayout(control_layout)
        layout.addStretch()

    def _create_folder_group(self) -> QFrame:
        """Create the folder selection group."""
        frame = QFrame()
        frame.setFrameStyle(QFrame.StyledPanel)
        layout = QVBoxLayout(frame)

        label = QLabel("Source Folder")
        label.setStyleSheet("font-weight: bold; font-size: 13px;")
        layout.addWidget(label)

        input_layout = QHBoxLayout()
        self._folder_input = QLineEdit()
        self._folder_input.setPlaceholderText("Select a folder containing photos and videos...")
        self._folder_input.setMinimumHeight(36)
        input_layout.addWidget(self._folder_input)

        browse_btn = QPushButton("Browse...")
        browse_btn.setMinimumHeight(36)
        browse_btn.clicked.connect(self._on_browse)
        input_layout.addWidget(browse_btn)

        layout.addLayout(input_layout)

        # Folder info
        self._folder_info = QLabel("No folder selected")
        self._folder_info.setStyleSheet("font-size: 12px;")
        layout.addWidget(self._folder_info)

        return frame

    def _create_options_group(self) -> QFrame:
        """Create processing options group."""
        frame = QFrame()
        frame.setFrameStyle(QFrame.StyledPanel)
        layout = QHBoxLayout(frame)

        # Workers
        layout.addWidget(QLabel("Max Workers:"))
        self._workers_spin = QSpinBox()
        self._workers_spin.setRange(1, 16)
        self._workers_spin.setValue(getattr(parent, 'settings', None).max_workers if parent else 1)
        self._workers_spin.valueChanged.connect(self._on_workers_changed)
        layout.addWidget(self._workers_spin)

        layout.addStretch()

        # Output format
        layout.addWidget(QLabel("Output:"))
        self._format_combo = QComboBox()
        self._format_combo.addItems(["Embedded (IPTC/XMP)", "XMP Sidecar", "Both"])
        self._format_combo.currentIndexChanged.connect(self._on_format_changed)
        layout.addWidget(self._format_combo)

        return frame

    def _on_browse(self) -> None:
        """Open folder browser dialog."""
        folder = QFileDialog.getExistingDirectory(
            self, "Select Source Folder", "",
            QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks
        )
        if folder:
            self._folder_input.setText(folder)
            self._update_folder_info(folder)
            return folder
        return None

    def _update_folder_info(self, folder: str) -> None:
        """Update folder info label with file counts."""
        import os
        from config.constants import SUPPORTED_EXTENSIONS

        count = 0
        for dirpath, dirnames, filenames in os.walk(folder):
            dirnames[:] = [d for d in dirnames if not d.startswith('.') and d not in ('node_modules', '__pycache__', '.venv')]
            for f in filenames:
                ext = os.path.splitext(f)[1].lower()
                if ext in SUPPORTED_EXTENSIONS:
                    count += 1
            if count > 1000:
                self._folder_info.setText("1000+ supported files")
                return

        self._folder_info.setText(f"Found {count} supported files")

    def _on_start(self) -> None:
        """Start batch processing."""
        import os

        folder = self._folder_input.text().strip()
        if not folder:
            folder = self._on_browse()
            if not folder:
                return

        if not os.path.isdir(folder):
            return

        from config.settings import Settings
        settings = Settings()
        settings.set('max_workers', self._workers_spin.value())
        fmt_idx = self._format_combo.currentIndex()
        settings.set('output_format', ['embedded', 'sidecar', 'both'][fmt_idx])
        settings.save()

        self._start_btn.setEnabled(False)
        self._cancel_btn.setEnabled(True)
        self.start_signal.emit(folder)

    def _on_cancel(self) -> None:
        """Emit cancel signal."""
        self.cancel_signal.emit()

    def _on_workers_changed(self, value: int) -> None:
        self._workers_label.setText(f"Workers: {value}")

    def _on_format_changed(self, index: int) -> None:
        pass  # Just stores for later

    def set_processing_state(self, is_processing: bool) -> None:
        """Enable/disable controls during processing."""
        self._start_btn.setEnabled(not is_processing)
        self._cancel_btn.setEnabled(is_processing)
        self._folder_input.setEnabled(not is_processing)
        self._workers_spin.setEnabled(not is_processing)
        self._format_combo.setEnabled(not is_processing)
