"""Тесты: conftest."""

import pytest

from ticketgen.data.database import Database
from ticketgen.data.repositories import (
    DifficultyRepository,
    QuestionRepository,
    SeriesRepository,
    TemplateRepository,
    TopicRepository,
)
from ticketgen.seed_data import fill_database


@pytest.fixture
def db():
    """Пустая база в оперативной памяти, своя для каждого теста."""
    database = Database(":memory:")
    yield database
    database.close()


@pytest.fixture
def filled_db(db):
    """База с тестовыми данными: 4 темы, 96 вопросов, 1 шаблон."""
    fill_database(db)
    return db


@pytest.fixture
def repos(filled_db):
    """Словарь со всеми репозиториями поверх заполненной базы."""
    return {
        "topics": TopicRepository(filled_db),
        "difficulty": DifficultyRepository(filled_db),
        "questions": QuestionRepository(filled_db),
        "templates": TemplateRepository(filled_db),
        "series": SeriesRepository(filled_db),
    }
