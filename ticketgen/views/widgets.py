"""Свои виджеты: вкладки с анимированной линией и скруглённые выпадающие списки."""

from PyQt6 import sip
from PyQt6.QtCore import (
    QEasingCurve,
    QEvent,
    QObject,
    QRectF,
    Qt,
    QVariantAnimation,
)
from PyQt6.QtGui import QColor, QCursor, QPainter
from PyQt6.QtWidgets import QComboBox, QStyledItemDelegate, QTabBar

from ticketgen.views.styles import PRIMARY, ROW_HOVER, TAB_HOVER_LINE

LINE_HEIGHT = 2
SLIDE_MS = 250  # перемещение синей линии к выбранной вкладке
HOVER_MS = 180  # рост линии при наведении


class AnimatedTabBar(QTabBar):
    """Панель вкладок с анимированной нижней линией.

    * При наведении под вкладкой из центра вырастает светло-синяя линия,
      а когда курсор уходит, она плавно сжимается.
    * Синяя линия выбранной вкладки не перескакивает, а плавно переезжает
      к новой вкладке.

    Линии рисуются в ``paintEvent`` поверх стандартной отрисовки, поэтому
    в стилях у вкладок нет своей нижней границы.
    """

    def __init__(self, parent=None):
        """Настраивает две анимации: переезд линии и рост линии наведения."""
        super().__init__(parent)
        self.setMouseTracking(True)
        self.setDrawBase(False)
        self._line = QRectF()  # где сейчас нарисована синяя линия
        self._hover_target = -1  # вкладка под курсором
        self._hover_drawn = -1  # вкладка, под которой рисуется линия наведения
        self._hover_progress = 0.0  # 0 — линии нет, 1 — во всю ширину

        self._slide = QVariantAnimation(self)
        self._slide.setDuration(SLIDE_MS)
        self._slide.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._slide.valueChanged.connect(self._on_slide)

        self._grow = QVariantAnimation(self)
        self._grow.setDuration(HOVER_MS)
        self._grow.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._grow.valueChanged.connect(self._on_grow)

        self.currentChanged.connect(self._slide_to)

    # ----- Синяя линия выбранной вкладки -----

    def _line_rect(self, index: int) -> QRectF:
        """Прямоугольник линии под вкладкой index."""
        tab = self.tabRect(index)
        return QRectF(
            tab.x(), tab.y() + tab.height() - LINE_HEIGHT, tab.width(), LINE_HEIGHT
        )

    def _slide_to(self, index: int):
        """Запускает переезд линии к вкладке index."""
        if index < 0:
            self._line = QRectF()
            self.update()
            return
        target = self._line_rect(index)
        if self._line.isNull() or not self.isVisible():
            self._line = target
            self.update()
            return
        self._slide.stop()
        self._slide.setStartValue(QRectF(self._line))
        self._slide.setEndValue(target)
        self._slide.start()

    def _on_slide(self, value):
        """Шаг анимации переезда."""
        self._line = QRectF(value)
        self.update()

    def _snap_line(self):
        """Ставит линию на место без анимации (после изменения размеров)."""
        if self._slide.state() != QVariantAnimation.State.Running:
            index = self.currentIndex()
            self._line = self._line_rect(index) if index >= 0 else QRectF()
            self.update()

    def tabLayoutChange(self):  # имя метода задано библиотекой Qt
        """Вкладки перестроились: линия переезжает вслед за ними."""
        super().tabLayoutChange()
        self._snap_line()

    def resizeEvent(self, event):  # имя метода задано библиотекой Qt
        """После изменения размера линия встаёт под выбранную вкладку."""
        super().resizeEvent(event)
        self._snap_line()

    def showEvent(self, event):  # имя метода задано библиотекой Qt
        """При первом показе линия сразу стоит под выбранной вкладкой."""
        super().showEvent(event)
        self._snap_line()

    # ----- Линия при наведении -----

    def _set_hover(self, index: int):
        """Запускает рост линии под новой вкладкой или сжатие старой."""
        if index == self._hover_target:
            return
        self._hover_target = index
        self._grow.stop()
        if index >= 0:
            self._hover_drawn = index
            self._grow.setStartValue(0.0)
            self._grow.setEndValue(1.0)
        else:
            self._grow.setStartValue(self._hover_progress)
            self._grow.setEndValue(0.0)
        self._grow.start()

    def _on_grow(self, value):
        """Шаг анимации линии наведения."""
        self._hover_progress = float(value)
        self.update()

    def mouseMoveEvent(self, event):  # имя метода задано библиотекой Qt
        """Следит, над какой вкладкой курсор."""
        self._set_hover(self.tabAt(event.position().toPoint()))
        super().mouseMoveEvent(event)

    def leaveEvent(self, event):  # имя метода задано библиотекой Qt
        """Курсор ушёл с панели — линия наведения сжимается."""
        self._set_hover(-1)
        super().leaveEvent(event)

    # ----- Отрисовка -----

    def paintEvent(self, event):  # имя метода задано библиотекой Qt
        """Рисует вкладки, затем линию наведения и синюю линию выбора."""
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        hovered = self._hover_drawn
        if (
            0 <= hovered < self.count()
            and hovered != self.currentIndex()
            and self._hover_progress > 0
        ):
            full = self._line_rect(hovered)
            width = full.width() * self._hover_progress
            line = QRectF(full.center().x() - width / 2, full.y(), width, full.height())
            painter.setBrush(QColor(TAB_HOVER_LINE))
            painter.drawRoundedRect(line, 1, 1)
        if not self._line.isNull():
            painter.setBrush(QColor(PRIMARY))
            painter.drawRoundedRect(self._line, 1, 1)
        painter.end()


