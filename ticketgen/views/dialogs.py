"""Диалоговые окна: вопрос, темы, импорт, замена, экспорт, ведомость."""

from pathlib import Path

from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QPlainTextEdit,
    QVBoxLayout,
)

from ticketgen.domain.models import (
    QUESTION_TYPES,
    Question,
    TicketGenError,
)

from ticketgen.views.common import (
    build_dialog,
    confirm,
    fill_table,
    make_button,
    make_table,
    plural,
    set_error,
    show_error,
)


def fill_combo(combo: QComboBox, items, text_of, first_item: str = ""):
    """Заполняет выпадающий список; id объекта хранится в userData."""
    combo.clear()
    if first_item:
        combo.addItem(first_item, None)
    for item in items:
        combo.addItem(text_of(item), item.id)


def ok_cancel_buttons(dialog: QDialog) -> QDialogButtonBox:
    """Кнопки «ОК» и «Отмена», подключённые к диалогу."""
    buttons = QDialogButtonBox(
        QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
    )
    buttons.button(QDialogButtonBox.StandardButton.Ok).setText("Сохранить")
    buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("Отмена")
    buttons.accepted.connect(dialog.accept)
    buttons.rejected.connect(dialog.reject)
    return buttons


class QuestionDialog(QDialog):
    """Добавление и изменение вопроса."""

    def __init__(self, controller, question: Question | None = None, parent=None):
        """Строит форму; если question передан — заполняет её."""
        super().__init__(parent)
        self.controller = controller
        self.question = question
        self.setWindowTitle(
            f"Изменение вопроса № {question.id}" if question else "Новый вопрос"
        )
        self.resize(560, 600)

        self.topic_combo = QComboBox()
        fill_combo(self.topic_combo, controller.get_topics(), lambda t: t.topic_name)
        self.difficulty_combo = QComboBox()
        fill_combo(
            self.difficulty_combo,
            controller.get_difficulties(),
            lambda d: (
                f"{d.level_name.capitalize()} "
                f"({plural(d.weight, ('балл', 'балла', 'баллов'))})"
            ),
        )
        self.type_combo = QComboBox()
        for q_type in QUESTION_TYPES:
            self.type_combo.addItem(q_type.capitalize(), q_type)
        self.text_edit = QPlainTextEdit()
        self.text_edit.setPlaceholderText("Введите текст вопроса…")
        self.text_edit.setMinimumHeight(110)
        self.answer_edit = QPlainTextEdit()
        self.answer_edit.setMinimumHeight(110)
        self.error_label = QLabel("")
        self.error_label.setObjectName("error")
        self.error_label.setVisible(False)
        self.active_check = QCheckBox("Вопрос активен (участвует в генерации)")
        self.active_check.setChecked(True)

        def caption(text: str) -> QLabel:
            label = QLabel(text)
            label.setObjectName("hint")
            return label

        def column(text: str, widget) -> QVBoxLayout:
            box = QVBoxLayout()
            box.setSpacing(4)
            box.addWidget(caption(text))
            box.addWidget(widget)
            return box

        pair = QHBoxLayout()
        pair.setSpacing(16)
        pair.addLayout(column("Сложность *", self.difficulty_combo), 1)
        pair.addLayout(column("Тип *", self.type_combo), 1)
        body = QVBoxLayout()
        body.setSpacing(12)
        body.addLayout(column("Тема *", self.topic_combo))
        body.addLayout(pair)
        body.addLayout(column("Текст вопроса *", self.text_edit))
        body.addWidget(self.error_label)
        body.addLayout(
            column("Эталонный ответ — попадёт только в файл ответов", self.answer_edit)
        )
        body.addWidget(self.active_check)
        cancel = make_button("Отмена")
        cancel.clicked.connect(self.reject)
        save = make_button("Сохранить", "primary")
        save.clicked.connect(self.accept)
        footer = QHBoxLayout()
        footer.addStretch()
        footer.addWidget(cancel)
        footer.addWidget(save)
        build_dialog(self, self.windowTitle(), body, footer)

        if question:
            self._load(question)

    def _load(self, question: Question):
        """Переносит данные вопроса в поля формы."""
        self.topic_combo.setCurrentIndex(self.topic_combo.findData(question.topic_id))
        self.difficulty_combo.setCurrentIndex(
            self.difficulty_combo.findData(question.difficulty_id)
        )
        self.type_combo.setCurrentIndex(self.type_combo.findData(question.q_type))
        self.active_check.setChecked(question.is_active)
        self.text_edit.setPlainText(question.question_text)
        self.answer_edit.setPlainText(question.answer_text)

    def accept(self):
        """Проверяет поля и сохраняет вопрос."""
        text = self.text_edit.toPlainText().strip()
        set_error(self.text_edit, not text)
        if not text:
            self.error_label.setText("Введите текст вопроса")
            self.error_label.setVisible(True)
            return
        if self.topic_combo.currentData() is None:
            show_error(self, "Сначала создайте тему (кнопка «Темы…»).")
            return
        question = Question(
            id=self.question.id if self.question else None,
            topic_id=self.topic_combo.currentData(),
            difficulty_id=self.difficulty_combo.currentData(),
            q_type=self.type_combo.currentData(),
            question_text=text,
            answer_text=self.answer_edit.toPlainText().strip(),
            is_active=self.active_check.isChecked(),
        )
        try:
            self.controller.save_question(question)
        except TicketGenError as error:
            show_error(self, str(error))
            return
        super().accept()


