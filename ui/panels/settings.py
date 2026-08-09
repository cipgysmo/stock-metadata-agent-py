"""Settings panel for configuring AI endpoints and preferences."""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QLineEdit, QPushButton, QFormLayout, QGroupBox,
    QMessageBox, QSpinBox, QCheckBox, QComboBox, QFrame
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QWheelEvent
from config.settings import Settings
from config.constants import DEFAULT_SETTINGS


class _WheelSpinBox(QLineEdit):
    """QLineEdit that increments/decrements on mouse wheel."""

    def wheelEvent(self, event: QWheelEvent) -> None:
        try:
            val = int(self.text())
        except ValueError:
            val = 10
        if event.angleDelta().y() > 0:
            val = min(val + 1, 50)
        else:
            val = max(val - 1, 1)
        self.setText(str(val))
        event.accept()


class SettingsPanel(QWidget):
    """Settings configuration panel."""

    settings_saved = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.main_window = parent
        self.settings = Settings()
        self._setup_ui()
        self._load_settings()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(8, 12, 8, 12)

        # Vision model
        layout.addWidget(self._section("Vision Model", self._vision_fields()))

        # Reuse for text model checkbox + conditional fields
        self._reuse_text_cb = QCheckBox("Use same settings for text model")
        self._reuse_text_cb.setChecked(True)
        self._reuse_text_cb.stateChanged.connect(self._on_text_toggle)
        layout.addWidget(self._reuse_text_cb)

        # Text model section — hidden by default
        self._text_section = self._section("Text Model", self._text_fields())
        self._text_section.setVisible(False)
        layout.addWidget(self._text_section)

        # Cloud text fallback
        layout.addWidget(self._section("Cloud Text Fallback", self._cloud_text_fields()))

        # Processing
        layout.addWidget(self._section("Processing", self._processing_fields()))

        # Connection status feedback
        self._test_results = QLabel("")
        self._test_results.setWordWrap(True)
        self._test_results.setStyleSheet("font-size: 12px; padding: 4px 0;")
        layout.addWidget(self._test_results)

        # Buttons pinned to bottom with stretch above
        layout.addStretch()
        btn_row = QHBoxLayout()
        btn_row.addStretch()

        self._save_btn = QPushButton("Save")
        self._save_btn.setObjectName('primary')
        self._save_btn.clicked.connect(self._on_save)
        btn_row.addWidget(self._save_btn)

        layout.addLayout(btn_row)

    def _section(self, title, widgets):
        """Create a card section with a title."""
        card = QFrame()
        card.setObjectName('card')
        layout = QVBoxLayout(card)
        layout.setSpacing(8)
        layout.setContentsMargins(16, 14, 16, 14)

        hdr = QLabel(title)
        hdr.setStyleSheet("font-weight: 600; font-size: 13px;")
        layout.addWidget(hdr)

        for w in widgets:
            if isinstance(w, (QHBoxLayout, QVBoxLayout, QFormLayout)):
                layout.addLayout(w)
            else:
                layout.addWidget(w)

        return card

    def _vision_fields(self):
        fields = []

        row = QHBoxLayout()
        row.addWidget(QLabel("Endpoint"), 0)
        self._vision_endpoint = QLineEdit()
        self._vision_endpoint.setPlaceholderText("http://127.0.0.1:8000")
        row.addWidget(self._vision_endpoint, 1)
        fields.append(row)

        row = QHBoxLayout()
        row.addWidget(QLabel("API Key"), 0)
        self._vision_api_key = QLineEdit()
        self._vision_api_key.setPlaceholderText("API key")
        self._vision_api_key.setEchoMode(QLineEdit.Password)
        row.addWidget(self._vision_api_key, 1)
        self._connect_btn = QPushButton()
        self._connect_btn.setIcon(self._link_icon())
        self._connect_btn.setFixedSize(28, 28)
        self._connect_btn.setToolTip("Connect & fetch models")
        self._connect_btn.clicked.connect(self._connect_and_fetch)
        row.addWidget(self._connect_btn)
        fields.append(row)

        self._vision_model_row = QHBoxLayout()
        self._vision_model_row.addWidget(QLabel("Model"), 0)
        self._vision_model = QLineEdit()
        self._vision_model.setPlaceholderText("connect first")
        self._vision_model.setEnabled(False)
        self._vision_model_row.addWidget(self._vision_model, 1)
        fields.append(self._vision_model_row)

        return fields

    def _text_fields(self):
        fields = []

        row = QHBoxLayout()
        row.addWidget(QLabel("Endpoint"), 0)
        self._text_endpoint = QLineEdit()
        self._text_endpoint.setPlaceholderText("http://127.0.0.1:8000")
        row.addWidget(self._text_endpoint, 1)
        fields.append(row)

        row = QHBoxLayout()
        row.addWidget(QLabel("API Key"), 0)
        self._text_api_key = QLineEdit()
        self._text_api_key.setPlaceholderText("API key")
        self._text_api_key.setEchoMode(QLineEdit.Password)
        row.addWidget(self._text_api_key, 1)
        self._text_connect_btn = QPushButton()
        self._text_connect_btn.setIcon(self._link_icon())
        self._text_connect_btn.setFixedSize(28, 28)
        self._text_connect_btn.setToolTip("Connect & fetch models")
        self._text_connect_btn.clicked.connect(self._text_connect_and_fetch)
        row.addWidget(self._text_connect_btn)
        fields.append(row)

        self._text_model_row = QHBoxLayout()
        self._text_model_row.addWidget(QLabel("Model"), 0)
        self._text_model = QLineEdit()
        self._text_model.setPlaceholderText("connect first")
        self._text_model.setEnabled(False)
        self._text_model_row.addWidget(self._text_model, 1)
        fields.append(self._text_model_row)

        return fields

    def _cloud_text_fields(self):
        fields = []

        self._cloud_text_cb = QCheckBox("Enable cloud text fallback (GPT-4o-mini)")
        self._cloud_text_cb.setChecked(False)
        fields.append(self._cloud_text_cb)

        row = QHBoxLayout()
        row.addWidget(QLabel("Endpoint"), 0)
        self._cloud_text_endpoint = QLineEdit()
        self._cloud_text_endpoint.setPlaceholderText("https://api.openai.com")
        row.addWidget(self._cloud_text_endpoint, 1)
        fields.append(row)

        row = QHBoxLayout()
        row.addWidget(QLabel("API Key"), 0)
        self._cloud_text_api_key = QLineEdit()
        self._cloud_text_api_key.setPlaceholderText("sk-...")
        self._cloud_text_api_key.setEchoMode(QLineEdit.Password)
        row.addWidget(self._cloud_text_api_key, 1)
        self._cloud_connect_btn = QPushButton()
        self._cloud_connect_btn.setIcon(self._link_icon())
        self._cloud_connect_btn.setFixedSize(28, 28)
        self._cloud_connect_btn.setToolTip("Connect & fetch models")
        self._cloud_connect_btn.clicked.connect(self._cloud_connect_and_fetch)
        row.addWidget(self._cloud_connect_btn)
        fields.append(row)

        self._cloud_text_model_row = QHBoxLayout()
        self._cloud_text_model_row.addWidget(QLabel("Model"), 0)
        self._cloud_text_model = QLineEdit()
        self._cloud_text_model.setPlaceholderText("connect first")
        self._cloud_text_model.setEnabled(False)
        self._cloud_text_model_row.addWidget(self._cloud_text_model, 1)
        fields.append(self._cloud_text_model_row)

        return fields

    def _cloud_connect_and_fetch(self):
        """Test cloud endpoint connection and fetch models."""
        endpoint = self._cloud_text_endpoint.text().strip()
        api_key = self._cloud_text_api_key.text().strip()
        if not endpoint:
            self._test_results.setText("Enter an endpoint URL.")
            self._test_results.setStyleSheet("font-size: 12px; padding: 4px 0; color: #f59e0b;")
            return
        self._test_results.setText("Connecting...")
        self._test_results.setStyleSheet("font-size: 12px; padding: 4px 0;")
        from ai.client import AIClient
        client = AIClient(endpoint, api_key)
        result = client.get_models()
        if result['status'] == 'ok' and result['models']:
            model_ids = [m['id'] for m in result['models']]
            old_widget = self._cloud_text_model
            self._cloud_text_model_row.removeWidget(old_widget)
            old_widget.deleteLater()
            combo = QComboBox()
            combo.addItems(model_ids)
            current = self.settings.get('cloud_text_model', 'gpt-4o-mini')
            if current in model_ids:
                combo.setCurrentText(current)
            self._cloud_text_model = combo
            self._cloud_text_model_row.addWidget(combo, 1)
            self._test_results.setText(f"Connected! Found {len(model_ids)} models.")
            self._test_results.setStyleSheet("font-size: 12px; padding: 4px 0; color: #22c55e;")
        else:
            self._test_results.setText(f"Failed: {result['message']}")
            self._test_results.setStyleSheet("font-size: 12px; padding: 4px 0; color: #ef4444;")
            if result['status_code'] == 401:
                self._test_results.setText("Failed: Invalid API key")
            elif result['status_code'] == 403:
                self._test_results.setText("Failed: API key not authorized")

    def _processing_fields(self):
        fields = []

        # Workers
        row = QHBoxLayout()
        row.addWidget(QLabel("Workers"), 0)
        w_inner = QHBoxLayout()
        w_inner.setSpacing(2)
        self._workers_spin = _WheelSpinBox()
        self._workers_spin.setText("4")
        self._workers_spin.setFixedWidth(60)
        self._workers_spin.setAlignment(Qt.AlignCenter)
        self._workers_spin.setValidator(self._int_validator(1, 16))
        w_inner.addWidget(self._workers_spin)
        w_btn_col = QVBoxLayout()
        w_btn_col.setSpacing(2)
        w_up = QPushButton("+")
        w_up.setFixedSize(28, 18)
        w_up.setStyleSheet("font-weight: 700; font-size: 14px; padding: 0;")
        w_up.clicked.connect(lambda: self._spin_step(self._workers_spin, 1, 1, 16))
        w_btn_col.addWidget(w_up)
        w_down = QPushButton("−")
        w_down.setFixedSize(28, 18)
        w_down.setStyleSheet("font-weight: 700; font-size: 14px; padding: 0;")
        w_down.clicked.connect(lambda: self._spin_step(self._workers_spin, -1, 1, 16))
        w_btn_col.addWidget(w_down)
        w_inner.addLayout(w_btn_col)
        row.addStretch()
        row.addLayout(w_inner)
        fields.append(row)

        # Output format
        row = QHBoxLayout()
        row.addWidget(QLabel("Output"), 0)
        self._format_combo = QComboBox()
        self._format_combo.addItems(["Embedded", "Sidecar", "Both"])
        row.addWidget(self._format_combo)
        fields.append(row)

        # Export CSV
        self._export_csv_cb = QCheckBox("Export CSV after batch")
        self._export_csv_cb.setChecked(True)
        fields.append(self._export_csv_cb)

        # Duplicate threshold
        row = QHBoxLayout()
        row.addWidget(QLabel("Duplicate Threshold Distance"), 0)
        dup_inner = QHBoxLayout()
        dup_inner.setSpacing(2)
        self._dup_threshold = _WheelSpinBox()
        self._dup_threshold.setText("10")
        self._dup_threshold.setFixedWidth(60)
        self._dup_threshold.setAlignment(Qt.AlignCenter)
        self._dup_threshold.setValidator(self._int_validator(1, 50))
        dup_inner.addWidget(self._dup_threshold)
        btn_col = QVBoxLayout()
        btn_col.setSpacing(2)
        self._dup_up = QPushButton("+")
        self._dup_up.setFixedSize(28, 18)
        self._dup_up.setStyleSheet("font-weight: 700; font-size: 14px; padding: 0;")
        self._dup_up.clicked.connect(self._dup_increment)
        btn_col.addWidget(self._dup_up)
        self._dup_down = QPushButton("−")
        self._dup_down.setFixedSize(28, 18)
        self._dup_down.setStyleSheet("font-weight: 700; font-size: 14px; padding: 0;")
        self._dup_down.clicked.connect(self._dup_decrement)
        btn_col.addWidget(self._dup_down)
        dup_inner.addLayout(btn_col)
        row.addStretch()
        row.addLayout(dup_inner)
        fields.append(row)

        self._auto_learn = QCheckBox("Auto-learn new locations")
        self._auto_learn.setChecked(True)
        fields.append(self._auto_learn)

        return fields

    @staticmethod
    def _int_validator(min_val, max_val):
        from PySide6.QtGui import QIntValidator
        return QIntValidator(min_val, max_val)

    def _dup_increment(self):
        val = int(self._dup_threshold.text() or "10")
        if val < 50:
            self._dup_threshold.setText(str(val + 1))

    def _dup_decrement(self):
        val = int(self._dup_threshold.text() or "10")
        if val > 1:
            self._dup_threshold.setText(str(val - 1))

    @staticmethod
    def _spin_step(spin, step, min_val, max_val):
        try:
            val = int(spin.text())
        except ValueError:
            val = min_val
        val = max(min_val, min(max_val, val + step))
        spin.setText(str(val))

    @property
    def dup_threshold_value(self):
        try:
            return int(self._dup_threshold.text())
        except ValueError:
            return 10

    def _on_text_toggle(self, state):
        """Show/hide text model section based on checkbox state."""
        checked = self._reuse_text_cb.isChecked()
        self._text_section.setVisible(not checked)

    def _load_settings(self):
        """Load current settings into UI."""
        self._vision_endpoint.setText(self.settings.vision_endpoint)
        self._vision_api_key.setText(self.settings.vision_api_key)

        vm = self.settings.vision_model
        if vm and vm != 'auto':
            if hasattr(self._vision_model, 'setCurrentText'):
                self._vision_model.setCurrentText(vm)
            else:
                self._vision_model.setText(vm)
            self._vision_model.setEnabled(True)

        self._text_endpoint.setText(self.settings.text_endpoint)
        self._text_api_key.setText(self.settings.text_api_key)
        tm = self.settings.text_model
        if tm:
            if hasattr(self._text_model, 'setCurrentText'):
                self._text_model.setCurrentText(tm)
            else:
                self._text_model.setText(tm)
            self._text_model.setEnabled(True)

        # Auto-detect if text differs from vision
        text_differs = (
            self.settings.text_endpoint != self.settings.vision_endpoint
            or self.settings.text_api_key != self.settings.vision_api_key
            or self.settings.text_model != self.settings.vision_model
        )
        self._reuse_text_cb.blockSignals(True)
        self._reuse_text_cb.setChecked(not text_differs)
        self._reuse_text_cb.blockSignals(False)
        self._text_section.setVisible(text_differs)

        self._auto_learn.setChecked(self.settings.auto_learn_location)
        self._dup_threshold.setText(str(self.settings.get('duplicate_threshold', 10)))
        self._workers_spin.setText(str(self.settings.max_workers))
        fmt = self.settings.get('output_format', 'embedded')
        self._format_combo.setCurrentIndex({'embedded': 0, 'sidecar': 1, 'both': 2}.get(fmt, 0))
        self._export_csv_cb.setChecked(self.settings.get('export_csv', True))

        # Cloud text fallback
        self._cloud_text_cb.setChecked(self.settings.get('cloud_text_enabled', False))
        self._cloud_text_endpoint.setText(self.settings.get('cloud_text_endpoint', 'https://api.openai.com'))
        self._cloud_text_api_key.setText(self.settings.get('cloud_text_api_key', ''))
        ct_model = self.settings.get('cloud_text_model', 'gpt-4o-mini')
        if ct_model:
            if hasattr(self._cloud_text_model, 'setCurrentText'):
                self._cloud_text_model.setCurrentText(ct_model)
            else:
                self._cloud_text_model.setText(ct_model)
            self._cloud_text_model.setEnabled(True)

    def _on_save(self):
        """Save settings."""
        self.settings.set('vision_endpoint', self._vision_endpoint.text().strip())
        self.settings.set('vision_api_key', self._vision_api_key.text().strip())
        vision_model_text = self._vision_model.currentText().strip() if hasattr(self._vision_model, 'currentText') else self._vision_model.text().strip()
        self.settings.set('vision_model', vision_model_text)

        reuse = self._reuse_text_cb.isChecked()
        if reuse:
            self.settings.set('text_endpoint', self._vision_endpoint.text().strip())
            self.settings.set('text_api_key', self._vision_api_key.text().strip())
            self.settings.set('text_model', vision_model_text)
        else:
            self.settings.set('text_endpoint', self._text_endpoint.text().strip())
            self.settings.set('text_api_key', self._text_api_key.text().strip())
        text_model_text = self._text_model.currentText().strip() if hasattr(self._text_model, 'currentText') else self._text_model.text().strip()
        self.settings.set('text_model', text_model_text)
        self.settings.set('auto_learn_location', self._auto_learn.isChecked())
        self.settings.set('duplicate_threshold', self.dup_threshold_value)
        try:
            self.settings.set('max_workers', int(self._workers_spin.text()))
        except ValueError:
            pass
        fmt_map = {0: 'embedded', 1: 'sidecar', 2: 'both'}
        self.settings.set('output_format', fmt_map.get(self._format_combo.currentIndex(), 'embedded'))
        self.settings.set('export_csv', self._export_csv_cb.isChecked())

        # Cloud text fallback
        self.settings.set('cloud_text_enabled', self._cloud_text_cb.isChecked())
        self.settings.set('cloud_text_endpoint', self._cloud_text_endpoint.text().strip())
        self.settings.set('cloud_text_api_key', self._cloud_text_api_key.text().strip())
        ct_model_text = self._cloud_text_model.currentText().strip() if hasattr(self._cloud_text_model, 'currentText') else self._cloud_text_model.text().strip()
        self.settings.set('cloud_text_model', ct_model_text)

        self.settings.save()
        self.settings_saved.emit()

    @staticmethod
    def _link_icon():
        from PySide6.QtGui import QPainter, QPixmap, QIcon, QImage
        from PySide6.QtSvg import QSvgRenderer
        from PySide6.QtCore import QByteArray
        svg = (
            '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="black" '
            'stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
            '<path d="M10 13a5 5 0 007.54.54l3-3a5 5 0 00-7.07-7.07l-1.72 1.71"/>'
            '<path d="M14 11a5 5 0 00-7.54-.54l-3 3a5 5 0 007.07 7.07l1.71-1.71"/>'
            '</svg>'
        )
        renderer = QSvgRenderer(QByteArray(svg.encode()))
        img = QImage(24, 24, QImage.Format.Format_ARGB32)
        img.fill(0)
        painter = QPainter(img)
        renderer.render(painter)
        painter.end()
        return QIcon(QPixmap.fromImage(img))

    def _connect_and_fetch(self):
        """Test connection and fetch available models."""
        from ai.client import AIClient
        endpoint = self._vision_endpoint.text().strip()
        api_key = self._vision_api_key.text().strip()
        if not endpoint:
            return

        self._test_results.setText("Connecting...")
        self._test_results.setStyleSheet("font-size: 12px; padding: 4px 0;")
        client = AIClient(endpoint, api_key)
        result = client.get_models()
        if result['status'] == 'ok':
            models = result['models']
            if models:
                self._replace_with_combo(self._vision_model_row, self._vision_model, models)
                self._test_results.setText("Connected — fetched " + str(len(models)) + " model" + ("s" if len(models) != 1 else ""))
                self._test_results.setStyleSheet("font-size: 12px; padding: 4px 0; color: #22c55e;")
            else:
                self._test_results.setText("Connected but no models available")
                self._test_results.setStyleSheet("font-size: 12px; padding: 4px 0; color: #f59e0b;")
        else:
            self._test_results.setText("Connection failed — " + result['message'])
            self._test_results.setStyleSheet("font-size: 12px; padding: 4px 0; color: #ef4444;")
        client.close()

    def _text_connect_and_fetch(self):
        """Test text connection and fetch available models."""
        from ai.client import AIClient
        endpoint = self._text_endpoint.text().strip()
        api_key = self._text_api_key.text().strip()
        if not endpoint:
            return

        self._test_results.setText("Connecting...")
        self._test_results.setStyleSheet("font-size: 12px; padding: 4px 0;")
        client = AIClient(endpoint, api_key)
        result = client.get_models()
        if result['status'] == 'ok':
            models = result['models']
            if models:
                self._replace_with_combo(self._text_model_row, self._text_model, models)
                self._test_results.setText("Connected — fetched " + str(len(models)) + " model" + ("s" if len(models) != 1 else ""))
                self._test_results.setStyleSheet("font-size: 12px; padding: 4px 0; color: #22c55e;")
            else:
                self._test_results.setText("Connected but no models available")
                self._test_results.setStyleSheet("font-size: 12px; padding: 4px 0; color: #f59e0b;")
        else:
            self._test_results.setText("Connection failed — " + result['message'])
            self._test_results.setStyleSheet("font-size: 12px; padding: 4px 0; color: #ef4444;")
        client.close()

    def _replace_with_combo(self, row_layout, old_widget, models):
        """Replace a QLineEdit with a QComboBox in the same layout position."""
        # Find index of old widget in the row layout
        index = -1
        for i in range(row_layout.count()):
            item = row_layout.itemAt(i)
            if item and item.widget() is old_widget:
                index = i
                break

        if index == -1:
            return

        # Create new combo box
        combo = QComboBox()
        combo.setEditable(True)
        for m in models:
            combo.addItem(m.get('id', '?'))
        combo.setCurrentIndex(0)

        # Replace in layout
        row_layout.removeItem(row_layout.takeAt(index))
        row_layout.insertWidget(index, combo, 1)
        old_widget.deleteLater()

        # Update reference
        if old_widget is self._vision_model:
            self._vision_model = combo
        elif old_widget is self._text_model:
            self._text_model = combo
