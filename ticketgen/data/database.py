"""Подключение к SQLite, создание схемы и резервное копирование."""

import sqlite3
from datetime import datetime
from pathlib import Path

from ticketgen.config import AppConfig

SCHEMA = """
CREATE TABLE IF NOT EXISTS tbl_topics (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    discipline  TEXT NOT NULL,
    topic_name  TEXT NOT NULL,
    UNIQUE (discipline, topic_name)
);

CREATE TABLE IF NOT EXISTS tbl_difficulty (
    id          INTEGER PRIMARY KEY,
    level_name  TEXT UNIQUE NOT NULL,
    weight      INTEGER NOT NULL CHECK (weight > 0)
);

CREATE TABLE IF NOT EXISTS tbl_questions (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    topic_id       INTEGER NOT NULL REFERENCES tbl_topics(id),
    difficulty_id  INTEGER NOT NULL REFERENCES tbl_difficulty(id),
    q_type         TEXT NOT NULL DEFAULT 'теория'
                   CHECK (q_type IN ('теория', 'задача', 'практика')),
    question_text  TEXT NOT NULL,
    answer_text    TEXT DEFAULT '',
    is_active      INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS tbl_templates (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    template_name  TEXT UNIQUE NOT NULL,
    header_text    TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS tbl_template_rules (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    template_id      INTEGER NOT NULL
                     REFERENCES tbl_templates(id) ON DELETE CASCADE,
    topic_id         INTEGER NOT NULL REFERENCES tbl_topics(id),
    difficulty_id    INTEGER NOT NULL REFERENCES tbl_difficulty(id),
    questions_count  INTEGER NOT NULL CHECK (questions_count > 0),
    UNIQUE (template_id, topic_id, difficulty_id)
);

CREATE TABLE IF NOT EXISTS tbl_series (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    template_id     INTEGER NOT NULL REFERENCES tbl_templates(id),
    created_at      TEXT NOT NULL,
    seed            INTEGER NOT NULL,
    no_overlap      INTEGER NOT NULL DEFAULT 0,
    variants_count  INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS tbl_variants (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    series_id    INTEGER NOT NULL REFERENCES tbl_series(id) ON DELETE CASCADE,
    variant_no   INTEGER NOT NULL,
    total_score  INTEGER
);

CREATE TABLE IF NOT EXISTS tbl_variant_questions (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    variant_id   INTEGER NOT NULL
                 REFERENCES tbl_variants(id) ON DELETE CASCADE,
    question_id  INTEGER NOT NULL REFERENCES tbl_questions(id),
    position     INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_questions_topic_difficulty
    ON tbl_questions (topic_id, difficulty_id);
CREATE INDEX IF NOT EXISTS idx_variants_series ON tbl_variants (series_id);
CREATE INDEX IF NOT EXISTS idx_variant_questions_variant
    ON tbl_variant_questions (variant_id);

INSERT OR IGNORE INTO tbl_difficulty (id, level_name, weight) VALUES
    (1, 'лёгкий', 1),
    (2, 'средний', 2),
    (3, 'сложный', 3);
"""


class Database:
    """Подключение к файлу базы данных.

    В программе используется одно подключение (паттерн Singleton), его
    возвращает ``Database.instance()``. В тестах объект создаётся напрямую:
    ``Database(":memory:")`` — база в оперативной памяти.
    """

    _instance = None

    def __init__(self, path):
        """Открывает базу и создаёт таблицы, если их ещё нет.

        Args:
            path: путь к файлу .db или ":memory:".
        """
        self.path = str(path)
        self.connection = sqlite3.connect(self.path)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA foreign_keys = ON")
        self.connection.executescript(SCHEMA)
        self.connection.commit()

    @classmethod
    def instance(cls):
        """Возвращает единственное подключение к tickets.db."""
        if cls._instance is None:
            cls._instance = cls(AppConfig().db_path)
        return cls._instance

    def backup(self, backup_dir: Path, keep: int = 5) -> Path:
        """Сохраняет копию базы и удаляет самые старые копии.

        Args:
            backup_dir: папка для резервных копий.
            keep: сколько последних копий хранить.

        Returns:
            Путь к созданной копии.
        """
        backup_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        target_path = backup_dir / f"tickets_{stamp}.db"
        target = sqlite3.connect(target_path)
        self.connection.backup(target)
        target.close()
        old_copies = sorted(backup_dir.glob("tickets_*.db"))[:-keep]
        for old_copy in old_copies:
            old_copy.unlink()
        return target_path

    def close(self):
        """Закрывает подключение."""
        self.connection.close()