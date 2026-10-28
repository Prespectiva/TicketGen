"""Точка входа TicketGen."""

import sys

from PyQt6.QtWidgets import QApplication, QMessageBox

from ticketgen.controllers.app_controller import AppController
from ticketgen.data.database import Database
from ticketgen.views.main_window import MainWindow
from ticketgen.views.styles import apply_light_theme


def main():
    """Создаёт приложение, подключает базу и показывает главное окно."""
    app = QApplication(sys.argv)
    apply_light_theme(app)
    try:
        database = Database.instance()
    except Exception as error:  # база повреждена или нет прав на папку
        QMessageBox.critical(None, "TicketGen", f"Не удалось открыть базу:\n{error}")
        return 1
    window = MainWindow(AppController(database))
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
