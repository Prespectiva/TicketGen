"""Диалоговые окна: вопрос, темы, импорт, замена, экспорт, ведомость."""

import random
from pathlib import Path

from PyQt6.QtCore import QSize, Qt, QUrl
from PyQt6.QtGui import QDesktopServices, QTextDocument
from PyQt6.QtPrintSupport import QPrintDialog, QPrinter
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
    QListWidgetItem,
    QPlainTextEdit,
    QProgressBar,
    QRadioButton,
    QVBoxLayout,
    QWidget,
)

from ticketgen.domain.models import (
    QUESTION_TYPES,
    Question,
    TicketGenError,
)
from ticketgen.logic.exporters import ExporterFactory, build_summary, export_series
from ticketgen.views.common import (
    build_dialog,
    confirm,
    divider,
    fill_table,
    make_button,
    make_table,
    plural,
    set_error,
    show_error,
)
from ticketgen.workers.background_worker import BackgroundWorker


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
        """Строит форму; если question передан --- заполняет её."""
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
        self.text_edit.setPlaceholderText("Введите текст вопроса...")
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
            column(
                "Эталонный ответ --- попадёт только в файл ответов", self.answer_edit
            )
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
            show_error(self, "Сначала создайте тему (кнопка «Темы...»).")
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
        self.path_edit.setPlaceholderText("Выберите CSV-файл...")
        self.path_edit.textChanged.connect(self._reset_state)
        browse = make_button("Обзор...")
        browse.clicked.connect(self._browse)
        path_row = QHBoxLayout()
        path_row.addWidget(self.path_edit, 1)
        path_row.addWidget(browse)
        caption = QLabel("Файл")
        caption.setObjectName("hint")
        format_hint = QLabel(
            "Формат строки: дисциплина;тема;сложность;тип;вопрос;ответ. "
            "Кодировка UTF-8, первая строка --- заголовки."
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
                f"⚠ Пропущено строк с ошибками: {len(result.errors)} --- "
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


def used_text(count: int) -> str:
    """«не используется», «в 1 билете», «в 4 билетах»."""
    if count == 0:
        return "не используется"
    return f"в {count} " + ("билете" if count % 10 == 1 and count != 11 else "билетах")


class ReplaceQuestionDialog(QDialog):
    """Выбор вопроса для замены; usage --- в скольких билетах серии он уже есть."""

    def __init__(
        self, number, variant_no, old_question, candidates, usage, parent=None
    ):
        """Показывает вопросы той же темы и сложности с числом использований."""
        super().__init__(parent)
        self.setWindowTitle(f"Замена вопроса {number} в билете № {variant_no}")
        self.resize(640, 520)
        self.selected = None
        self.radios = []
        title = QLabel(f"Замена вопроса {number} в билете № {variant_no}")
        title.setObjectName("dialogTitle")
        title.setContentsMargins(24, 0, 24, 0)
        title.setFixedHeight(64)
        current = QLabel(old_question.question_text)
        current.setObjectName("questionCard")
        current.setWordWrap(True)
        current.setContentsMargins(12, 14, 12, 14)
        self.list_widget = QListWidget()
        self.list_widget.setObjectName("choices")
        for question in candidates:
            self._add_choice(question, used_text(usage.get(question.id, 0)))
        self.list_widget.currentRowChanged.connect(self._sync_radios)
        self.list_widget.itemDoubleClicked.connect(lambda _: self.accept())
        random_button = make_button("Случайный вопрос")
        random_button.clicked.connect(self.pick_random)
        cancel = make_button("Отмена")
        cancel.clicked.connect(self.reject)
        self.ok_button = make_button("Заменить", "primary")
        self.ok_button.setEnabled(False)
        self.ok_button.clicked.connect(self.accept)
        footer = QHBoxLayout()
        footer.setContentsMargins(24, 12, 24, 12)
        footer.setSpacing(8)
        footer.addWidget(random_button)
        footer.addStretch()
        footer.addWidget(cancel)
        footer.addWidget(self.ok_button)
        body = QVBoxLayout()
        body.setContentsMargins(24, 12, 24, 12)
        body.setSpacing(8)
        body.addWidget(self._hint("Сейчас в билете"))
        body.addWidget(current)
        body.addSpacing(8)
        body.addWidget(
            self._hint(
                f"Можно заменить на (тема «{old_question.topic_name}», "
                f"сложность «{old_question.level_name.lower()}»)"
            )
        )
        body.addWidget(self.list_widget, 1)
        body.addWidget(
            self._hint("Вопросы, которые уже есть в этом билете, не показываются.")
        )
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(title)
        layout.addWidget(divider())
        layout.addLayout(body, 1)
        layout.addWidget(divider())
        layout.addLayout(footer)

    def _add_choice(self, question, note: str):
        """Строка списка: радиокнопка с текстом вопроса и серая пометка справа."""
        item = QListWidgetItem()
        item.setSizeHint(QSize(0, 48))
        item.setData(Qt.ItemDataRole.UserRole, question)
        self.list_widget.addItem(item)
        holder = QWidget()
        holder.setObjectName("templateItem")
        row = QHBoxLayout(holder)
        row.setContentsMargins(12, 0, 16, 0)
        radio = QRadioButton(question.question_text)
        radio.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        tail = QLabel(note)
        tail.setObjectName("hint")
        row.addWidget(radio, 1)
        row.addWidget(tail)
        self.radios.append(radio)
        self.list_widget.setItemWidget(item, holder)

    def _sync_radios(self, row: int):
        """Отмечает радиокнопку выбранной строки."""
        for index, radio in enumerate(self.radios):
            radio.setChecked(index == row)
        self.ok_button.setEnabled(row >= 0)

    def pick_random(self):
        """Выбирает случайный вопрос из списка."""
        if self.radios:
            self.list_widget.setCurrentRow(random.randrange(len(self.radios)))

    @staticmethod
    def _hint(text: str) -> QLabel:
        """Серая подпись."""
        label = QLabel(text)
        label.setObjectName("hint")
        label.setWordWrap(True)
        return label

    def accept(self):
        """Запоминает выбранный вопрос."""
        item = self.list_widget.currentItem()
        if item is None:
            show_error(self, "Выберите вопрос из списка.")
            return
        self.selected = item.data(Qt.ItemDataRole.UserRole)
        super().accept()


class ExportDialog(QDialog):
    """Настройки экспорта серии: формат, что сохранить, папка."""

    def __init__(
        self, folder: Path, base_name: str, subtitle: str, header, variants, parent=None
    ):
        """Строит окно экспорта; сам запускает сохранение файлов в потоке."""
        super().__init__(parent)
        self.setWindowTitle("Экспорт серии")
        self.resize(560, 524)
        self.base_name = base_name
        self.header = header
        self.variants = variants
        self.worker = None
        self.files = []
        sub = QLabel(subtitle)
        sub.setObjectName("subtitle")
        self.docx_radio = QRadioButton("DOCX (Word)")
        self.pdf_radio = QRadioButton("PDF")
        self.both_radio = QRadioButton("DOCX и PDF")
        self.docx_radio.setChecked(True)
        self.tickets_check = QCheckBox("Билеты (без ответов)")
        self.tickets_check.setChecked(True)
        self.answers_check = QCheckBox("Файл ответов для преподавателя --- отдельно")
        self.answers_check.setChecked(True)
        self.summary_check = QCheckBox("Сводная ведомость")
        self.folder_edit = QLineEdit(str(folder))
        browse_button = make_button("Обзор...")
        browse_button.clicked.connect(self._browse)
        self.files_label = QLabel()
        self.files_label.setObjectName("hint")
        self.files_label.setWordWrap(True)

        format_row = QHBoxLayout()
        format_row.setSpacing(32)
        for radio in (self.docx_radio, self.pdf_radio, self.both_radio):
            format_row.addWidget(radio)
        format_row.addStretch()
        folder_row = QHBoxLayout()
        folder_row.addWidget(self.folder_edit)
        folder_row.addWidget(browse_button)
        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        folder_caption = QLabel("Папка")
        folder_caption.setObjectName("hint")
        body = QVBoxLayout()
        body.setSpacing(8)
        body.addWidget(sub)
        body.addSpacing(4)
        body.addWidget(self._caption("Формат"))
        body.addLayout(format_row)
        body.addSpacing(8)
        body.addWidget(self._caption("Что сохранить"))
        for check in (self.tickets_check, self.answers_check, self.summary_check):
            body.addWidget(check)
        body.addSpacing(8)
        body.addWidget(folder_caption)
        body.addLayout(folder_row)
        body.addWidget(self.files_label)
        self.status_label = QLabel()
        self.status_label.setObjectName("hint")
        self.status_label.setVisible(False)
        self.result_label = QLabel()
        self.result_label.setObjectName("success")
        self.result_label.setVisible(False)
        body.addWidget(self.status_label)
        body.addWidget(self.result_label)
        body.addStretch()
        body.addWidget(self.progress_bar)
        self.cancel_button = make_button("Отмена")
        self.cancel_button.clicked.connect(self.reject)
        self.export_button = make_button("Экспортировать", "primary")
        self.export_button.clicked.connect(self.accept)
        self.open_button = make_button("Открыть папку")
        self.open_button.clicked.connect(self._open_folder)
        self.open_button.setVisible(False)
        footer = QHBoxLayout()
        footer.addStretch()
        footer.addWidget(self.open_button)
        footer.addWidget(self.cancel_button)
        footer.addWidget(self.export_button)
        self.controls = [
            self.docx_radio,
            self.pdf_radio,
            self.both_radio,
            self.tickets_check,
            self.answers_check,
            self.summary_check,
            self.folder_edit,
            browse_button,
        ]
        build_dialog(self, "Экспорт серии", body, footer)
        for widget in (
            self.docx_radio,
            self.pdf_radio,
            self.both_radio,
            self.tickets_check,
            self.answers_check,
            self.summary_check,
        ):
            widget.toggled.connect(self._update_files)
        self._update_files()

    @staticmethod
    def _caption(text: str) -> QLabel:
        """Жирная подпись раздела."""
        label = QLabel(text)
        label.setObjectName("caption")
        return label

    def formats(self) -> list[str]:
        """Выбранные форматы."""
        if self.both_radio.isChecked():
            return ["docx", "pdf"]
        return ["pdf"] if self.pdf_radio.isChecked() else ["docx"]

    def _update_files(self):
        """Показывает имена файлов, которые будут созданы."""
        names = []
        for fmt in self.formats():
            if self.tickets_check.isChecked():
                names.append(f"{self.base_name}_билеты.{fmt}")
        first = self.formats()[0]
        if self.answers_check.isChecked():
            names.append(f"{self.base_name}_ответы.{first}")
        if self.summary_check.isChecked():
            names.append(f"{self.base_name}_ведомость.{first}")
        self.files_label.setText("Будут созданы: " + ", ".join(names))

    def _browse(self):
        """Выбор папки для сохранения."""
        folder = QFileDialog.getExistingDirectory(
            self, "Папка", self.folder_edit.text()
        )
        if folder:
            self.folder_edit.setText(folder)

    def accept(self):
        """Запускает экспорт; после успеха кнопка превращается в «Готово»."""
        if self.worker is not None:
            return
        if self.files:
            super().accept()
            return
        if not (
            self.tickets_check.isChecked()
            or self.answers_check.isChecked()
            or self.summary_check.isChecked()
        ):
            show_error(self, "Отметьте, что нужно сохранить.")
            return
        self.worker = BackgroundWorker(
            export_series,
            Path(self.folder_edit.text()),
            self.base_name,
            self.header,
            self.variants,
            self.formats(),
            self.answers_check.isChecked(),
            self.summary_check.isChecked(),
            with_tickets=self.tickets_check.isChecked(),
        )
        self.worker.progress.connect(self._on_progress)
        self.worker.finished_ok.connect(self._on_done)
        self.worker.failed.connect(self._on_failed)
        for widget in self.controls:
            widget.setEnabled(False)
        self.export_button.setEnabled(False)
        self.files_label.setVisible(False)
        self.result_label.setVisible(False)
        self.status_label.setVisible(True)
        self._on_progress(0)
        self.worker.start()

    def _on_progress(self, percent: int):
        """Показывает ход сохранения."""
        total = len(self.variants)
        self.progress_bar.setValue(percent)
        self.status_label.setText(
            f"Сохранение файлов... билет {total * percent // 100} из {total}"
        )

    def _on_done(self, files):
        """Показывает зелёную плашку и кнопки «Открыть папку» / «Готово»."""
        self.worker = None
        self.files = list(files)
        self.progress_bar.setValue(100)
        self.status_label.setVisible(False)
        self.result_label.setText(f"✓ Сохранено файлов: {len(self.files)}")
        self.result_label.setVisible(True)
        self.open_button.setVisible(True)
        self.cancel_button.setVisible(False)
        self.export_button.setText("Готово")
        self.export_button.setEnabled(True)

    def _on_failed(self, message: str):
        """Возвращает окно в исходный вид и показывает ошибку."""
        self.worker = None
        for widget in self.controls:
            widget.setEnabled(True)
        self.export_button.setEnabled(True)
        self.status_label.setVisible(False)
        self.files_label.setVisible(True)
        self.progress_bar.setValue(0)
        show_error(self, message)

    def _open_folder(self):
        """Открывает папку с готовыми файлами."""
        QDesktopServices.openUrl(QUrl.fromLocalFile(self.folder_edit.text()))

    def reject(self):
        """Не даёт закрыть окно, пока идёт сохранение."""
        if self.worker is None:
            super().reject()


def topics_text(questions) -> str:
    """Темы билета со счётчиком: «Циклы ×2, Функции»."""
    counts: dict[str, int] = {}
    for question in questions:
        counts[question.topic_name] = counts.get(question.topic_name, 0) + 1
    return ", ".join(
        f"{name} ×{count}" if count > 1 else name for name, count in counts.items()
    )


class SummaryDialog(QDialog):
    """Сводная ведомость серии: состав и баллы всех билетов."""

    def __init__(self, title, subtitle, variants, header="", parent=None):
        """Показывает таблицу по всем билетам, итог проверки и кнопки."""
        super().__init__(parent)
        self.setWindowTitle("Сводная ведомость")
        self.resize(960, 640)
        self.header = header or title
        self.variants = variants
        sub = QLabel(subtitle)
        sub.setObjectName("subtitle")
        self.rows = [
            [
                f"№ {variant.variant_no}",
                ", ".join(str(q.id) for q in variant.questions),
                topics_text(variant.questions),
                variant.total_score,
            ]
            for variant in variants
        ]
        table = make_table(
            ["Билет", "Вопросы (№ в банке)", "Темы", "Баллы"], stretch_column=2
        )
        fill_table(table, self.rows)
        table.verticalHeader().setDefaultSectionSize(40)
        banner = QLabel("✓ " + self.summary_text(variants))
        banner.setObjectName("success")
        banner.setWordWrap(True)
        body = QVBoxLayout()
        body.setSpacing(12)
        body.addWidget(sub)
        body.addWidget(table, 1)
        body.addWidget(banner)
        print_button = make_button("Печать")
        print_button.clicked.connect(self.print_summary)
        save_button = make_button("Сохранить в DOCX")
        save_button.clicked.connect(self.save_docx)
        close_button = make_button("Закрыть", "primary")
        close_button.clicked.connect(self.accept)
        footer = QHBoxLayout()
        footer.addStretch()
        footer.addWidget(print_button)
        footer.addWidget(save_button)
        footer.addWidget(close_button)
        build_dialog(self, f"Сводная ведомость --- {title}", body, footer)

    @staticmethod
    def summary_text(variants) -> str:
        """Итог: одинаковые ли баллы и нет ли билетов с одним составом."""
        scores = {variant.total_score for variant in variants}
        sets = {frozenset(q.id for q in variant.questions) for variant in variants}
        count = len(variants)
        if len(scores) == 1:
            first = f"У всех {count} билетов одинаковый балл: {scores.pop()}"
        else:
            first = "Баллы билетов различаются"
        if len(sets) == count:
            return first + " · одинаковых по составу билетов нет"
        return first + " · есть билеты с одинаковым составом"

    def print_summary(self):
        """Отправляет ведомость на принтер."""
        printer = QPrinter()
        if QPrintDialog(printer, self).exec() != QDialog.DialogCode.Accepted:
            return
        rows = "".join(
            "<tr>" + "".join(f"<td>{cell}</td>" for cell in row) + "</tr>"
            for row in self.rows
        )
        document = QTextDocument()
        document.setHtml(
            f"<h2>{self.header}</h2><table border='1' cellspacing='0' "
            "cellpadding='4'><tr><th>Билет</th><th>Вопросы</th><th>Темы</th>"
            f"<th>Баллы</th></tr>{rows}</table>"
        )
        document.print(printer)

    def save_docx(self):
        """Сохраняет ведомость в файл DOCX."""
        name, _ = QFileDialog.getSaveFileName(
            self, "Сохранить ведомость", "ведомость.docx", "Word (*.docx)"
        )
        if not name:
            return
        try:
            ExporterFactory.create("docx").save(
                build_summary(self.header, self.variants), Path(name).with_suffix("")
            )
        except (OSError, TicketGenError) as error:
            show_error(self, str(error))
