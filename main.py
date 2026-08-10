"""AI Stock Metadata Agent - Main entry point."""

import sys
import os
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
    ]
)
logging.getLogger('PIL').setLevel(logging.WARNING)
logging.getLogger('urllib3').setLevel(logging.WARNING)

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon, QPalette
from ui.window import MainWindow


def _get_icon_path():
    """Get icon path for development or bundled app."""
    if getattr(sys, 'frozen', False):
        base_dir = sys._MEIPASS
    else:
        base_dir = os.path.dirname(os.path.abspath(__file__))

    icon_path = os.path.join(base_dir, 'resources', 'icon.png')
    if os.path.exists(icon_path):
        return icon_path
    return None


def _is_dark_mode() -> bool:
    """Detect system dark mode."""
    try:
        palette = QApplication.palette()
        bg = palette.color(QPalette.ColorRole.Window)
        return bg.lightness() < 128
    except Exception:
        return False


def _get_stylesheet():
    """Return stylesheet matching system theme."""
    dark = _is_dark_mode()

    if dark:
        BG = '#18181b'
        CARD = '#27272a'
        BORDER = '#3f3f46'
        TEXT = '#fafafa'
        TEXT_SEC = '#a1a1aa'
        ACCENT = '#6366f1'
        ACCENT_HOV = '#818cf8'
        ACCENT_DIS = '#4338ca'
        OK = '#22c55e'
        FAIL = '#ef4444'
        WARN = '#f59e0b'
        INPUT_BG = '#1f1f23'
        TAB_BG = '#27272a'
        TAB_SEL = '#18181b'
    else:
        BG = '#ffffff'
        CARD = '#f8f9fa'
        BORDER = '#e5e7eb'
        TEXT = '#111827'
        TEXT_SEC = '#6b7280'
        ACCENT = '#6366f1'
        ACCENT_HOV = '#4f46e5'
        ACCENT_DIS = '#a5b4fc'
        OK = '#16a34a'
        FAIL = '#dc2626'
        WARN = '#d97706'
        INPUT_BG = '#ffffff'
        TAB_BG = '#f3f4f6'
        TAB_SEL = '#ffffff'

    return f"""
        QMainWindow {{ background-color: {BG}; }}
        QWidget {{ font-family: "Helvetica Neue", Arial; font-size: 13px; color: {TEXT}; }}

        QTabWidget::pane {{
            border: none; background: transparent;
        }}
        QTabBar {{
            font-size: 13px; font-weight: 500;
        }}
        QTabBar::tab {{
            background: {TAB_BG}; border: none; border-bottom: 2px solid transparent;
            padding: 10px 20px; margin-right: 4px; color: {TEXT_SEC};
            border-radius: 8px 8px 0 0;
        }}
        QTabBar::tab:selected {{
            background: {TAB_SEL}; border-bottom: 2px solid {ACCENT}; color: {TEXT};
        }}
        QTabBar::tab:hover:!selected {{
            background: {CARD};
        }}

        QGroupBox {{
            border: none; margin-top: 4px; padding-top: 0; font-size: 13px; font-weight: 600; color: {TEXT};
        }}
        QGroupBox::title {{
            subcontrol-origin: margin; subcontrol-position: top left;
            left: 0px; padding: 0 4px;
        }}

        QFrame#card {{
            background: {CARD}; border: 1px solid {BORDER}; border-radius: 10px;
        }}

        QProgressBar {{
            border: none; border-radius: 6px; text-align: center;
            height: 6px; background: {CARD};
        }}
        QProgressBar::chunk {{
            background-color: {ACCENT}; border-radius: 6px;
        }}

        QTableWidget {{
            border: 1px solid {BORDER}; border-radius: 8px;
            background: {CARD}; gridline-color: {BORDER};
            selection-background-color: {ACCENT}; selection-color: white;
            alternate-background-color: transparent;
        }}
        QTableWidget::item {{ padding: 6px 8px; border: none; }}
        QTableWidget::item:selected {{ background: {ACCENT}; color: white; }}
        QHeaderView::section {{
            background: transparent; border: none; border-bottom: 1px solid {BORDER};
            padding: 8px; font-weight: 600; font-size: 11px; color: {TEXT_SEC};
            text-transform: uppercase; letter-spacing: 0.5px;
        }}
        QTableWidget QScrollBar:vertical {{
            background: transparent; width: 6px;
        }}
        QTableWidget QScrollBar::handle:vertical {{
            background: {BORDER}; border-radius: 3px;
        }}

        QPushButton {{
            border: none; border-radius: 8px; padding: 8px 18px;
            background: {CARD}; color: {TEXT}; font-size: 13px; font-weight: 500;
        }}
        QPushButton:hover {{ background: {BORDER}; }}
        QPushButton:pressed {{ background: {ACCENT}; color: white; }}
        QPushButton:disabled {{ background: {CARD}; color: {TEXT_SEC}; opacity: 0.5; }}

        QPushButton#primary {{
            background: {ACCENT}; color: white; font-weight: 600; padding: 10px 24px;
        }}
        QPushButton#primary:hover {{ background: {ACCENT_HOV}; }}
        QPushButton#primary:pressed {{ background: {ACCENT_DIS}; }}
        QPushButton#primary:disabled {{ background: {ACCENT_DIS}; color: rgba(255,255,255,0.5); }}

        QPushButton#danger {{
            background: {FAIL}; color: white;
        }}
        QPushButton#danger:hover {{ background: #b91c1c; }}

        QPushButton#secondary {{
            background: {CARD}; border: 1px solid {BORDER};
        }}

        QLineEdit {{
            border: 1px solid {BORDER}; border-radius: 8px;
            padding: 8px 12px; background: {INPUT_BG}; color: {TEXT};
        }}
        QLineEdit:focus {{ border-color: {ACCENT}; }}
        QLineEdit:disabled {{ background: {CARD}; color: {TEXT_SEC}; }}

        QComboBox {{
            border: 1px solid {BORDER}; border-radius: 8px;
            padding: 8px 12px; background: {INPUT_BG}; color: {TEXT};
        }}
        QComboBox QAbstractItemView {{
            background: {INPUT_BG}; color: {TEXT}; selection-background-color: {ACCENT};
            selection-color: white; border: 1px solid {BORDER}; border-radius: 8px;
        }}
        QComboBox:focus {{ border-color: {ACCENT}; }}

        QSpinBox {{
            border: 1px solid {BORDER}; border-radius: 8px;
            padding: 8px 12px; background: {INPUT_BG}; color: {TEXT};
        }}
        QSpinBox:focus {{ border-color: {ACCENT}; }}
        QSpinBox::up-button, QSpinBox::down-button {{
            width: 0; background: transparent; border: none;
        }}

        QCheckBox {{
            spacing: 8px; color: {TEXT};
        }}
        QCheckBox::indicator {{
            width: 18px; height: 18px; border-radius: 4px;
            border: 1px solid {BORDER}; background: {INPUT_BG};
        }}
        QCheckBox::indicator:checked {{
            background: {ACCENT}; border-color: {ACCENT};
        }}

        QTextEdit {{
            border: 1px solid {BORDER}; border-radius: 8px;
            background: {CARD}; color: {TEXT}; padding: 8px;
        }}
        QTextEdit:focus {{ border-color: {ACCENT}; }}

        QLabel {{ color: {TEXT}; }}
        QScrollArea {{ background: transparent; border: none; }}
        QScrollBar:vertical {{
            background: transparent; width: 6px;
        }}
        QScrollBar::handle:vertical {{
            background: {BORDER}; border-radius: 3px; min-height: 20px;
        }}
        QScrollBar::handle:vertical:hover {{ background: {TEXT_SEC}; }}
        QScrollBar::add-line, QScrollBar::sub-line {{ height: 0px; }}
        QScrollBar::add-page, QScrollBar::sub-page {{ background: none; }}

        QMenuBar {{ background: {BG}; color: {TEXT}; }}
        QMenuBar::item:selected {{ background: {CARD}; }}

        QFileDialog {{ background: {BG}; color: {TEXT}; }}

        QToolTip {{
            background: {CARD}; color: {TEXT}; border: 1px solid {BORDER};
            border-radius: 6px; padding: 6px 10px;
        }}

        QStatusBar {{
            border-top: 1px solid {BORDER}; background: {BG}; color: {TEXT_SEC}; font-size: 12px;
        }}
    """


def main():
    """Application entry point."""
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    app = QApplication(sys.argv)
    app.setApplicationName("AI Stock Metadata Agent")
    app.setApplicationVersion("0.1.5")
    app.setStyle("Fusion")

    icon_path = _get_icon_path()
    if icon_path:
        app.setWindowIcon(QIcon(icon_path))

    app.setStyleSheet(_get_stylesheet())

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == '__main__':
    main()
