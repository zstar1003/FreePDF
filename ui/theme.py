"""Shared desktop design tokens and consistent vector action icons."""

from PyQt6.QtCore import QEvent, QObject, QSize, Qt
from PyQt6.QtGui import QIcon, QPixmap
from PyQt6.QtWidgets import QApplication, QComboBox, QDialog, QFrame, QLabel, QPushButton, QWidget
from utils.resources import resource_path

STYLE = """
QWidget { color: #19343e; font-family: 'PingFang SC', 'Microsoft YaHei UI', 'Noto Sans CJK SC'; font-size: 15px; }
QMainWindow, QDialog { background: #eef3f5; }
QDialog { padding: 4px; }
QLabel { background: transparent; }
QLabel#brandTitle { font-size: 25px; font-weight: 700; letter-spacing: -1px; }
QLabel#dialogTitle { font-size: 18px; font-weight: 600; }
QLabel#muted, QLabel#emptyState { color: #637c86; }
QLabel#emptyState { font-size: 18px; padding: 28px; }
QLabel#sectionTitle { font-size: 16px; font-weight: 600; padding: 8px 14px; background: #ffffff; }
QLabel#versionBadge { color: #116a64; background: #ddefeb; padding: 4px 10px; border-radius: 10px; }
QFrame#documentPanel, QFrame#qaPanel { background: #ffffff; border: 1px solid #d6e1e5; border-radius: 12px; }
QPushButton { background: #ffffff; border: 1px solid #ccdce1; border-radius: 8px; padding: 8px 12px; min-height: 20px; font-weight: 500; }
QPushButton:hover { background: #e5f1ef; border-color: #83b4ae; }
QPushButton:pressed { background: #d6eae6; }
QPushButton:focus { border: 2px solid #187d74; padding: 7px 11px; }
QPushButton[role="primary"] { background: #126d66; border-color: #126d66; color: white; }
QPushButton[role="primary"]:hover { background: #0b5954; }
QPushButton[role="quiet"] { background: transparent; border-color: transparent; }
QPushButton:disabled { color: #81949c; background: #e6edef; border-color: #dce6e9; }
QLineEdit, QSpinBox, QComboBox { background: white; padding: 7px 10px; border: 1px solid #ccdce1; border-radius: 7px; min-height: 20px; selection-background-color: #126d66; }
QLineEdit:focus, QComboBox:focus, QSpinBox:focus { border: 1px solid #187d74; }
QComboBox::drop-down { border: 0; width: 24px; }
QComboBox QAbstractItemView { background: white; selection-background-color: #dcefeb; selection-color: #19343e; padding: 5px; }
QGroupBox { background: white; border: 1px solid #d6e1e5; border-radius: 10px; margin-top: 14px; padding: 18px 14px 12px; font-weight: 600; }
QGroupBox::title { subcontrol-origin: margin; left: 16px; padding: 0 5px; }
QTextEdit, QTextBrowser, QListWidget, QTableWidget { background: #ffffff; border: 1px solid #d6e1e5; border-radius: 8px; padding: 9px; selection-background-color: #dcefeb; }
QCheckBox { spacing: 8px; padding: 4px; }
QCheckBox::indicator { width: 18px; height: 18px; }
QProgressBar { border: 0; border-radius: 5px; background: #deeaed; text-align: center; min-height: 8px; }
QProgressBar::chunk { background: #168577; border-radius: 5px; }
QProgressBar#translationProgress { min-height: 26px; max-height: 26px; }
QSplitter::handle { background: transparent; width: 10px; }
QScrollBar:vertical { background: #f2f6f7; width: 10px; margin: 2px; }
QScrollBar::handle:vertical { background: #b6cbd1; border-radius: 4px; min-height: 30px; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QStatusBar { background: #eef3f5; color: #526e78; padding: 6px 12px; font-size: 14px; }
QToolTip { background: #19343e; color: #ffffff; border: 0; padding: 7px; }
"""

