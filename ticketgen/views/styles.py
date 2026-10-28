"""Окно/виджеты: styles."""
from pathlib import Path

ICONS = (Path(__file__).parent / "icons").as_posix()

PRIMARY = "#2563EB"
DIFFICULTY_COLORS = {1: "#DCFCE7", 2: "#FEF3C7", 3: "#FEE2E2"}
DIFFICULTY_TEXT = {1: "#16A34A", 2: "#D97706", 3: "#DC2626"}
INACTIVE_TEXT = "#94A3B8"

APP_STYLE = """
QWidget { font-family: "Inter", "Segoe UI"; font-size: 14px; color: #0F172A; }
QMainWindow { background: #F8FAFC; }
QDialog { background: white; }

QPushButton {
    background: white; border: 1px solid #CBD5E1;
    border-radius: 10px; padding: 7px 16px; min-height: 20px;
}
QPushButton:hover { background: #F1F5F9; }
QPushButton:pressed { background: #E2E8F0; }
QPushButton:disabled { color: #94A3B8; background: #F1F5F9; }
QPushButton[kind="primary"] { background: #2563EB; color: white; border: none; }
QPushButton[kind="primary"]:hover { background: #1D4ED8; }
QPushButton[kind="primary"]:disabled { background: #93C5FD; }
QPushButton[kind="danger"] { color: #DC2626; border-color: #FCA5A5; }
QPushButton[kind="link"] {
    border: none; background: transparent; color: #2563EB; padding: 0;
}

QLineEdit, QComboBox, QSpinBox, QPlainTextEdit, QTextBrowser, QListWidget {
    background: white; border: 1px solid #E2E8F0; border-radius: 6px;
    padding: 0 8px; min-height: 34px;
}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QPlainTextEdit:focus {
    border: 2px solid #2563EB; padding: 0 7px; min-height: 32px;
}
QLineEdit[error="true"], QPlainTextEdit[error="true"] {
    border: 2px solid #DC2626; padding: 0 7px; min-height: 32px;
}
QLineEdit:disabled, QComboBox:disabled, QSpinBox:disabled {
    background: #F1F5F9; color: #94A3B8;
}

QComboBox::drop-down { border: none; width: 24px; }
QComboBox::down-arrow { image: url(@ICONS@/chevron.svg); width: 12px; height: 12px; }

QTabBar::tab { padding: 14px 20px; background: transparent; color: #64748B; }
QTabBar::tab:hover { background: #F1F5F9; }
QTabBar::tab:selected {
    color: #2563EB; background: transparent; border-bottom: 2px solid #2563EB;
}

QTableWidget {
    background: white; border: 1px solid #E2E8F0; border-radius: 8px;
    outline: none;
}
QTableWidget::item {
    padding: 0 16px; border-bottom: 1px solid #E2E8F0; color: #0F172A;
}
QTableWidget::item:hover { background: #F8FAFC; }
QTableWidget::item:selected { background: #EFF6FF; color: #0F172A; }
QHeaderView::section {
    background: #F1F5F9; color: #64748B; font-size: 12px; font-weight: normal;
    padding: 0 16px; border: none;
}

QLabel#title { font-size: 20px; font-weight: bold; }
QLabel#hint { color: #64748B; font-size: 12px; }
QLabel#hintBold { color: #64748B; font-size: 12px; font-weight: bold; }
QFrame#divider { background: #E2E8F0; border: none; }
QLabel#h2 { font-size: 16px; font-weight: bold; }
QLabel#value { font-size: 20px; font-weight: bold; }
QLabel#valueBlue { font-size: 20px; font-weight: bold; color: #2563EB; }
QLabel#tiny { color: #64748B; font-size: 11px; }
QLabel#okText { color: #16A34A; font-size: 11px; padding: 0 16px; }
QFrame#questionCard {
    background: #F8FAFC; border: 1px solid #E2E8F0; border-radius: 8px;
}
QScrollArea#cardsScroll, QWidget#cardsHost {
    background: transparent; border: none;
}
QLabel#dialogTitle { font-size: 20px; font-weight: bold; }
QListWidget#choices {
    background: white; border: 1px solid #E2E8F0; border-radius: 8px;
    padding: 0; min-height: 0; outline: none;
}
QListWidget#choices::item { border-bottom: 1px solid #E2E8F0; }
QListWidget#choices::item:selected { background: #EFF6FF; }
QLabel#questionCard {
    background: #F8FAFC; border: 1px solid #E2E8F0; border-radius: 8px;
}
QLabel#subtitle { color: #64748B; }
QLabel#caption { font-size: 12px; font-weight: bold; }
QLabel#itemTitle { font-weight: bold; }
QListWidget#templates {
    background: transparent; border: none; padding: 0; min-height: 0;
    outline: none;
}
QListWidget#templates::item { border-bottom: 1px solid #E2E8F0; }
QListWidget#templates::item:selected {
    background: #EFF6FF; border-left: 3px solid #2563EB;
}
QWidget#templateItem { background: transparent; }
QLabel#error { color: #DC2626; font-size: 12px; }
QLabel#warning {
    background: #FEF3C7; border: 1px solid #D97706; border-radius: 6px; padding: 8px;
}
QLabel#errorBanner {
    background: #FEF2F2; border: 1px solid #DC2626; border-radius: 6px; padding: 8px;
}
QLabel#chip {
    border-radius: 12px; padding: 2px 8px; font-size: 12px; max-height: 20px;
}
QCheckBox::indicator, QRadioButton::indicator, QTableView::indicator {
    width: 16px; height: 16px;
}
QTableView::indicator:unchecked { image: url(@ICONS@/check_off.svg); }
QTableView::indicator:checked { image: url(@ICONS@/check_on.svg); }
QCheckBox::indicator:unchecked { image: url(@ICONS@/check_off.svg); }
QCheckBox::indicator:checked { image: url(@ICONS@/check_on.svg); }
QRadioButton::indicator:unchecked { image: url(@ICONS@/radio_off.svg); }
QRadioButton::indicator:checked { image: url(@ICONS@/radio_on.svg); }
QLabel#success {
    background: #DCFCE7; border: 1px solid #16A34A; border-radius: 6px; padding: 8px;
}
QFrame#card {
    background: white; border: 1px solid #E2E8F0; border-radius: 8px;
}
QFrame#highlight {
    background: #EFF6FF; border: 1px solid #2563EB; border-radius: 6px;
}

QScrollBar:vertical { background: transparent; width: 8px; margin: 0; }
QScrollBar::handle:vertical {
    background: #CBD5E1; border-radius: 4px; min-height: 24px;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: none; }

QProgressBar {
    border: none; border-radius: 4px; text-align: center;
    background: #E2E8F0; max-height: 8px; color: transparent;
}
QProgressBar::chunk { background: #2563EB; border-radius: 4px; }
"""
APP_STYLE = APP_STYLE.replace("@ICONS@", ICONS)