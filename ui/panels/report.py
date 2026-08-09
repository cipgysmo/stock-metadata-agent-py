"""Report panel displaying batch processing results."""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QTextEdit, QGroupBox, QGridLayout, QPushButton,
    QFileDialog, QMessageBox
)
from PySide6.QtCore import Qt
from core.orchestrator import BatchReport
from core.report import ReportGenerator


class ReportPanel(QWidget):
    """Displays batch processing report."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._report: BatchReport | None = None
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)

        # Placeholder
        self._placeholder = QLabel(
            "No batch results yet.\n\n"
            "Run a batch processing job to see the report here."
        )
        self._placeholder.setAlignment(Qt.AlignCenter)
        self._placeholder.setStyleSheet("padding: 40px; font-size: 13px;")
        layout.addWidget(self._placeholder)

        # Summary stats
        self._stats_group = QGroupBox("Summary")
        stats_layout = QGridLayout(self._stats_group)

        self._stat_labels = {}
        stat_items = [
            ('total_files', 'Total Files'), ('images', 'Images'),
            ('videos', 'Videos'), ('successful', 'Successful'),
            ('failed', 'Failed'), ('avg_quality', 'Avg Quality'),
        ]
        for i, (key, label) in enumerate(stat_items):
            row = i // 3
            col = (i % 3) * 2
            lbl = QLabel(label)
            lbl.setStyleSheet("font-size: 12px;")
            stats_layout.addWidget(lbl, row, col)
            val = QLabel("0")
            val.setStyleSheet("font-weight: bold; font-size: 14px;")
            stats_layout.addWidget(val, row, col + 1)
            self._stat_labels[key] = val

        self._stats_group.setVisible(False)
        layout.addWidget(self._stats_group)

        # Quality metrics
        self._quality_group = QGroupBox("Quality Metrics")
        quality_layout = QGridLayout(self._quality_group)

        quality_items = [
            ('duplicates', 'Duplicates'), ('similar', 'Similar Files'),
            ('gps_issues', 'GPS Inconsistencies'), ('review', 'Needs Review'),
            ('warnings', 'Commercial Warnings'),
        ]
        for i, (key, label) in enumerate(quality_items):
            row = i // 2
            col = i % 2 * 2
            lbl = QLabel(label)
            lbl.setStyleSheet("font-size: 12px;")
            quality_layout.addWidget(lbl, row, col)
            val = QLabel("0")
            val.setStyleSheet("font-weight: bold; font-size: 14px;")
            quality_layout.addWidget(val, row, col + 1)
            self._stat_labels[key] = val

        self._quality_group.setVisible(False)
        layout.addWidget(self._quality_group)

        # Full report text
        self._report_text = QTextEdit()
        self._report_text.setReadOnly(True)
        self._report_text.setVisible(False)
        self._report_text.setStyleSheet("font-family: monospace; font-size: 11px;")
        layout.addWidget(self._report_text)

        # Actions
        action_layout = QHBoxLayout()
        self._export_btn = QPushButton("Export Report")
        self._export_btn.setEnabled(False)
        self._export_btn.clicked.connect(self._on_export)
        action_layout.addWidget(self._export_btn)
        action_layout.addStretch()
        layout.addLayout(action_layout)

    def display(self, report: BatchReport) -> None:
        """Display a batch report."""
        self._report = report
        self._placeholder.setVisible(False)
        self._stats_group.setVisible(True)
        self._quality_group.setVisible(True)
        self._report_text.setVisible(True)
        self._export_btn.setEnabled(True)

        # Update stats
        self._stat_labels['total_files'].setText(str(report.total_files))
        self._stat_labels['images'].setText(str(report.images_processed))
        self._stat_labels['videos'].setText(str(report.videos_processed))
        self._stat_labels['successful'].setText(str(report.successful))
        self._stat_labels['failed'].setText(str(report.failed))
        self._stat_labels['avg_quality'].setText(f"{report.average_quality:.1f}/100")

        # Update quality metrics
        self._stat_labels['duplicates'].setText(str(report.duplicates_found))
        self._stat_labels['similar'].setText(str(report.similar_found))
        self._stat_labels['gps_issues'].setText(str(report.gps_inconsistencies))
        self._stat_labels['review'].setText(str(report.files_needing_review))
        self._stat_labels['warnings'].setText(str(report.commercial_warnings))

        # Set quality colors
        avg = report.average_quality
        color = "green" if avg >= 80 else ("orange" if avg >= 60 else "red")
        self._stat_labels['avg_quality'].setStyleSheet(
            f"font-weight: bold; font-size: 14px; color: {color};"
        )

        # Generate full report
        gen = ReportGenerator()
        self._report_text.setPlainText(gen.generate_text(report))

    def _on_export(self) -> None:
        """Export report to file."""
        if not self._report:
            return

        path, _ = QFileDialog.getSaveFileName(
            self, "Save Report", "", "Text Files (*.txt);;All Files (*)"
        )
        if path:
            gen = ReportGenerator()
            report_text = gen.generate_text(self._report)
            with open(path, 'w', encoding='utf-8') as f:
                f.write(report_text)
            QMessageBox.information(self, "Exported", f"Report saved to:\n{path}")
