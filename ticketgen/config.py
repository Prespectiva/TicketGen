"""Настройки приложения (паттерн Singleton)."""

import sys
from pathlib import Path


class AppConfig:
    """Единственный экземпляр настроек приложения.

    Хранит пути к файлу базы, папке резервных копий и папке экспорта.
    Повторный вызов ``AppConfig()`` возвращает тот же объект.
    """

    _instance = None

    def __new__(cls):
        """Создаёт объект только при первом вызове, потом возвращает его же."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._load()
        return cls._instance

    def _load(self):
        """Заполняет пути относительно папки программы."""
        if getattr(sys, "frozen", False):
            # Программа собрана PyInstaller: база лежит рядом с TicketGen.exe.
            base_dir = Path(sys.executable).parent
        else:
            base_dir = Path(__file__).resolve().parent.parent
        self.base_dir = base_dir
        self.db_path = base_dir / "tickets.db"
        self.backup_dir = base_dir / "backup"
        self.export_dir = base_dir / "export"
        self.backups_to_keep = 5
