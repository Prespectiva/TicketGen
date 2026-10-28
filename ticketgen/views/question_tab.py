"""Вкладка «Банк вопросов»: поиск, фильтры, таблица, страницы, импорт."""

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QBrush, QColor
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ticketgen.domain.models import QUESTION_TYPES, TicketGenError
from ticketgen.views.common import (
    confirm,
    icon,
    left_cell,
    make_button,
    make_chip,
    make_table,
    plural,
    show_error,
)
from ticketgen.views.dialogs import (
    ImportDialog,
    QuestionDialog,
    TopicsDialog,
    fill_combo,
)
from ticketgen.views.styles import INACTIVE_TEXT

HEADERS = ["№", "Текст вопроса", "Тема", "Сложность", "Тип", "Активен", "Действия"]
TEXT_COLUMN, DIFFICULTY_COLUMN, ACTIVE_COLUMN, ACTIONS_COLUMN = 1, 3, 5, 6
PAGE_SIZE = 15
COLUMN_WIDTHS = {0: 56, 2: 320, 3: 160, 4: 160, 5: 110, 6: 146}


def page_numbers(current: int, pages: int) -> list:
    """Номера кнопок страниц; None обозначает многоточие.

    Пример: page_numbers(1, 17) → [1, 2, 3, None, 17].
    """
    first = max(1, min(current - 1, pages - 2))
    shown = sorted({1, pages, *range(first, first + 3)} & set(range(1, pages + 1)))
    result = []
    for number in shown:
        if result and number - result[-1] > 1:
            result.append(None)
        result.append(number)
    return result


