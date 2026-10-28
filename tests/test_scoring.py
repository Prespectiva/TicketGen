"""Тесты подсчёта баллов и проверки банка."""

from ticketgen.domain.models import TemplateRule
from ticketgen.logic.scoring import (
    check_rules,
    possible_tickets,
    score_formula,
    ticket_score,
)


def make_rule(topic_id, difficulty_id, count, weight):
    """Создаёт правило шаблона для теста."""
    return TemplateRule(None, 1, topic_id, difficulty_id, count, weight=weight)


def test_ticket_score():
    """S = 2·1 + 1·3 = 5."""
    rules = [make_rule(1, 1, 2, 1), make_rule(2, 3, 1, 3)]
    assert ticket_score(rules) == 5
    assert score_formula(rules) == "2×1 + 1×3 = 5"


def test_check_rules_normal_mode():
    """В обычном режиме достаточно n ≥ k."""
    checks = check_rules([make_rule(1, 1, 2, 1)], {(1, 1): 3})
    assert checks[0].ok


def test_check_rules_no_overlap():
    """В режиме без пересечений нужно n ≥ m·k."""
    checks = check_rules([make_rule(1, 1, 2, 1)], {(1, 1): 3}, 30, no_overlap=True)
    assert not checks[0].ok
    assert checks[0].missing == 57


def test_possible_tickets():
    """C(4, 2) · C(3, 1) = 6 · 3 = 18."""
    rules = [make_rule(1, 1, 2, 1), make_rule(2, 2, 1, 2)]
    assert possible_tickets(rules, {(1, 1): 4, (2, 2): 3}) == 18