PATHS = {
    "open": '<path d="M3 7h6l2 2h10v10H3z"/><path d="M3 7V5h7l2 2h7v2"/>',
    "export": '<path d="M12 3v12m-4-4 4 4 4-4"/><path d="M4 15v5h16v-5"/>',
    "settings": '<path d="M4 7h16M4 17h16"/><circle cx="9" cy="7" r="3"/><circle cx="15" cy="17" r="3"/>',
    "sync": '<path d="M4 8h15l-4-4M20 16H5l4 4"/>',
    "about": '<circle cx="12" cy="12" r="9"/><path d="M12 11v6m0-10v1"/>',
    "update": '<path d="M20 10a8 8 0 1 0-2 8M20 4v6h-6"/>',
    "batch": '<rect x="7" y="3" width="13" height="16" rx="2"/><path d="M4 6v15h13M10 8h7m-7 4h7"/>',
    "chat": '<path d="M4 4h16v12H9l-5 4z"/><path d="M8 8h8m-8 4h5"/>',
    "close": '<path d="m6 6 12 12M18 6 6 18"/>',
    "previous": '<path d="m15 5-7 7 7 7"/>',
    "next": '<path d="m9 5 7 7-7 7"/>',
    "send": '<path d="m3 3 18 9-18 9 4-9zM7 12h14"/>',
}


def action_icon(name, light=False):
    from PyQt6.QtSvg import QSvgRenderer
    from PyQt6.QtGui import QPainter
    color = "#ffffff" if light else "#335e67"
    svg = f'<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24"><g fill="none" stroke="{color}" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round">{PATHS.get(name, PATHS["settings"])}</g></svg>'
    pixmap = QPixmap(48, 48)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    QSvgRenderer(svg.encode()).render(painter)
    painter.end()
    pixmap.setDevicePixelRatio(2)
    return QIcon(pixmap)


def style_button(button, icon=None, primary=False, quiet=False):
    button.setStyleSheet("")
    button.setProperty("role", "primary" if primary else "quiet" if quiet else "default")
    if icon:
        button.setIcon(action_icon(icon, primary))
        button.setIconSize(QSize(18, 18))
    button.style().unpolish(button)
    button.style().polish(button)


def polish_window(window):
    """Replace legacy per-control styling without overriding custom painted widgets."""
    from PyQt6.QtWidgets import QAbstractButton, QLineEdit, QGroupBox, QTextEdit, QProgressBar
    for widget in [window, *window.findChildren(QWidget)]:
        if isinstance(widget, (QPushButton, QComboBox, QLineEdit, QGroupBox, QTextEdit, QProgressBar)):
            widget.setStyleSheet("")
        if isinstance(widget, QFrame) and not isinstance(widget, QLabel):
            widget.setStyleSheet("")
        if widget.__class__.__name__ in ("EmbeddedQAWidget", "QWidget"):
            widget.setStyleSheet("")
        if isinstance(widget, QPushButton):
            if widget.maximumHeight() < 36:
                widget.setMaximumHeight(16777215)
                widget.setMinimumHeight(36)
            if widget.maximumWidth() < 90:
                widget.setMaximumWidth(16777215)
                widget.setMinimumWidth(70)
        if isinstance(widget, QLabel) and widget.styleSheet():
            # Dynamic status colors remain meaningful; raise the smallest legacy captions.
            import re
            widget.setStyleSheet(re.sub(r'font-size:\s*(?:10|11|12|13)px', 'font-size: 14px', widget.styleSheet()))
    if isinstance(window, QDialog):
        window.setStyleSheet("")
        if window.minimumWidth() == window.maximumWidth():
            window.setMinimumWidth(min(760, window.minimumWidth()))
            window.setMaximumWidth(16777215)
        if window.minimumHeight() == window.maximumHeight():
            window.setMinimumHeight(min(550, window.minimumHeight()))
            window.setMaximumHeight(16777215)
        window.ensurePolished()
        if window.layout():
            window.layout().invalidate()
            window.layout().activate()
        window.resize(window.size().expandedTo(window.minimumSizeHint()))


class ThemeFilter(QObject):
    def eventFilter(self, obj, event):
        if isinstance(obj, QDialog) and event.type() == QEvent.Type.Show:
            polish_window(obj)
        return False


def install_theme(app):
    from PyQt6.QtGui import QFont, QFontDatabase
    families = QFontDatabase.families()
    family = next((name for name in ("PingFang SC", "Microsoft YaHei UI", "Noto Sans CJK SC") if name in families), app.font().family())
    font = QFont(family)
    font.setPixelSize(15)
    app.setFont(font)
    app.setStyle("Fusion")
    app.setStyleSheet(STYLE + 'QComboBox::down-arrow { image: url("' + str(resource_path("ui/icons/chevron-down.svg")) + '"); width: 14px; height: 14px; }')
    theme_filter = ThemeFilter(app)
    app.installEventFilter(theme_filter)
    app._freepdf_theme_filter = theme_filter