class QuestionTab(QWidget):
    """Банк вопросов (View). Данные получает только через контроллер."""

    def __init__(self, controller, parent=None):
        """Строит элементы вкладки и подписывается на сигналы контроллера."""
        super().__init__(parent)
        self.controller = controller
        self.questions = []  # вопросы текущей страницы
        self.page = 1

        title = QLabel("Банк вопросов")
        title.setObjectName("title")
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Поиск по тексту вопроса…")
        self.search_edit.addAction(
            icon("search"), QLineEdit.ActionPosition.LeadingPosition
        )
        self.search_edit.setFixedWidth(560)
        self.topic_filter = QComboBox()
        self.difficulty_filter = QComboBox()
        self.type_filter = QComboBox()
        self.type_filter.addItem("Все типы", None)
        for q_type in QUESTION_TYPES:
            self.type_filter.addItem(q_type.capitalize(), q_type)
        self.topic_filter.setFixedWidth(296)
        self.difficulty_filter.setFixedWidth(216)
        self.type_filter.setFixedWidth(216)
        self.inactive_check = QCheckBox("Показывать отключённые")
        self.inactive_check.setChecked(True)
        reset_button = make_button("Сбросить фильтры", "link")

        topics_button = make_button("Темы…")
        import_button = make_button("Импорт CSV")
        add_button = make_button("+ Добавить вопрос", "primary")
        self.table = make_table(
            HEADERS, stretch_column=TEXT_COLUMN, widths=COLUMN_WIDTHS
        )
        self.table.verticalHeader().setDefaultSectionSize(48)
        self.empty_label = QLabel(
            "Ничего не найдено\nИзмените фильтры или добавьте новый вопрос."
        )
        self.empty_label.setObjectName("hint")
        self.empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.found_label = QLabel()
        self.found_label.setObjectName("hint")
        self.pages_row = QHBoxLayout()

        top_row = QHBoxLayout()
        top_row.addWidget(title)
        top_row.addStretch()
        for button in (topics_button, import_button, add_button):
            top_row.addWidget(button)
        filter_row = QHBoxLayout()
        filter_row.addWidget(self.search_edit)
        for combo in (self.topic_filter, self.difficulty_filter, self.type_filter):
            filter_row.addWidget(combo)
        filter_row.addSpacing(8)
        filter_row.addWidget(self.inactive_check)
        filter_row.addStretch()
        filter_row.addWidget(reset_button)
        bottom_row = QHBoxLayout()
        bottom_row.addWidget(self.found_label)
        bottom_row.addStretch()
        bottom_row.addLayout(self.pages_row)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 16)
        layout.setSpacing(16)
        layout.addLayout(top_row)
        layout.addLayout(filter_row)
        layout.addWidget(self.table)
        layout.addWidget(self.empty_label)
        layout.addLayout(bottom_row)

        self.search_edit.textChanged.connect(self.filters_changed)
        for combo in (self.topic_filter, self.difficulty_filter, self.type_filter):
            combo.currentIndexChanged.connect(self.filters_changed)
        self.inactive_check.toggled.connect(self.filters_changed)
        reset_button.clicked.connect(self.reset_filters)
        topics_button.clicked.connect(self.open_topics)
        import_button.clicked.connect(self.import_csv)
        add_button.clicked.connect(self.add_question)
        self.table.cellDoubleClicked.connect(lambda row, _: self.edit_question(row))
        self.table.itemChanged.connect(self.on_item_changed)
        controller.questions_changed.connect(self.refresh)
        self.refresh()

    def refresh(self):
        """Обновляет списки фильтров и таблицу (вызывается по сигналу)."""
        self._reload_combo(
            self.topic_filter,
            self.controller.get_topics(),
            lambda t: t.topic_name,
            "Все темы",
        )
        self._reload_combo(
            self.difficulty_filter,
            self.controller.get_difficulties(),
            lambda d: d.level_name,
            "Любая сложность",
        )
        self.refresh_table()

    @staticmethod
    def _reload_combo(combo, items, text_of, first_item):
        """Перезаполняет фильтр, сохраняя выбранное значение."""
        current = combo.currentData()
        combo.blockSignals(True)
        fill_combo(combo, items, text_of, first_item)
        combo.setCurrentIndex(max(0, combo.findData(current)))
        combo.blockSignals(False)

    def filters_changed(self):
        """Любой фильтр изменился: возвращаемся на первую страницу."""
        self.page = 1
        self.refresh_table()

    def reset_filters(self):
        """Сбрасывает поиск и все фильтры."""
        for widget in (self.search_edit, self.topic_filter, self.difficulty_filter):
            widget.blockSignals(True)
        self.search_edit.clear()
        self.topic_filter.setCurrentIndex(0)
        self.difficulty_filter.setCurrentIndex(0)
        self.type_filter.setCurrentIndex(0)
        self.inactive_check.setChecked(True)
        for widget in (self.search_edit, self.topic_filter, self.difficulty_filter):
            widget.blockSignals(False)
        self.filters_changed()

    def refresh_table(self):
        """Ищет вопросы по фильтрам и заполняет таблицу текущей страницы."""
        found = self.controller.find_questions(
            text=self.search_edit.text().strip(),
            topic_id=self.topic_filter.currentData(),
            difficulty_id=self.difficulty_filter.currentData(),
            q_type=self.type_filter.currentData(),
            only_active=not self.inactive_check.isChecked(),
        )
        pages = max(1, -(-len(found) // PAGE_SIZE))
        self.page = min(self.page, pages)
        start = (self.page - 1) * PAGE_SIZE
        self.questions = found[start : start + PAGE_SIZE]

        self.table.blockSignals(True)
        self.table.setRowCount(len(self.questions))
        for row, question in enumerate(self.questions):
            self._fill_row(row, start + row + 1, question)
        self.table.blockSignals(False)

        self.empty_label.setVisible(not found)
        self.table.setVisible(bool(found))
        if found:
            self.found_label.setText(
                f"Найдено: {plural(len(found), ('вопрос', 'вопроса', 'вопросов'))}"
                f" · показаны {start + 1}–{start + len(self.questions)}"
                f" · страница {self.page} из {pages}"
            )
        else:
            self.found_label.setText("Найдено: 0 вопросов")
        self._build_pages(pages)

    def _fill_row(self, row: int, number: int, question):
        """Заполняет одну строку таблицы."""
        values = [
            number,
            question.question_text,
            question.topic_name,
            question.level_name,
            question.q_type.capitalize(),
        ]
        for column, value in enumerate(values):
            item = QTableWidgetItem(str(value))
            if not question.is_active:
                item.setForeground(QBrush(QColor(INACTIVE_TEXT)))
            self.table.setItem(row, column, item)
        self.table.item(row, DIFFICULTY_COLUMN).setText("")
        chip = make_chip(question.level_name, question.difficulty_id)
        self.table.setCellWidget(row, DIFFICULTY_COLUMN, left_cell(chip))
        active = QTableWidgetItem()
        active.setFlags(
            Qt.ItemFlag.ItemIsEnabled
            | Qt.ItemFlag.ItemIsSelectable
            | Qt.ItemFlag.ItemIsUserCheckable
        )
        active.setCheckState(
            Qt.CheckState.Checked if question.is_active else Qt.CheckState.Unchecked
        )
        self.table.setItem(row, ACTIVE_COLUMN, active)

        edit_button = make_button("", "link", "Изменить вопрос")
        edit_button.setIcon(icon("pencil"))
        delete_button = make_button("", "link", "Удалить вопрос")
        delete_button.setIcon(icon("trash"))
        edit_button.clicked.connect(lambda _, r=row: self.edit_question(r))
        delete_button.clicked.connect(lambda _, r=row: self.delete_question(r))
        cell = QWidget()
        cell_layout = QHBoxLayout(cell)
        cell_layout.setContentsMargins(16, 0, 16, 0)
        cell_layout.setSpacing(16)
        cell_layout.addStretch()
        cell_layout.addWidget(edit_button)
        cell_layout.addWidget(delete_button)
        self.table.setItem(row, ACTIONS_COLUMN, QTableWidgetItem())
        self.table.setCellWidget(row, ACTIONS_COLUMN, cell)

    def _build_pages(self, pages: int):
        """Перестраивает кнопки страниц под таблицей."""
        while self.pages_row.count():
            widget = self.pages_row.takeAt(0).widget()
            if widget:
                widget.deleteLater()
        if pages <= 1:
            return
        prev_button = make_button("‹")
        prev_button.setEnabled(self.page > 1)
        prev_button.clicked.connect(lambda: self.go_to_page(self.page - 1))
        self.pages_row.addWidget(prev_button)
        for number in page_numbers(self.page, pages):
            if number is None:
                self.pages_row.addWidget(QLabel("…"))
                continue
            button = make_button(str(number), "primary" if number == self.page else "")
            button.clicked.connect(lambda _, n=number: self.go_to_page(n))
            self.pages_row.addWidget(button)
        next_button = make_button("›")
        next_button.setEnabled(self.page < pages)
        next_button.clicked.connect(lambda: self.go_to_page(self.page + 1))
        self.pages_row.addWidget(next_button)

    def go_to_page(self, number: int):
        """Переходит на страницу таблицы."""
        self.page = number
        self.refresh_table()

    def on_item_changed(self, item):
        """Флажок «Активен» в таблице: включает или отключает вопрос."""
        if item.column() == ACTIVE_COLUMN and 0 <= item.row() < len(self.questions):
            self.controller.toggle_question(self.questions[item.row()])

    def open_topics(self):
        """Открывает окно управления темами."""
        TopicsDialog(self.controller, self).exec()

    def add_question(self):
        """Открывает окно нового вопроса."""
        QuestionDialog(self.controller, parent=self).exec()

    def edit_question(self, row: int):
        """Открывает окно изменения вопроса из строки row."""
        if 0 <= row < len(self.questions):
            QuestionDialog(self.controller, self.questions[row], self).exec()

    def delete_question(self, row: int):
        """Удаляет вопрос из строки row после подтверждения."""
        if not 0 <= row < len(self.questions):
            return
        question = self.questions[row]
        text = (
            f"Удалить вопрос?\n\nВопрос «{question.question_text}» будет удалён "
            "из банка. В уже созданных сериях он останется. Если вопрос может "
            "понадобиться позже, лучше снимите флажок «Активен»."
        )
        if confirm(self, text):
            try:
                self.controller.delete_question(question.id)
            except TicketGenError as error:
                show_error(self, f"{error}\nВместо удаления вопрос можно отключить.")

    def import_csv(self):
        """Открывает окно импорта вопросов из CSV."""
        ImportDialog(self.controller, self).exec()
