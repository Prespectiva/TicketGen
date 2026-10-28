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
tests/test_repositories.py:
"""Тесты CRUD-операций репозиториев."""

import pytest

from ticketgen.domain.models import Question, TicketGenError


def test_question_crud(repos):
    """Вопрос можно создать, прочитать, изменить и удалить."""
    questions = repos["questions"]
    topic_id = repos["topics"].add("ОАиП", "Словари")
    new_id = questions.add(Question(None, topic_id, 1, "теория", "Что такое dict?"))
    assert questions.get(new_id).question_text == "Что такое dict?"

    question = questions.get(new_id)
    question.question_text = "Что такое словарь?"
    questions.update(question)
    assert questions.get(new_id).question_text == "Что такое словарь?"

    questions.delete(new_id)
    assert questions.get(new_id) is None


def test_find_with_filters(repos):
    """Фильтр по сложности и поиск по тексту работают вместе."""
    found = repos["questions"].find(text="рекурсия", difficulty_id=1)
    assert len(found) == 1
    assert found[0].level_name == "лёгкий"


def test_sql_injection_is_harmless(repos):
    """Опасный текст в поиске не ломает запрос и не удаляет данные."""
    repos["questions"].find(text="'; DROP TABLE tbl_questions; --")
    assert repos["questions"].count() == 96


def test_topic_with_questions_cannot_be_deleted(repos):
    """Внешний ключ не даёт удалить тему, у которой есть вопросы."""
    topic_id = repos["topics"].get_all()[0].id
    with pytest.raises(TicketGenError):
        repos["topics"].delete(topic_id)