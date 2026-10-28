"""Окно/виджеты: common."""
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ticketgen.views.styles import (
    DIFFICULTY_COLORS,
    DIFFICULTY_TEXT,
    ICONS,
)


def make_button(text: str, kind: str = "", tooltip: str = "") -> QPushButton:
    """Создаёт кнопку нужного вида: "", "primary", "danger" или "link"."""
    button = QPushButton(text)
    if kind:
        button.setProperty("kind", kind)
    if tooltip:
        button.setToolTip(tooltip)
    return button


def plural(number: int, forms: tuple[str, str, str]) -> str:
    """Подбирает форму слова по числу: plural(2, ("билет", "билета", "билетов")).

    Возвращает строку вида «2 билета».
    """
    last_two, last = number % 100, number % 10
    if 11 <= last_two <= 14:
        form = forms[2]
    elif last == 1:
        form = forms[0]
    elif 2 <= last <= 4:
        form = forms[1]
    else:
        form = forms[2]
    return f"{number} {form}"


def set_error(widget, has_error: bool):
    """Включает или выключает красную рамку у поля ввода."""
    widget.setProperty("error", has_error)
    widget.style().unpolish(widget)
    widget.style().polish(widget)


def make_table(
    headers: list[str], stretch_column: int = -1, widths: dict | None = None
) -> QTableWidget:
    """Создаёт таблицу только для чтения с выделением целых строк."""
    table = QTableWidget(0, len(headers))
    table.setHorizontalHeaderLabels(headers)
    table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
    table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
    table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
    table.verticalHeader().setVisible(False)
    header = table.horizontalHeader()
    header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
    header.setFixedHeight(40)
    header.setDefaultAlignment(
        Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
    )
    header.setHighlightSections(False)
    table.setShowGrid(False)
    table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
    if stretch_column >= 0:
        header.setSectionResizeMode(stretch_column, QHeaderView.ResizeMode.Stretch)
    for column, width in (widths or {}).items():
        header.setSectionResizeMode(column, QHeaderView.ResizeMode.Fixed)
        header.resizeSection(column, width)
    return table


def icon(name: str) -> QIcon:
    """Иконка из папки views/icons (например, icon("pencil"))."""
    return QIcon(f"{ICONS}/{name}.svg")


def fill_table(table: QTableWidget, rows: list[list]):
    """Заполняет таблицу строками значений (всё приводится к тексту)."""
    table.setRowCount(len(rows))
    for row_index, values in enumerate(rows):
        for column, value in enumerate(values):
            table.setItem(row_index, column, QTableWidgetItem(str(value)))


def show_error(parent, text: str):
    """Показывает окно с ошибкой."""
    QMessageBox.warning(parent, "Ошибка", text)


def show_info(parent, text: str):
    """Показывает информационное окно."""
    QMessageBox.information(parent, "TicketGen", text)


def divider() -> QFrame:
    """Тонкая горизонтальная линия."""
    line = QFrame()
    line.setObjectName("divider")
    line.setFixedHeight(1)
    return line


class ConfirmDialog(QDialog):
    """Окно подтверждения из макета: заголовок, крестик, текст, две кнопки."""

    def __init__(self, parent, title: str, body: str, ok_text: str):
        """title — крупный заголовок, body — пояснение, ok_text — красная кнопка."""
        super().__init__(parent)
        self.setWindowTitle("Подтверждение")
        self.setFixedWidth(480)
        self.setMinimumHeight(216)
        heading = QLabel(title)
        heading.setObjectName("dialogTitle")
        close = make_button("✕", "link")
        close.clicked.connect(self.reject)
        top = QHBoxLayout()
        top.setContentsMargins(24, 0, 24, 0)
        heading.setFixedHeight(66)
        top.addWidget(heading, 1)
        top.addWidget(close)
        text = QLabel(body)
        text.setWordWrap(True)
        text.setContentsMargins(24, 14, 24, 12)
        text.setAlignment(Qt.AlignmentFlag.AlignTop)
        text.setMinimumHeight(88)
        cancel = make_button("Отмена")
        cancel.clicked.connect(self.reject)
        ok = make_button(ok_text, "danger")
        ok.clicked.connect(self.accept)
        bottom = QHBoxLayout()
        bottom.setContentsMargins(24, 12, 24, 12)
        bottom.addStretch()
        bottom.addWidget(cancel)
        bottom.addWidget(ok)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addLayout(top)
        layout.addWidget(divider())
        layout.addWidget(text, 1)
        layout.addWidget(divider())
        layout.addLayout(bottom)


def build_dialog(dialog, title: str, body, footer):
    """Каркас окна из макета: заголовок, линия, тело, линия, нижние кнопки."""
    heading = QLabel(title)
    heading.setObjectName("dialogTitle")
    heading.setContentsMargins(24, 0, 24, 0)
    heading.setFixedHeight(64)
    body.setContentsMargins(24, 12, 24, 12)
    footer.setContentsMargins(24, 12, 24, 12)
    footer.setSpacing(8)
    layout = QVBoxLayout(dialog)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(0)
    layout.addWidget(heading)
    layout.addWidget(divider())
    layout.addLayout(body, 1)
    layout.addWidget(divider())
    layout.addLayout(footer)


def confirm(parent, text: str) -> bool:
    """Спрашивает подтверждение. Первая строка текста — заголовок вопроса."""
    title, _, body = text.partition("\n\n")
    ok_text = title.rstrip("?")
    return (
        ConfirmDialog(parent, title, body, ok_text).exec()
        == QDialog.DialogCode.Accepted
    )


def format_dt(value: str) -> str:
    """Дата из базы «2026-10-20 14:05» → «20.10.2026 14:05»."""
    try:
        date, time = value.split(" ")
        year, month, day = date.split("-")
        return f"{day}.{month}.{year} {time}"
    except ValueError:
        return value


def make_chip(level_name: str, difficulty_id: int) -> QLabel:
    """Метка сложности в виде «пилюли» (как Chip в макете)."""
    chip = QLabel(level_name.capitalize())
    chip.setObjectName("chip")
    chip.setAlignment(Qt.AlignmentFlag.AlignCenter)
    background = DIFFICULTY_COLORS.get(difficulty_id, "#F1F5F9")
    color = DIFFICULTY_TEXT.get(difficulty_id, "#64748B")
    chip.setStyleSheet(f"background: {background}; color: {color};")
    return chip


def left_cell(widget) -> QWidget:
    """Ячейка таблицы: виджет у левого края с отступами 16px."""
    cell = QWidget()
    cell_layout = QHBoxLayout(cell)
    cell_layout.setContentsMargins(16, 0, 16, 0)
    cell_layout.addWidget(widget)
    cell_layout.addStretch()
    return cell