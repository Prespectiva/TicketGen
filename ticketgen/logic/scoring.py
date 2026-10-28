"""Подсчёт баллов билета и проверка, хватает ли вопросов для шаблона."""

import math
from dataclasses import dataclass

from ticketgen.domain.models import TemplateRule


@dataclass
class RuleCheck:
    """Результат проверки одного правила шаблона."""

    rule: TemplateRule
    available: int
    required: int

    @property
    def ok(self) -> bool:
        """True, если подходящих вопросов достаточно."""
        return self.available >= self.required

    @property
    def missing(self) -> int:
        """Сколько вопросов не хватает (0, если хватает)."""
        return max(0, self.required - self.available)


def ticket_score(rules: list[TemplateRule]) -> int:
    """Суммарный балл билета: S = Σ(kᵢ · wᵢ).

    kᵢ — число вопросов по правилу, wᵢ — вес сложности.
    """
    return sum(rule.questions_count * rule.weight for rule in rules)


def score_formula(rules: list[TemplateRule]) -> str:
    """Строка с расчётом балла для интерфейса, например «1×1 + 2×3 = 7»."""
    if not rules:
        return "0"
    parts = [f"{rule.questions_count}×{rule.weight}" for rule in rules]
    return " + ".join(parts) + f" = {ticket_score(rules)}"


def check_rules(
    rules: list[TemplateRule],
    available: dict[tuple[int, int], int],
    variants_count: int = 1,
    no_overlap: bool = False,
) -> list[RuleCheck]:
    """Проверяет каждое правило шаблона.

    Обычный режим требует n ≥ k, режим «без пересечений» — n ≥ m·k,
    где n — вопросов в банке, k — вопросов в правиле, m — число билетов.

    Args:
        rules: правила шаблона.
        available: число активных вопросов по паре (тема, сложность).
        variants_count: сколько билетов нужно создать.
        no_overlap: включён ли режим «без пересечений».
    """
    checks = []
    for rule in rules:
        required = rule.questions_count
        if no_overlap:
            required *= variants_count
        count = available.get((rule.topic_id, rule.difficulty_id), 0)
        checks.append(RuleCheck(rule, count, required))
    return checks


def possible_tickets(rules: list[TemplateRule], available: dict) -> int:
    """Сколько разных билетов можно составить: произведение C(n, k)."""
    if not rules:
        return 0
    total = 1
    for rule in rules:
        count = available.get((rule.topic_id, rule.difficulty_id), 0)
        total *= math.comb(count, rule.questions_count)
    return total