class TopicsDialog(QDialog):
    """Управление темами: добавить, переименовать, удалить (CRUD tbl_topics)."""

    def __init__(self, controller, parent=None):
        """Строит список тем и поля ввода."""
        super().__init__(parent)
        self.controller = controller
        self.setWindowTitle("Темы")
        self.resize(480, 400)
        self.topic_list = QListWidget()
        self.topic_list.currentRowChanged.connect(self._on_select)
        self.discipline_edit = QLineEdit("ОАиП")
        self.name_edit = QLineEdit()
        add_button = make_button("Добавить", "primary")
        rename_button = make_button("Переименовать")
        delete_button = make_button("Удалить", "danger")
        add_button.clicked.connect(self._add)
        rename_button.clicked.connect(self._rename)
        delete_button.clicked.connect(self._delete)

        form = QFormLayout()
        form.addRow("Дисциплина", self.discipline_edit)
        form.addRow("Тема", self.name_edit)
        buttons = QHBoxLayout()
        for button in (add_button, rename_button, delete_button):
            buttons.addWidget(button)
        layout = QVBoxLayout(self)
        layout.addWidget(self.topic_list)
        layout.addLayout(form)
        layout.addLayout(buttons)
        self._refresh()

    def _refresh(self):
        """Перечитывает список тем из базы."""
        self.topics = self.controller.get_topics()
        self.topic_list.clear()
        self.topic_list.addItems([topic.title for topic in self.topics])

    def _on_select(self, row: int):
        """Подставляет выбранную тему в поля ввода."""
        if 0 <= row < len(self.topics):
            self.discipline_edit.setText(self.topics[row].discipline)
            self.name_edit.setText(self.topics[row].topic_name)

    def _values(self):
        """Возвращает (дисциплина, тема) или None, если поле пустое."""
        discipline = self.discipline_edit.text().strip()
        name = self.name_edit.text().strip()
        set_error(self.name_edit, not name)
        set_error(self.discipline_edit, not discipline)
        return (discipline, name) if discipline and name else None

    def _run(self, action):
        """Выполняет действие и показывает ошибку, если она возникла."""
        try:
            action()
        except TicketGenError as error:
            show_error(self, str(error))
        self._refresh()

    def _add(self):
        """Добавляет тему."""
        values = self._values()
        if values:
            self._run(lambda: self.controller.add_topic(*values))

    def _rename(self):
        """Переименовывает выбранную тему."""
        row = self.topic_list.currentRow()
        values = self._values()
        if row >= 0 and values:
            topic = self.topics[row]
            topic.discipline, topic.topic_name = values
            self._run(lambda: self.controller.rename_topic(topic))

    def _delete(self):
        """Удаляет выбранную тему."""
        row = self.topic_list.currentRow()
        if row >= 0 and confirm(self, "Удалить тему?"):
            self._run(lambda: self.controller.delete_topic(self.topics[row].id))


