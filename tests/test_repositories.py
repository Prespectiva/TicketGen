"""Тесты CRUD-операций репозиториев."""

import pytest

from ticketgen.domain.models import Question, Series, TicketGenError
from ticketgen.logic.generator import generate_variants


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


def test_search_ignores_case_for_cyrillic(repos):
    """Поиск находит текст независимо от регистра, в том числе русских букв."""
    questions = repos["questions"]
    assert questions.find(text="рекурсия") == questions.find(text="РЕКУРСИЯ")
    assert len(questions.find(text="Рекурсия")) >= 1


def test_template_with_series_cannot_be_deleted(repos):
    """Шаблон, по которому есть серии, не удаляется, а пользователь видит причину."""
    template = repos["templates"].get_all()[0]
    pool = repos["questions"].find(only_active=True)
    variants = generate_variants(template.rules, pool, 2, seed=1)
    series = Series(None, template.id, "2026-11-01 12:00", 1, False, 2)
    repos["series"].save(series, variants)
    with pytest.raises(TicketGenError, match="серий"):
        repos["templates"].delete(template.id)
    assert repos["templates"].get(template.id) is not None


def test_template_without_series_is_deleted(repos):
    """Шаблон без серий удаляется вместе с правилами."""
    template = repos["templates"].get_all()[0]
    repos["templates"].delete(template.id)
    assert repos["templates"].get(template.id) is None
