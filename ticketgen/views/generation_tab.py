"""Вкладка «Генерация»: параметры серии, проверка банка, запуск, предпросмотр."""

from datetime import datetime

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QIntValidator
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QProgressBar,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from ticketgen.logic.generator import generate_variants, random_seed, ticket_title
from ticketgen.logic.scoring import ticket_score
from ticketgen.views.common import make_button, make_chip, plural, show_error
from ticketgen.workers.background_worker import BackgroundWorker

SEED_HINT = (
    "Seed — число, от которого зависит случайный выбор вопросов.\n"
    "Одинаковый seed и шаблон всегда дают одинаковый комплект билетов.\n"
    "Оставьте поле пустым, чтобы seed выбрался случайно."
)
OVERLAP_HINT = (
    "Каждый вопрос попадёт только в один билет серии.\n"
    "Внутри одного билета вопросы не повторяются в любом режиме."
)
OK_ICON = "<span style='color:#16A34A'>✓</span> "
WARN_ICON = "<span style='color:#D97706'>⚠</span> "


def _label(text: str = "", name: str = "") -> QLabel:
    """Подпись с именем стиля (hint, h2...)."""
    label = QLabel(text)
    if name:
        label.setObjectName(name)
    return label


class GenerationTab(QWidget):
    """Генерация серии билетов (View)."""

    # (id серии, нужно ли сразу открыть экспорт) — вкладку «Результаты» открывает окно
    open_series = pyqtSignal(int, bool)

    def __init__(self, controller, parent=None):
        """Строит карточку параметров слева и предпросмотр справа."""
        super().__init__(parent)
        self.controller = controller
        self.templates = []
        self.worker = None
        self.cancelled = False
        self.started = datetime.now()
        self.pending = None  # параметры генерации, которая сейчас идёт
        self.last_series_id = None

        self.template_combo = QComboBox()
        self.count_spin = QSpinBox()
        self.count_spin.setRange(1, 100)
        self.count_spin.setValue(30)
        self.count_spin.setFixedWidth(80)
        self.count_spin.setButtonSymbols(QSpinBox.ButtonSymbols.NoButtons)
        self.no_overlap_check = QCheckBox(
            "Без пересечений — вопрос в серии только один раз"
        )
        self.no_overlap_check.setToolTip(OVERLAP_HINT)
        self.seed_edit = QLineEdit()
        self.seed_edit.setText(str(random_seed()))
        self.seed_edit.setValidator(QIntValidator(1, 999_999_999))
        self.seed_edit.setToolTip(SEED_HINT)
        random_button = make_button("Случайный")
        random_button.clicked.connect(
            lambda: self.seed_edit.setText(str(random_seed()))
        )
        seed_hint = _label("Тот же seed и тот же шаблон дадут тот же комплект", "hint")
        seed_hint.setToolTip(SEED_HINT)

        self.checks_box = QVBoxLayout()
        self.checks_box.setSpacing(6)
        self.error_banner = QLabel()
        self.error_banner.setObjectName("errorBanner")
        self.error_banner.setWordWrap(True)
        self.generate_button = make_button("", "primary")
        self.progress_bar = QProgressBar()
        self.status_label = _label("Готово к генерации", "hint")
        self.cancel_button = make_button("Отмена", "link")
        self.cancel_button.setVisible(False)
        self.cancel_button.clicked.connect(self.cancel_generation)

        divider = QFrame()
        divider.setObjectName("divider")
        divider.setFixedHeight(1)
        count_row = QHBoxLayout()
        count_row.addWidget(self.count_spin)
        count_row.addWidget(_label("от 1 до 100", "hint"))
        count_row.addStretch()
        seed_row = QHBoxLayout()
        seed_row.addWidget(self.seed_edit, 1)
        seed_row.addWidget(random_button)
        status_row = QHBoxLayout()
        status_row.addWidget(self.status_label, 1)
        status_row.addWidget(self.cancel_button)

        left_card = QFrame()
        left_card.setObjectName("card")
        left_card.setFixedWidth(640)
        left = QVBoxLayout(left_card)
        left.setContentsMargins(24, 24, 24, 24)
        left.setSpacing(4)
        left.addWidget(_label("Параметры генерации", "h2"))
        left.addSpacing(8)
        left.addWidget(_label("Шаблон билета", "hint"))
        left.addWidget(self.template_combo)
        left.addSpacing(12)
        left.addWidget(_label("Количество билетов", "hint"))
        left.addLayout(count_row)
        left.addSpacing(12)
        left.addWidget(self.no_overlap_check)
        note = _label("Нужно не меньше «билеты × вопросы» по каждому правилу", "hint")
        note.setContentsMargins(24, 0, 0, 0)
        left.addWidget(note)
        left.addSpacing(12)
        left.addWidget(_label("Seed — число для повторения результата", "hint"))
        left.addLayout(seed_row)
        left.addWidget(seed_hint)
        left.addSpacing(12)
        left.addWidget(divider)
        left.addSpacing(12)
        left.addWidget(_label("Проверка банка вопросов", "hintBold"))
        left.addSpacing(4)
        left.addLayout(self.checks_box)
        left.addWidget(self.error_banner)
        left.addSpacing(12)
        left.addWidget(self.generate_button)
        left.addSpacing(4)
        left.addLayout(status_row)
        left.addWidget(self.progress_bar)
        left.addStretch()

        layout = QHBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 16)
        layout.setSpacing(16)
        layout.addWidget(left_card)
        layout.addWidget(self._build_preview(), 1)

        self.template_combo.currentIndexChanged.connect(self.update_check)
        self.count_spin.valueChanged.connect(self.update_check)
        self.no_overlap_check.toggled.connect(self.update_check)
        self.generate_button.clicked.connect(self.start_generation)
        controller.templates_changed.connect(self.refresh)
        controller.questions_changed.connect(self.update_check)
        self.refresh()

    def _build_preview(self) -> QFrame:
        """Правая карточка: заголовок, заглушка и готовый билет с кнопками."""
        card = QFrame()
        card.setObjectName("card")
        self.placeholder = _label("Здесь появится билет № 1 после генерации", "hint")
        self.placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.result_banner = QLabel()
        self.result_banner.setObjectName("success")
        self.ticket_card = QFrame()
        self.ticket_card.setObjectName("card")
        self.ticket_layout = QVBoxLayout(self.ticket_card)
        self.ticket_layout.setContentsMargins(24, 24, 24, 24)
        all_button = make_button("Все билеты серии")
        export_button = make_button("Экспорт…", "primary")
        all_button.clicked.connect(lambda: self._open_results(False))
        export_button.clicked.connect(lambda: self._open_results(True))
        self.result_buttons = QWidget()
        buttons = QHBoxLayout(self.result_buttons)
        buttons.setContentsMargins(0, 0, 0, 0)
        buttons.addStretch()
        buttons.addWidget(all_button)
        buttons.addWidget(export_button)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)
        layout.addWidget(_label("Предпросмотр", "h2"))
        layout.addWidget(self.result_banner)
        layout.addWidget(self.placeholder, 1)
        layout.addWidget(self.ticket_card, 1)
        layout.addWidget(self.result_buttons)
        self._show_result(False)
        return card

    def _show_result(self, has_result: bool):
        """Переключает правую карточку между заглушкой и готовым билетом."""
        self.placeholder.setVisible(not has_result)
        for widget in (self.result_banner, self.ticket_card, self.result_buttons):
            widget.setVisible(has_result)

    def _open_results(self, export: bool):
        """Просит окно открыть вкладку «Результаты» (и экспорт)."""
        if self.last_series_id is not None:
            self.open_series.emit(self.last_series_id, export)

    def refresh(self):
        """Обновляет список шаблонов (по сигналу контроллера)."""
        current = self.template_combo.currentData()
        self.templates = self.controller.get_templates()
        self.template_combo.blockSignals(True)
        self.template_combo.clear()
        for template in self.templates:
            questions = sum(rule.questions_count for rule in template.rules)
            self.template_combo.addItem(
                f"{template.template_name} "
                f"({plural(questions, ('вопрос', 'вопроса', 'вопросов'))}, "
                f"{plural(ticket_score(template.rules), ('балл', 'балла', 'баллов'))})",
                template.id,
            )
        self.template_combo.setCurrentIndex(
            max(0, self.template_combo.findData(current))
        )
        self.template_combo.blockSignals(False)
        self.update_check()

    def current_template(self):
        """Выбранный шаблон или None."""
        index = self.template_combo.currentIndex()
        return self.templates[index] if 0 <= index < len(self.templates) else None

    def _set_checks(self, lines: list[str], banner: str = ""):
        """Показывает строки проверки (с иконками) и красную плашку."""
        while self.checks_box.count():
            widget = self.checks_box.takeAt(0).widget()
            if widget:
                widget.deleteLater()
        for line in lines:
            label = QLabel(line)
            label.setTextFormat(Qt.TextFormat.RichText)
            self.checks_box.addWidget(label)
        self.error_banner.setText("⚠ " + banner if banner else "")
        self.error_banner.setVisible(bool(banner))

    def update_check(self):
        """Пересчитывает блок «Проверка банка» и текст кнопки."""
        count = self.count_spin.value()
        if self.worker is None:
            self.generate_button.setText(
                "Сгенерировать " + plural(count, ("билет", "билета", "билетов"))
            )
        template = self.current_template()
        if template is None or not template.rules:
            self._set_checks([], "Выберите шаблон с правилами.")
            self.generate_button.setEnabled(False)
            return
        no_overlap = self.no_overlap_check.isChecked()
        checks, possible = self.controller.check_template(template, count, no_overlap)
        problems = [c for c in checks if not c.ok]
        enough_unique = no_overlap or possible >= count
        questions = sum(rule.questions_count for rule in template.rules)
        score = ticket_score(template.rules)
        lines = [
            OK_ICON + "В каждом билете "
            f"{plural(questions, ('вопрос', 'вопроса', 'вопросов'))} и "
            f"{plural(score, ('балл', 'балла', 'баллов'))}",
            OK_ICON + f"Возможных разных билетов: {possible:,}".replace(",", " "),
        ]
        limits = [c.available // c.rule.questions_count for c in checks]
        limit = min(limits, default=0)
        banner = ""
        if no_overlap and problems:
            words = plural(limit, ("билет", "билета", "билетов"))
            banner = f"Режим без пересечений: хватит на {words} из {count}"
        elif problems:
            for number, c in enumerate(checks, 1):
                if not c.ok:
                    lines.append(
                        WARN_ICON + f"Правило {number}: не хватает вопросов — "
                        f"в банке {c.available} из {c.required}"
                    )
        elif not no_overlap and limit < count:
            words = plural(limit, ("билет", "билета", "билетов"))
            lines.append(
                WARN_ICON + f"Без пересечений хватит только на {words} "
                f"(правило {limits.index(limit) + 1})"
            )
        if not enough_unique:
            banner = f"Нельзя составить {count} разных билетов"
        self._set_checks(lines, banner)
        can_generate = not problems and enough_unique
        self.generate_button.setEnabled(can_generate and self.worker is None)

    def start_generation(self):
        """Запускает генерацию в фоновом потоке."""
        template = self.current_template()
        seed_text = self.seed_edit.text().strip()
        seed = int(seed_text) if seed_text else random_seed()
        no_overlap = self.no_overlap_check.isChecked()
        self.pending = (template, seed, no_overlap)
        self.worker = BackgroundWorker(
            generate_variants,
            template.rules,
            self.controller.active_pool(),
            self.count_spin.value(),
            seed,
            no_overlap,
        )
        self.worker.progress.connect(self.on_progress)
        self.worker.finished_ok.connect(self.on_generated)
        self.worker.failed.connect(self.on_failed)
        self.generate_button.setEnabled(False)
        self.generate_button.setText("Идёт генерация…")
        self.cancel_button.setVisible(True)
        self.cancelled = False
        self.started = datetime.now()
        self.status_label.setText(f"Сгенерировано 0 из {self.count_spin.value()}")
        self.worker.start()

    def on_progress(self, percent: int):
        """Показывает ход генерации."""
        self.progress_bar.setValue(percent)
        total = self.count_spin.value()
        self.status_label.setText(f"Сгенерировано {total * percent // 100} из {total}")

    def cancel_generation(self):
        """Отменяет результат текущей генерации."""
        if self.worker is not None:
            self.cancelled = True

    def _finish(self):
        """Возвращает кнопки в обычное состояние."""
        self.worker = None
        self.cancel_button.setVisible(False)
        self.update_check()

    def on_generated(self, variants):
        """Сохраняет серию в базу и показывает первый билет."""
        template, seed, no_overlap = self.pending
        if self.cancelled:
            self.status_label.setText("Генерация отменена")
            self.progress_bar.setValue(0)
            self._finish()
            return
        self.last_series_id = self.controller.save_series(
            template, seed, no_overlap, variants
        )
        seconds = (datetime.now() - self.started).total_seconds()
        self.status_label.setText(f"Готово за {seconds:.1f} с".replace(".", ","))
        self.progress_bar.setValue(100)
        count = plural(len(variants), ("билет", "билета", "билетов"))
        self.result_banner.setText(
            f"✓ Сгенерировано {count} · seed {seed} · повторов билетов нет"
        )
        self._show_ticket(template, variants[0])
        self._show_result(True)
        self._finish()

    def _show_ticket(self, template, variant):
        """Рисует первый билет серии: заголовок, вопросы с метками, сумму."""
        while self.ticket_layout.count():
            item = self.ticket_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
            elif item.layout():
                self._clear(item.layout())
        title = _label(
            ticket_title(template.header_text or template.template_name, 1), "h2"
        )
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.ticket_layout.addWidget(title)
        self.ticket_layout.addSpacing(12)
        for number, question in enumerate(variant.questions, 1):
            row = QHBoxLayout()
            text = QLabel(f"{number}. {question.question_text}")
            text.setWordWrap(True)
            row.addWidget(text, 1)
            row.addWidget(make_chip(question.level_name, question.difficulty_id))
            self.ticket_layout.addLayout(row)
            self.ticket_layout.addSpacing(8)
        self.ticket_layout.addStretch()
        self.ticket_layout.addWidget(
            _label(f"Сумма баллов: {variant.total_score}", "itemTitle")
        )

    @staticmethod
    def _clear(layout):
        """Удаляет все элементы вложенной раскладки."""
        while layout.count():
            item = layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def on_failed(self, message: str):
        """Показывает ошибку генерации."""
        self.status_label.setText("")
        self.progress_bar.setValue(0)
        self._finish()
        show_error(self, message)