class _HoverDelegate(QStyledItemDelegate):
    """Рисует серый фон под ячейками строки, над которой мышь."""

    def __init__(self, highlighter):
        """Запоминает, у кого спрашивать номер строки под курсором."""
        super().__init__(highlighter.table)
        self.highlighter = highlighter

    def paint(self, painter, option, index):  # имя метода задано библиотекой Qt
        """Сначала серый фон (если строка под курсором), потом обычная ячейка."""
        if index.row() == self.highlighter.row:
            painter.fillRect(option.rect, self.highlighter.color)
        super().paint(painter, option, index)


class RowHoverHighlighter(QObject):
    """Подсвечивает серым всю строку таблицы под курсором (как в макете).

    Стили Qt умеют подсвечивать только одну ячейку, а в строке правила
    есть поля ввода, которые сами перехватывают мышь. Поэтому строка
    вычисляется по движению мыши над таблицей и по входу в каждое поле.
    """

    def __init__(self, table, color: str = ROW_HOVER):
        """Подключается к таблице table."""
        super().__init__(table)
        self.table = table
        self.row = -1
        self.color = QColor(color)
        # Фон ячеек из стилей (::item) перекрывает setBackground, поэтому
        # серый фон рисует свой делегат прямо перед отрисовкой ячейки.
        table.setItemDelegate(_HoverDelegate(self))
        table.setMouseTracking(True)
        table.viewport().setMouseTracking(True)
        table.viewport().installEventFilter(self)

    def watch(self, widget, row: int):
        """Поле ввода в ячейке: при наведении на него подсвечивается строка row."""
        widget.setProperty("hoverRow", row)
        widget.installEventFilter(self)

    def reset(self):
        """Снимает подсветку (перед перезаполнением таблицы)."""
        self.row = -1

    def eventFilter(self, obj, event):  # имя метода задано библиотекой Qt
        """Следит за мышью над таблицей и над полями в ячейках."""
        if sip.isdeleted(self.table):
            # Окно закрывается: Qt уже удалил таблицу, но ещё присылает
            # последние события. Обращаться к таблице теперь нельзя.
            return False
        kind = event.type()
        if obj is self.table.viewport():
            if kind == QEvent.Type.MouseMove:
                self._set_row(self.table.rowAt(int(event.position().y())))
            elif kind == QEvent.Type.Leave:
                self._set_row(-1)
        elif kind == QEvent.Type.Enter:
            self._set_row(obj.property("hoverRow"))
        elif kind == QEvent.Type.Leave:
            # Мышь ушла с поля: если и с таблицы тоже — снимаем подсветку.
            viewport = self.table.viewport()
            if not viewport.rect().contains(viewport.mapFromGlobal(QCursor.pos())):
                self._set_row(-1)
        return False

    def _set_row(self, row):
        """Перекрашивает старую и новую строку."""
        row = -1 if row is None else row
        if row != self.row:
            self.row = row
            self.table.viewport().update()


class ComboPopupStyler(QObject):
    """Делает выпадающие списки всех QComboBox скруглёнными, как в макете.

    Окно списка в Qt по умолчанию квадратное, с рамкой и тенью Windows.
    Фильтр событий ловит каждый новый QComboBox и один раз убирает у окна
    списка рамку и фон, а скругление и цвета задаются в стилях (styles.py).
    """

    def eventFilter(self, obj, event):  # имя метода задано библиотекой Qt
        """При первой «полировке» выпадающего списка настраивает его окно."""
        if (
            event.type() == QEvent.Type.Polish
            and isinstance(obj, QComboBox)
            and not obj.property("roundPopup")
        ):
            obj.setProperty("roundPopup", True)
            style_combo_popup(obj)
        return False


def style_combo_popup(combo: QComboBox):
    """Убирает у окна списка рамку, тень и фон; пункты рисует делегат стилей."""
    # Обычный делегат понимает стили ::item (высота, отступы, скругление).
    combo.setItemDelegate(QStyledItemDelegate(combo))
    popup = combo.view().window()
    popup.setWindowFlags(
        popup.windowFlags()
        | Qt.WindowType.FramelessWindowHint
        | Qt.WindowType.NoDropShadowWindowHint
    )
    popup.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)


def install_combo_styler(app):
    """Включает скруглённые выпадающие списки во всём приложении."""
    styler = ComboPopupStyler(app)
    app.installEventFilter(styler)
    app._combo_styler = styler  # ссылка, чтобы фильтр не удалил сборщик мусора
