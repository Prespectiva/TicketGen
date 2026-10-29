"""Фоновый поток."""

from PyQt6.QtCore import QThread, pyqtSignal


class BackgroundWorker(QThread):
    """Выполняет функцию в отдельном потоке, чтобы окно не зависало.

    Функция должна принимать именованный аргумент ``progress`` — в него
    передаётся процент выполнения. С окном поток общается только сигналами:
    трогать виджеты из другого потока в Qt нельзя.
    """

    progress = pyqtSignal(int)
    finished_ok = pyqtSignal(object)
    failed = pyqtSignal(str)

    def __init__(self, function, *args, **kwargs):
        """Запоминает функцию и её аргументы."""
        super().__init__()
        self._function = function
        self._args = args
        self._kwargs = kwargs

    def run(self):
        """Код, который выполняется в фоновом потоке."""
        try:
            result = self._function(
                *self._args, progress=self.progress.emit, **self._kwargs
            )
            self.finished_ok.emit(result)
        except Exception as error:  # показываем пользователю любую ошибку
            self.failed.emit(str(error))
