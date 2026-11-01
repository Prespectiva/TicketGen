"""Точка входа TicketGen."""

import ctypes
import sys

from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QApplication, QMessageBox

from ticketgen.controllers.app_controller import AppController
from ticketgen.data.database import Database
from ticketgen.views.main_window import MainWindow
from ticketgen.views.styles import ICONS, apply_light_theme


def main():
    """Создаёт приложение, подключает базу и показывает главное окно."""
    if sys.platform == "win32":
        # Свой идентификатор, чтобы на панели задач была иконка TicketGen,
        # а не иконка Python.
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("TicketGen.App")
    app = QApplication(sys.argv)
    app.setWindowIcon(QIcon(f"{ICONS}/app_icon.png"))
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
