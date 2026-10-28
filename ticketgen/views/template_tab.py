"""Вкладка «Шаблоны»: список шаблонов, правила, балл, проверка банка."""

from PyQt6.QtCore import QSize, Qt, QTimer
from PyQt6.QtGui import QBrush, QColor, QFont
from PyQt6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QSpinBox,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ticketgen.domain.models import TemplateRule, TicketGenError
from ticketgen.logic.scoring import score_formula, ticket_score
from ticketgen.views.common import (
    confirm,
    icon,
    make_button,
    make_table,
    plural,
    show_error,
)
from ticketgen.views.dialogs import QuestionDialog, fill_combo

HEADERS = ["№", "Тема", "Сложность", "Кол-во вопросов", "Баллы всего", "В банке", ""]
TOPIC_COLUMN, LEVEL_COLUMN, COUNT_COLUMN, POINTS_COLUMN = 1, 2, 3, 4
BANK_COLUMN, DELETE_COLUMN = 5, 6
COLUMN_WIDTHS = {0: 56, 2: 200, 3: 200, 4: 160, 5: 224}
GREEN, ORANGE = "#16A34A", "#D97706"
NEW_NAME = "Новый шаблон"
NEW_HEADER = "Экзаменационный билет № {N} по дисциплине «ОАиП»"


def template_summary(template) -> str:
    """Подпись шаблона в списке: «4 правила · 5 вопросов · 9 баллов»."""
    rules = template.rules
    if not rules:
        return "Правил пока нет"
    questions = sum(rule.questions_count for rule in rules)
    return (
        f"{plural(len(rules), ('правило', 'правила', 'правил'))} · "
        f"{plural(questions, ('вопрос', 'вопроса', 'вопросов'))} · "
        f"{plural(ticket_score(rules), ('балл', 'балла', 'баллов'))}"
    )


ADJECTIVES = {"лёгкий": "лёгких", "средний": "средних", "сложный": "сложных"}


def need_text(count: int, level: str) -> str:
    """«2 сложных вопроса», «5 средних вопросов», «1 сложный вопрос»."""
    if count % 10 == 1 and count != 11:
        return f"{count} {level} вопрос"
    adjective = ADJECTIVES.get(level, level)
    return plural(
        count, (f"{adjective} вопрос", f"{adjective} вопроса", f"{adjective} вопросов")
    )


