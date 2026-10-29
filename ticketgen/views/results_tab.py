"""Вкладка «Результаты»: история серий, билеты, замена вопроса, экспорт."""

from PyQt6.QtCore import QSize, Qt
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from ticketgen.config import AppConfig
from ticketgen.views.common import (
    confirm,
    format_dt,
    make_button,
    plural,
    show_error,
)
from ticketgen.views.dialogs import ExportDialog, ReplaceQuestionDialog, SummaryDialog


class ResultsTab(QWidget):
    """Просмотр и выгрузка сохранённых серий (View)."""

    def __init__(self, controller, parent=None):
        """Строит три белые карточки: серии, билеты, состав билета."""
        super().__init__(parent)
        self.controller = controller
        self.series = []
        self.variants = []

        self.series_list = self._make_list()
        self.variant_list = self._make_list()
        self.score_label = QLabel()
        self.score_label.setObjectName("okText")
        delete_button = make_button("Удалить серию", "danger")
        self.ticket_title = QLabel()
        self.ticket_title.setObjectName("itemTitle")
        self.ticket_score = QLabel()
        self.ticket_score.setObjectName("itemTitle")
        self.cards_layout = QVBoxLayout()
        self.cards_layout.setContentsMargins(0, 0, 0, 0)
        self.cards_layout.setSpacing(12)
        self.cards_layout.addStretch()
        cards_host = QWidget()
        cards_host.setObjectName("cardsHost")
        cards_host.setLayout(self.cards_layout)
        scroll = QScrollArea()
        scroll.setObjectName("cardsScroll")
        scroll.setWidgetResizable(True)
        scroll.setWidget(cards_host)
        summary_button = make_button("Сводная ведомость")
        export_button = make_button("Экспорт…", "primary")

        series_card = self._card_frame(240 + 120, "Серии билетов", self.series_list)
        variants_card = self._card_frame(240, "Билеты", self.variant_list)
        variants_card.layout().addWidget(self.score_label)
        head_row = QHBoxLayout()
        head_row.addWidget(self.ticket_title)
        head_row.addStretch()
        head_row.addWidget(self.ticket_score)
        ticket_card = QFrame()
        ticket_card.setObjectName("card")
        ticket_layout = QVBoxLayout(ticket_card)
        ticket_layout.setContentsMargins(12, 16, 12, 12)
        ticket_layout.setSpacing(12)
        ticket_layout.addLayout(head_row)
        ticket_layout.addWidget(scroll, 1)
        buttons = QHBoxLayout()
        buttons.addWidget(delete_button)
        buttons.addStretch()
        buttons.addWidget(summary_button)
        buttons.addWidget(export_button)
        right = QVBoxLayout()
        right.setSpacing(12)
        right.addWidget(ticket_card, 1)
        right.addLayout(buttons)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 16)
        layout.setSpacing(12)
        layout.addWidget(series_card)
        layout.addWidget(variants_card)
        layout.addLayout(right, 1)

        self.series_list.currentRowChanged.connect(self.show_series)
        self.variant_list.currentRowChanged.connect(self.show_variant)
        delete_button.clicked.connect(self.delete_series)
        summary_button.clicked.connect(self.show_summary)
        export_button.clicked.connect(self.export)
        controller.series_changed.connect(self.refresh)
        self.refresh()

    @staticmethod
    def _make_list() -> QListWidget:
        """Список без рамки внутри белой карточки."""
        widget = QListWidget()
        widget.setObjectName("templates")
        widget.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        return widget

    @staticmethod
    def _card_frame(width: int, title: str, content: QWidget) -> QFrame:
        """Белая карточка с заголовком h2 и списком."""
        frame = QFrame()
        frame.setObjectName("card")
        frame.setFixedWidth(width)
        column = QVBoxLayout(frame)
        column.setContentsMargins(0, 16, 0, 12)
        column.setSpacing(8)
        heading = QLabel(title)
        heading.setObjectName("h2")
        heading.setContentsMargins(16, 0, 16, 0)
        column.addWidget(heading)
        column.addWidget(content, 1)
        return frame

    def current_series(self):
        """Выбранная серия или None."""
        row = self.series_list.currentRow()
        return self.series[row] if 0 <= row < len(self.series) else None

    def current_variant(self):
        """Выбранный билет или None."""
        row = self.variant_list.currentRow()
        return self.variants[row] if 0 <= row < len(self.variants) else None

    def refresh(self):
        """Перечитывает историю, сохраняя выбранную серию и билет."""
        series_row = max(0, self.series_list.currentRow())
        variant_row = max(0, self.variant_list.currentRow())
        self.series = self.controller.get_series()
        self.series_list.blockSignals(True)
        self.series_list.clear()
        for series in self.series:
            count = plural(series.variants_count, ("билет", "билета", "билетов"))
            self._add_item(
                self.series_list,
                66,
                [
                    (series.template_name, "itemTitle"),
                    (f"{format_dt(series.created_at)} · {count}", "tiny"),
                    (f"seed {series.seed}", "tiny"),
                ],
            )
        self.series_list.blockSignals(False)
        self.series_list.setCurrentRow(min(series_row, len(self.series) - 1))
        self.show_series()
        if self.variants:
            self.variant_list.setCurrentRow(min(variant_row, len(self.variants) - 1))

    @staticmethod
    def _add_item(widget: QListWidget, height: int, lines, right: str = ""):
        """Добавляет строку списка: подписи столбиком, справа — серый текст."""
        item = QListWidgetItem()
        item.setSizeHint(QSize(0, height))
        widget.addItem(item)
        holder = QWidget()
        holder.setObjectName("templateItem")
        row = QHBoxLayout(holder)
        row.setContentsMargins(13, 8, 16, 8)
        column = QVBoxLayout()
        column.setSpacing(1)
        for text, name in lines:
            label = QLabel(text)
            label.setObjectName(name)
            column.addWidget(label)
        row.addLayout(column, 1)
        if right:
            tail = QLabel(right)
            tail.setObjectName("tiny")
            row.addWidget(tail)
        widget.setItemWidget(item, holder)

    def show_series(self):
        """Показывает билеты выбранной серии."""
        series = self.current_series()
        self.variants = self.controller.get_variants(series.id) if series else []
        self.variant_list.blockSignals(True)
        self.variant_list.clear()
        for variant in self.variants:
            self._add_item(
                self.variant_list,
                40,
                [(f"Билет № {variant.variant_no}", "")],
                f"{variant.total_score} б.",
            )
        self.variant_list.blockSignals(False)
        scores = {variant.total_score for variant in self.variants}
        if len(scores) == 1:
            total = plural(len(self.variants), ("билет", "билета", "билетов"))
            self.score_label.setText(f"{total}, у всех {scores.pop()} баллов")
        elif scores:
            self.score_label.setText("Баллы билетов различаются")
        else:
            self.score_label.setText("")
        if self.variants:
            self.variant_list.setCurrentRow(0)
        self.show_variant()

    def show_variant(self):
        """Показывает вопросы выбранного билета карточками."""
        while self.cards_layout.count() > 1:
            widget = self.cards_layout.takeAt(0).widget()
            if widget:
                widget.deleteLater()
        variant = self.current_variant()
        self.ticket_title.setText(f"Билет № {variant.variant_no}" if variant else "")
        self.ticket_score.setText(
            f"Сумма баллов: {variant.total_score}" if variant else ""
        )
        if not variant:
            return
        for number, question in enumerate(variant.questions, 1):
            self.cards_layout.insertWidget(
                self.cards_layout.count() - 1, self._card(variant, number, question)
            )

    def _card(self, variant, number, question):
        """Карточка вопроса: текст, подпись «Тема · уровень · баллы», «Заменить»."""
        card = QFrame()
        card.setObjectName("questionCard")
        text = QLabel(f"{number}. {question.question_text}")
        text.setWordWrap(True)
        meta = QLabel(
            f"Тема: {question.topic_name} · {question.level_name.lower()} · "
            f"{plural(question.weight, ('балл', 'балла', 'баллов'))}"
        )
        meta.setObjectName("tiny")
        button = make_button("Заменить")
        button.clicked.connect(
            lambda _, n=number, q=question: self.replace_question(variant, n, q)
        )
        left = QVBoxLayout()
        left.setSpacing(8)
        left.addWidget(text)
        left.addWidget(meta)
        row = QHBoxLayout(card)
        row.setContentsMargins(12, 12, 12, 12)
        row.addLayout(left, 1)
        row.addWidget(button)
        return card

    def replace_question(self, variant, number, old):
        """Заменяет вопрос билета на другой той же темы и сложности."""
        candidates = self.controller.replacement_candidates(variant, old)
        if not candidates:
            show_error(self, "Нет других вопросов этой темы и сложности.")
            return
        usage: dict[int, int] = {}
        for other in self.variants:
            for question in other.questions:
                usage[question.id] = usage.get(question.id, 0) + 1
        dialog = ReplaceQuestionDialog(
            number, variant.variant_no, old, candidates, usage, self
        )
        if dialog.exec():
            self.controller.replace_question(variant.id, old.id, dialog.selected.id)

    def delete_series(self):
        """Удаляет выбранную серию."""
        series = self.current_series()
        if series and confirm(
            self,
            f"Удалить серию?\n\nСерия «{series.template_name}» от "
            f"{format_dt(series.created_at)} "
            f"({plural(series.variants_count, ('билет', 'билета', 'билетов'))}) "
            "будет удалена из истории. Уже сохранённые файлы DOCX и PDF "
            "не затрагиваются.",
        ):
            self.controller.delete_series(series.id)

    @staticmethod
    def _subtitle(series) -> str:
        """«Серия от 20.10.2026 14:05 · 30 билетов · seed 4821»."""
        count = plural(series.variants_count, ("билет", "билета", "билетов"))
        return f"Серия от {format_dt(series.created_at)} · {count} · seed {series.seed}"

    def show_summary(self):
        """Открывает сводную ведомость серии."""
        if self.variants:
            series = self.current_series()
            SummaryDialog(
                series.template_name,
                self._subtitle(series),
                self.variants,
                series.header_text or series.template_name,
                self,
            ).exec()

    def select_series(self, series_id: int, export: bool = False):
        """Выбирает серию по id (после генерации); при export открывает экспорт."""
        for row, series in enumerate(self.series):
            if series.id == series_id:
                self.series_list.setCurrentRow(row)
                break
        if export:
            self.export()

    def export(self):
        """Спрашивает параметры экспорта и сохраняет файлы в фоновом потоке."""
        series = self.current_series()
        if series is None:
            show_error(self, "Сначала сгенерируйте серию.")
            return
        base_name = f"серия_{series.id}"
        ExportDialog(
            AppConfig().export_dir,
            base_name,
            f"{series.template_name} · "
            f"{plural(series.variants_count, ('билет', 'билета', 'билетов'))} · "
            f"{format_dt(series.created_at)[:10]}",
            series.header_text or series.template_name,
            self.variants,
            self,
        ).exec()
