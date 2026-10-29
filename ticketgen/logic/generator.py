"""Алгоритм генерации серии билетов по шаблону."""

import math
import random

from ticketgen.domain.models import (
    NotEnoughQuestionsError,
    Question,
    TemplateRule,
    TicketGenError,
    Variant,
)

MAX_ATTEMPTS = 1000  # сколько раз пробовать собрать билет, не совпадающий с другими


def random_seed() -> int:
    """Возвращает случайный seed, если пользователь его не задал."""
    return random.randint(1, 999_999)


def generate_variants(
    rules: list[TemplateRule],
    pool: list[Question],
    variants_count: int,
    seed: int,
    no_overlap: bool = False,
    progress=None,
) -> list[Variant]:
    """Создаёт заданное число билетов.

    Правила алгоритма:
    * для каждого правила берётся k разных вопросов нужной темы и сложности,
      поэтому внутри билета вопросы не повторяются;
    * два билета с одинаковым набором вопросов не допускаются;
    * в режиме no_overlap вопрос используется в серии только один раз;
    * одинаковый seed всегда даёт одинаковую серию.

    Args:
        rules: правила шаблона.
        pool: все активные вопросы банка.
        variants_count: сколько билетов создать.
        seed: число для генератора случайных чисел.
        no_overlap: режим «не повторять вопросы между билетами».
        progress: функция, которой передаётся процент выполнения (0–100).

    Raises:
        NotEnoughQuestionsError: если вопросов не хватает.
    """
    if not rules:
        raise TicketGenError("В шаблоне нет ни одного правила.")
    rng = random.Random(seed)
    candidates = [_candidates_for(rule, pool) for rule in rules]
    _check_enough(rules, candidates, variants_count, no_overlap)

    used_sets = set()
    variants = []
    for variant_no in range(1, variants_count + 1):
        questions = _pick_unique(rules, candidates, rng, used_sets)
        ids = frozenset(question.id for question in questions)
        used_sets.add(ids)
        if no_overlap:
            # Убираем выбранные вопросы из всех списков кандидатов.
            candidates = [[q for q in group if q.id not in ids] for group in candidates]
        total = sum(question.weight for question in questions)
        variants.append(Variant(None, None, variant_no, total, questions))
        if progress:
            progress(int(variant_no * 100 / variants_count))
    return variants


def _candidates_for(rule: TemplateRule, pool: list[Question]) -> list[Question]:
    """Отбирает активные вопросы нужной темы и сложности, сортирует по id.

    Сортировка нужна, чтобы при одинаковом seed результат был одинаковым.
    """
    matching = [
        question
        for question in pool
        if question.topic_id == rule.topic_id
        and question.difficulty_id == rule.difficulty_id
        and question.is_active
    ]
    return sorted(matching, key=lambda question: question.id)


def _check_enough(rules, candidates, variants_count, no_overlap):
    """Проверяет, что вопросов хватит на всю серию."""
    for rule, group in zip(rules, candidates):
        need = rule.questions_count * (variants_count if no_overlap else 1)
        if len(group) < need:
            raise NotEnoughQuestionsError(
                f"Тема «{rule.topic_name}», сложность «{rule.level_name}»: "
                f"нужно {need}, в банке {len(group)}."
            )
    if not no_overlap:
        possible = math.prod(
            math.comb(len(group), rule.questions_count)
            for rule, group in zip(rules, candidates)
        )
        if possible < variants_count:
            raise NotEnoughQuestionsError(
                f"Из банка можно составить только {possible} разных билетов."
            )


def _pick_unique(rules, candidates, rng, used_sets) -> list[Question]:
    """Собирает билет, которого ещё нет в серии."""
    for _ in range(MAX_ATTEMPTS):
        questions = []
        for rule, group in zip(rules, candidates):
            questions.extend(rng.sample(group, rule.questions_count))
        if frozenset(question.id for question in questions) not in used_sets:
            return questions
    raise TicketGenError("Не удалось составить уникальный билет. Пополните банк.")


def ticket_title(header: str, number: int) -> str:
    """Заголовок билета: «{N}» заменяется номером, иначе номер на второй строке."""
    if "{N}" in header:
        return header.replace("{N}", str(number))
    return f"{header}\nБилет № {number}"