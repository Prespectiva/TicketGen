"""Главное окно: заголовок, четыре вкладки, строка состояния, меню."""

from PyQt6.QtCore import QSize
from PyQt6.QtWidgets import (
    QApplication,
    QLabel,
    QMainWindow,
    QMessageBox,
    QTabWidget,
)

from ticketgen.views.generation_tab import GenerationTab
from ticketgen.views.question_tab import QuestionTab
from ticketgen.views.results_tab import ResultsTab
from ticketgen.views.template_tab import TemplateTab

ABOUT_TEXT = (
    "<b>TicketGen</b> — генератор вариантов экзаменационных билетов.<br>"
    "Версия 1.0, 2026.<br>Разработчик: Репенко Я. А., группа ИСП-341.<br><br>"
    "Порядок работы: заполните банк вопросов → создайте шаблон → "
    "сгенерируйте серию → проверьте билеты → экспортируйте в DOCX или PDF."
)


class MainWindow(QMainWindow):
    """Однооконный интерфейс с вкладками (по ТЗ, раздел 4.1.6)."""

    def __init__(self, controller):
        """Создаёт вкладки и подключает строку состояния."""
        super().__init__()
        self.controller = controller
        self.setWindowTitle("TicketGen — Генератор экзаменационных билетов")
        self.setMinimumSize(1280, 720)
        self.resize(self._start_size())

        tabs = QTabWidget()
        tabs.addTab(QuestionTab(controller), "Банк вопросов")
        tabs.addTab(TemplateTab(controller), "Шаблоны")
        generation_tab = GenerationTab(controller)
        results_tab = ResultsTab(controller)
        tabs.addTab(generation_tab, "Генерация")
        tabs.addTab(results_tab, "Результаты")
        self.setCentralWidget(tabs)

        def open_results(series_id: int, export: bool):
            """Переходит на «Результаты» и выбирает новую серию."""
            tabs.setCurrentWidget(results_tab)
            results_tab.select_series(series_id, export)

        generation_tab.open_series.connect(open_results)

        help_menu = self.menuBar().addMenu("Помощь")
        help_menu.addAction("О программе", self.show_about)

        self.status_label = QLabel()
        self.statusBar().addWidget(self.status_label, 1)
        version_label = QLabel("Версия 1.0")
        self.statusBar().addPermanentWidget(version_label)
        for signal in (
            controller.questions_changed,
            controller.templates_changed,
            controller.series_changed,
        ):
            signal.connect(self.update_status)
        self.update_status()

    def update_status(self):
        """Обновляет строку состояния."""
        self.status_label.setText(self.controller.stats())

    @staticmethod
    def _start_size() -> QSize:
        """1920×1080 как в макете, но не больше доступной области экрана."""
        screen = QApplication.primaryScreen()
        if screen is None:
            return QSize(1920, 1080)
        area = screen.availableGeometry()
        return QSize(min(1920, area.width()), min(1080, area.height()))

    def show_about(self):
        """Окно «О программе»."""
        QMessageBox.about(self, "О программе", ABOUT_TEXT)

    def closeEvent(self, event):  # имя метода задано библиотекой Qt
        """При закрытии окна делает резервную копию базы."""
        try:
            self.controller.backup()
        except OSError as error:
            QMessageBox.warning(self, "Резервная копия", f"Не удалось: {error}")
        event.accept()