class TemplateTab(QWidget):
    """Шаблоны билетов (View)."""

    def __init__(self, controller, parent=None):
        """Строит список шаблонов слева и редактор правил справа."""
        super().__init__(parent)
        self.controller = controller
        self.templates = []
        self.current = None

        new_button = make_button("+ Новый")
        self.template_list = QListWidget()
        self.template_list.setObjectName("templates")
        list_card = QFrame()
        list_card.setObjectName("card")
        list_card.setFixedWidth(360)
        list_header = QHBoxLayout()
        list_header.addWidget(self._label("Шаблоны", "h2"))
        list_header.addStretch()
        list_header.addWidget(new_button)
        list_layout = QVBoxLayout(list_card)
        list_layout.setContentsMargins(16, 16, 16, 0)
        list_layout.addLayout(list_header)
        list_layout.addWidget(self.template_list)

        self.name_edit = QLineEdit()
        self.header_edit = QLineEdit()
        name_column = QVBoxLayout()
        name_column.setSpacing(4)
        name_column.addWidget(self._label("Название шаблона *", "hint"))
        name_column.addWidget(self.name_edit)
        header_column = QVBoxLayout()
        header_column.setSpacing(4)
        header_column.addWidget(self._label("Заголовок билета", "hint"))
        header_column.addWidget(self.header_edit)
        form = QHBoxLayout()
        form.addLayout(name_column, 1)
        form.addLayout(header_column, 1)

        add_rule_button = make_button("+ Добавить правило")
        rules_header = QHBoxLayout()
        rules_header.addWidget(self._label("Правила билета", "h2"))
        rules_header.addStretch()
        rules_header.addWidget(add_rule_button)
        self.rules_table = make_table(
            HEADERS, stretch_column=DELETE_COLUMN, widths=COLUMN_WIDTHS
        )
        self.rules_table.verticalHeader().setDefaultSectionSize(48)

        self.questions_label = self._label("", "value")
        self.score_label = self._label("", "valueBlue")
        self.formula_label = QLabel()
        summary = QFrame()
        summary.setObjectName("card")
        summary_layout = QHBoxLayout(summary)
        summary_layout.setContentsMargins(24, 16, 24, 16)
        for caption, value in (
            ("Вопросов в билете", self.questions_label),
            ("Суммарный балл", self.score_label),
            ("Как считается", self.formula_label),
        ):
            column = QVBoxLayout()
            column.setSpacing(4)
            column.addWidget(self._label(caption, "hint"))
            column.addWidget(value)
            holder = QWidget()
            holder.setLayout(column)
            holder.setFixedWidth(320)
            summary_layout.addWidget(holder)
        summary_layout.addStretch()

        self.banner = QLabel()
        self.banner.setWordWrap(True)
        self.add_questions_button = make_button("Добавить вопросы →", "link")
        banner_row = QHBoxLayout()
        banner_row.addWidget(self.banner, 1)
        banner_row.addWidget(self.add_questions_button)

        self.delete_button = make_button("Удалить шаблон", "danger")
        cancel_button = make_button("Отменить")
        self.save_button = make_button("Сохранить", "primary")
        bottom = QHBoxLayout()
        bottom.addWidget(self.delete_button)
        bottom.addStretch()
        bottom.addWidget(cancel_button)
        bottom.addWidget(self.save_button)

        right = QVBoxLayout()
        right.setSpacing(16)
        right.addLayout(form)
        right.addLayout(rules_header)
        right.addWidget(self.rules_table)
        right.addWidget(summary)
        right.addLayout(banner_row)
        right.addStretch()
        right.addLayout(bottom)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 16)
        layout.setSpacing(16)
        layout.addWidget(list_card)
        layout.addLayout(right, 1)

        self.template_list.currentRowChanged.connect(self.show_template)
        new_button.clicked.connect(self.new_template)
        self.delete_button.clicked.connect(self.delete_template)
        self.save_button.clicked.connect(self.save_template)
        cancel_button.clicked.connect(lambda: self.show_template(self._row()))
        add_rule_button.clicked.connect(self.add_rule)
        self.add_questions_button.clicked.connect(
            lambda: QuestionDialog(self.controller, parent=self).exec()
        )
        controller.templates_changed.connect(self.refresh)
        controller.questions_changed.connect(self.refresh)
        self.refresh()

    @staticmethod
    def _label(text: str, name: str) -> QLabel:
        """Подпись с именем стиля (hint, h2, value...)."""
        label = QLabel(text)
        label.setObjectName(name)
        return label

    def _row(self) -> int:
        """Номер строки выбранного шаблона в списке (−1, если нет)."""
        return self.template_list.currentRow()

    def refresh(self):
        """Перечитывает шаблоны, сохраняя выбранный."""
        selected_id = self.current.id if self.current else None
        self.templates = self.controller.get_templates()
        self.template_list.blockSignals(True)
        self.template_list.clear()
        for template in self.templates:
            self._add_list_item(template)
        self.template_list.blockSignals(False)
        ids = [template.id for template in self.templates]
        row = ids.index(selected_id) if selected_id in ids else 0
        if self.templates:
            self.template_list.setCurrentRow(row)
        self.show_template(row if self.templates else -1)

    def _add_list_item(self, template):
        """Добавляет в список карточку шаблона: название и подпись."""
        item = QListWidgetItem()
        item.setSizeHint(QSize(0, 66))
        self.template_list.addItem(item)
        holder = QWidget()
        holder.setObjectName("templateItem")
        column = QVBoxLayout(holder)
        column.setContentsMargins(13, 12, 12, 12)
        column.setSpacing(2)
        column.addWidget(self._label(template.template_name, "itemTitle"))
        column.addWidget(self._label(template_summary(template), "hint"))
        self.template_list.setItemWidget(item, holder)

    def show_template(self, row: int):
        """Показывает правила, балл и сообщение о банке для шаблона."""
        self.current = self.templates[row] if 0 <= row < len(self.templates) else None
        template = self.current
        self.name_edit.setText(template.template_name if template else "")
        self.header_edit.setText(template.header_text if template else "")
        rules = template.rules if template else []
        checks, _ = self.controller.check_template(template) if template else ([], 0)
        self._fill_rules(checks)
        self.questions_label.setText(
            str(sum(rule.questions_count for rule in rules)) if template else ""
        )
        self.score_label.setText(str(ticket_score(rules)) if template else "")
        self.formula_label.setText(score_formula(rules) if rules else "—")
        self.save_button.setEnabled(bool(rules))
        self.delete_button.setEnabled(template is not None)
        self._show_banner(checks)

    def _show_banner(self, checks):
        """Сообщение под итогами: хватает ли вопросов в банке."""
        problems = [
            f"Правило {number}: нужно {need_text(c.required, c.rule.level_name)} "
            f"по теме «{c.rule.topic_name}», в банке только {c.available}."
            for number, c in enumerate(checks, 1)
            if not c.ok
        ]
        self.add_questions_button.setVisible(bool(problems))
        self.banner.setVisible(bool(checks))
        if problems:
            self.banner.setObjectName("warning")
            text = (
                "⚠ "
                + " ".join(problems)
                + " Добавьте вопросы или уменьшите количество."
            )
        elif len(checks) == 1:
            check = checks[0]
            self.banner.setObjectName("success")
            text = (
                "✓ Вопросов в банке хватает: нужно "
                f"{need_text(check.required, check.rule.level_name)} "
                f"по теме «{check.rule.topic_name}», в банке {check.available}."
            )
        else:
            self.banner.setObjectName("success")
            text = "✓ Вопросов в банке хватает по всем правилам"
        self.banner.setText(text)
        self.banner.style().unpolish(self.banner)
        self.banner.style().polish(self.banner)

    def _fill_rules(self, checks):
        """Заполняет таблицу правил: поля прямо в строках, как в макете."""
        table = self.rules_table
        table.clearContents()
        table.clearSpans()
        table.setRowCount(max(1, len(checks)))
        table.setFixedHeight(42 + 48 * max(1, len(checks)))
        if not checks:
            hint = QTableWidgetItem(
                "Правил пока нет. Нажмите «+ Добавить правило» и выберите тему, "
                "сложность и количество вопросов."
            )
            hint.setFlags(Qt.ItemFlag.NoItemFlags)
            hint.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            hint.setForeground(QBrush(QColor("#64748B")))
            table.setItem(0, 0, hint)
            table.setSpan(0, 0, 1, len(HEADERS))
            return
        topics = self.controller.get_topics()
        levels = self.controller.get_difficulties()
        for row, check in enumerate(checks):
            rule = check.rule
            if check.ok:
                bank_text, color = f"{check.available}", GREEN
            else:
                bank_text, color = f"⚠ {check.available} из {check.required}", ORANGE
            values = {
                0: row + 1,
                POINTS_COLUMN: rule.questions_count * rule.weight,
                BANK_COLUMN: bank_text,
            }
            for column, value in values.items():
                table.setItem(row, column, QTableWidgetItem(str(value)))
            bank_item = table.item(row, BANK_COLUMN)
            bank_item.setForeground(QBrush(QColor(color)))
            font = QFont(bank_item.font())
            font.setBold(True)
            bank_item.setFont(font)

            topic_combo = QComboBox()
            fill_combo(topic_combo, topics, lambda t: t.topic_name)
            topic_combo.setCurrentIndex(max(0, topic_combo.findData(rule.topic_id)))
            level_combo = QComboBox()
            fill_combo(level_combo, levels, lambda d: d.level_name.capitalize())
            level_combo.setCurrentIndex(
                max(0, level_combo.findData(rule.difficulty_id))
            )
            for combo in (topic_combo, level_combo):
                combo.activated.connect(
                    lambda _, r=rule, t=topic_combo, v=level_combo: self._target_edited(
                        r, t.currentData(), v.currentData()
                    )
                )
            table.setCellWidget(row, TOPIC_COLUMN, self._cell(topic_combo, True))
            table.setCellWidget(row, LEVEL_COLUMN, self._cell(level_combo, True))

            spin = QSpinBox()
            spin.setRange(1, 50)
            spin.setValue(rule.questions_count)
            spin.setFixedWidth(80)
            spin.setButtonSymbols(QSpinBox.ButtonSymbols.NoButtons)
            spin.editingFinished.connect(
                lambda r=rule, s=spin: self._count_edited(r, s.value())
            )
            table.setCellWidget(row, COUNT_COLUMN, self._cell(spin))
            delete_button = make_button("", "link", "Удалить правило")
            delete_button.setIcon(icon("trash"))
            delete_button.clicked.connect(lambda _, r=rule: self.delete_rule(r))
            table.setCellWidget(row, DELETE_COLUMN, self._cell(delete_button))

    @staticmethod
    def _cell(widget, stretch: bool = False) -> QWidget:
        """Оборачивает поле в ячейку с отступами 16px, как в макете."""
        cell = QWidget()
        cell_layout = QHBoxLayout(cell)
        cell_layout.setContentsMargins(16, 0, 16, 0)
        cell_layout.addWidget(widget)
        if not stretch:
            cell_layout.addStretch()
        return cell

    def _run(self, action):
        """Выполняет действие контроллера и показывает ошибку, если она есть."""
        try:
            action()
        except TicketGenError as error:
            show_error(self, str(error))
            self.refresh()

    def _count_edited(self, rule, count: int):
        """Сохраняет новое количество вопросов (после выхода из обработчика)."""
        if count != rule.questions_count:
            QTimer.singleShot(
                0,
                lambda: self._run(
                    lambda: self.controller.update_rule_count(rule.id, count)
                ),
            )

    def _target_edited(self, rule, topic_id: int, difficulty_id: int):
        """Сохраняет новую тему или сложность правила."""
        QTimer.singleShot(
            0,
            lambda: self._run(
                lambda: self.controller.update_rule_target(
                    rule.id, topic_id, difficulty_id
                )
            ),
        )

    def new_template(self):
        """Создаёт шаблон «Новый шаблон» и выбирает его."""
        names = {template.template_name for template in self.templates}
        name, number = NEW_NAME, 1
        while name in names:
            number += 1
            name = f"{NEW_NAME} {number}"
        try:
            template_id = self.controller.create_template(name, NEW_HEADER)
        except TicketGenError as error:
            show_error(self, str(error))
            return
        ids = [template.id for template in self.templates]
        self.template_list.setCurrentRow(ids.index(template_id))

    def save_template(self):
        """Сохраняет название и заголовок."""
        if not self.current:
            return
        name = self.name_edit.text().strip()
        if not name:
            show_error(self, "Введите название шаблона.")
            return
        self.current.template_name = name
        self.current.header_text = self.header_edit.text().strip()
        self._run(lambda: self.controller.update_template(self.current))

    def delete_template(self):
        """Удаляет выбранный шаблон."""
        if not self.current:
            return
        text = (
            f"Удалить шаблон?\n\nШаблон «{self.current.template_name}» и его "
            f"{plural(len(self.current.rules), ('правило', 'правила', 'правил'))} "
            "будут удалены. Серии билетов, созданные по этому шаблону, останутся "
            "на вкладке «Результаты»."
        )
        if confirm(self, text):
            template_id = self.current.id
            self.current = None
            self._run(lambda: self.controller.delete_template(template_id))

    def add_rule(self):
        """Добавляет правило: первая свободная пара «тема + сложность»."""
        if not self.current:
            return
        used = {(r.topic_id, r.difficulty_id) for r in self.current.rules}
        for topic in self.controller.get_topics():
            for level in self.controller.get_difficulties():
                if (topic.id, level.id) not in used:
                    rule = TemplateRule(None, self.current.id, topic.id, level.id, 1)
                    self._run(lambda: self.controller.add_rule(rule))
                    return
        show_error(self, "Все сочетания темы и сложности уже есть в шаблоне.")

    def delete_rule(self, rule):
        """Удаляет правило после подтверждения."""
        if confirm(self, "Удалить правило?"):
            self._run(lambda: self.controller.delete_rule(rule.id))
