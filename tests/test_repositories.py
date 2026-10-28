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