class ImportDialog(QDialog):
    """Импорт вопросов из CSV: выбор файла, загрузка и отчёт в одном окне."""

    def __init__(self, controller, parent=None):
        """Строит окно выбора файла; отчёт появляется ниже после загрузки."""
        super().__init__(parent)
        self.controller = controller
        self.result = None
        self.setWindowTitle("Импорт вопросов из CSV")
        self.setFixedWidth(640)
        self.path_edit = QLineEdit()
        self.path_edit.setPlaceholderText("Выберите CSV-файл…")
        self.path_edit.textChanged.connect(self._reset_state)
        browse = make_button("Обзор…")
        browse.clicked.connect(self._browse)
        path_row = QHBoxLayout()
        path_row.addWidget(self.path_edit, 1)
        path_row.addWidget(browse)
        caption = QLabel("Файл")
        caption.setObjectName("hint")
        format_hint = QLabel(
            "Формат строки: дисциплина;тема;сложность;тип;вопрос;ответ. "
            "Кодировка UTF-8, первая строка — заголовки."
        )
        format_hint.setObjectName("hint")
        format_hint.setWordWrap(True)
        self.error_banner = QLabel()
        self.error_banner.setObjectName("errorBanner")
        self.error_banner.setWordWrap(True)
        self.error_banner.setVisible(False)
        self.ok_banner = QLabel()
        self.ok_banner.setObjectName("success")
        self.ok_banner.setVisible(False)
        self.warn_banner = QLabel()
        self.warn_banner.setObjectName("warning")
        self.warn_banner.setVisible(False)
        self.errors_table = make_table(["Строка", "Ошибка"], stretch_column=1)
        self.errors_table.setVisible(False)
        self.errors_table.verticalHeader().setDefaultSectionSize(40)
        self.errors_table.setFixedHeight(40 * 5)
        body = QVBoxLayout()
        body.setSpacing(8)
        body.addWidget(caption)
        body.addLayout(path_row)
        body.addWidget(format_hint)
        body.addWidget(self.error_banner)
        body.addWidget(self.ok_banner)
        body.addWidget(self.warn_banner)
        body.addWidget(self.errors_table)
        self.report_button = make_button("Сохранить отчёт")
        self.report_button.clicked.connect(self._save_report)
        self.report_button.setVisible(False)
        self.cancel_button = make_button("Отмена")
        self.cancel_button.clicked.connect(self.reject)
        self.load_button = make_button("Загрузить", "primary")
        self.load_button.clicked.connect(self.accept)
        self.load_button.setEnabled(False)
        footer = QHBoxLayout()
        footer.addWidget(self.report_button)
        footer.addStretch()
        footer.addWidget(self.cancel_button)
        footer.addWidget(self.load_button)
        build_dialog(self, "Импорт вопросов из CSV", body, footer)
        self.setFixedHeight(252)

    def _browse(self):
        """Диалог выбора файла."""
        path, _ = QFileDialog.getOpenFileName(
            self, "Импорт вопросов из CSV", "", "CSV-файлы (*.csv)"
        )
        if path:
            self.path_edit.setText(path)

    def _reset_state(self):
        """После смены файла прячет прошлую ошибку и включает «Загрузить»."""
        set_error(self.path_edit, False)
        self.error_banner.setVisible(False)
        self.load_button.setEnabled(bool(self.path_edit.text().strip()))
        self.setFixedHeight(252)

    def accept(self):
        """Загружает файл; при удаче показывает отчёт, и кнопка становится «Готово»."""
        if self.result is not None:
            super().accept()
            return
        path = self.path_edit.text().strip()
        try:
            self.result = self.controller.import_csv(path)
        except (TicketGenError, OSError, UnicodeDecodeError, ValueError) as error:
            self.result = None
            reason = f" ({error})" if isinstance(error, TicketGenError) else ""
            name = Path(path).name
            set_error(self.path_edit, True)
            self.error_banner.setText(
                f"⚠ Не удалось прочитать файл «{name}». Это не CSV-файл или он "
                "повреждён. Сохраните таблицу как «CSV UTF-8 (разделитель ;)» "
                "и выберите файл заново." + reason
            )
            self.error_banner.setVisible(True)
            self.load_button.setEnabled(False)
            self.setFixedHeight(336)
            return
        self._show_report()

    def _show_report(self):
        """Показывает, сколько вопросов загружено и какие строки пропущены."""
        result = self.result
        self.ok_banner.setText(f"✓ Загружено вопросов: {result.imported}")
        self.ok_banner.setVisible(True)
        if result.errors:
            self.warn_banner.setText(
                f"⚠ Пропущено строк с ошибками: {len(result.errors)} — "
                "они не добавлены"
            )
            self.warn_banner.setVisible(True)
            fill_table(self.errors_table, [list(error) for error in result.errors])
            self.errors_table.setVisible(True)
            self.report_button.setVisible(True)
        self.path_edit.setEnabled(False)
        self.cancel_button.setVisible(False)
        self.load_button.setText("Готово")
        self.load_button.setEnabled(True)
        self.setFixedHeight(524 if result.errors else 300)

    def _save_report(self):
        """Сохраняет список ошибок в текстовый файл."""
        name, _ = QFileDialog.getSaveFileName(
            self, "Сохранить отчёт", "отчёт_импорта.txt", "Текст (*.txt)"
        )
        if name:
            lines = [f"Строка {row}: {reason}" for row, reason in self.result.errors]
            Path(name).write_text("\n".join(lines), encoding="utf-8")
