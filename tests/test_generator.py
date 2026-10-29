"""Тесты алгоритма генерации билетов."""

import time

import pytest

from ticketgen.domain.models import NotEnoughQuestionsError, Question, TemplateRule
from ticketgen.logic.generator import generate_variants


@pytest.fixture
def setup(repos):
    """Правила шаблона из тестовых данных и пул активных вопросов."""
    template = repos["templates"].get_all()[0]
    pool = repos["questions"].find(only_active=True)
    return template.rules, pool


def test_no_repeats_inside_ticket(setup):
    """Внутри одного билета вопросы не повторяются."""
    rules, pool = setup
    for variant in generate_variants(rules, pool, 30, seed=1):
        ids = [question.id for question in variant.questions]
        assert len(ids) == len(set(ids))


def test_tickets_are_unique_and_equal_score(setup):
    """Все билеты разные, а суммарный балл у всех одинаковый."""
    rules, pool = setup
    variants = generate_variants(rules, pool, 30, seed=1)
    sets = {frozenset(q.id for q in v.questions) for v in variants}
    assert len(sets) == 30
    assert len({variant.total_score for variant in variants}) == 1


def test_same_seed_same_result(setup):
    """Одинаковый seed даёт одинаковую серию."""
    rules, pool = setup
    first = generate_variants(rules, pool, 10, seed=42)
    second = generate_variants(rules, pool, 10, seed=42)
    assert [[q.id for q in v.questions] for v in first] == [
        [q.id for q in v.questions] for v in second
    ]


def test_no_overlap_mode(setup):
    """В режиме без пересечений вопрос встречается в серии один раз."""
    rules, pool = setup
    variants = generate_variants(rules, pool, 8, seed=5, no_overlap=True)
    all_ids = [q.id for v in variants for q in v.questions]
    assert len(all_ids) == len(set(all_ids))


def test_not_enough_questions(setup):
    """Если вопросов мало, генерация не запускается."""
    rules, pool = setup
    with pytest.raises(NotEnoughQuestionsError):
        generate_variants(rules, pool, 9, seed=5, no_overlap=True)


def test_speed_30_tickets_from_1000_questions():
    """30 билетов по 10 вопросов из банка в 1000 вопросов — меньше 3 секунд."""
    pool = [
        Question(i, i % 5 + 1, 1, "теория", f"Вопрос {i}", weight=1)
        for i in range(1, 1001)
    ]
    rules = [TemplateRule(None, 1, topic, 1, 2, weight=1) for topic in range(1, 6)]
    start = time.perf_counter()
    variants = generate_variants(rules, pool, 30, seed=7)
    assert time.perf_counter() - start < 3
    assert all(len(variant.questions) == 10 for variant in variants)
