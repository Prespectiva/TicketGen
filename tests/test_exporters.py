"""Тесты экспорта в DOCX и PDF."""

from ticketgen.domain.models import Question, Variant
from ticketgen.logic.exporters import (
    build_answers,
    build_summary,
    export_series,
    topics_text,
)
from ticketgen.logic.generator import generate_variants, plain_header


def test_export_creates_files(tmp_path, repos):
    """Экспорт создаёт билеты в двух форматах, ответы и ведомость."""
    template = repos["templates"].get_all()[0]
    pool = repos["questions"].find(only_active=True)
    variants = generate_variants(template.rules, pool, 5, seed=3)
    files = export_series(tmp_path, "серия_1", "Экзамен", variants, ["docx", "pdf"])
    assert len(files) == 4
    assert all(path.exists() and path.stat().st_size > 0 for path in files)


def test_series_files_have_no_number_placeholder():
    """В ответах и ведомости из заголовка убрана метка «{N}»."""
    header = "Экзаменационный билет № {N} по дисциплине «ОАиП»"
    assert plain_header(header) == "Экзаменационный билет по дисциплине «ОАиП»"
    for blocks in (build_answers(header, []), build_summary(header, [])):
        assert "{N}" not in blocks[0][1]


def test_summary_counts_repeated_topics():
    """Повторяющиеся темы выводятся как «Тема ×N», в ведомости тоже."""
    questions = [
        Question(i, 1, 1, "теория", "?", topic_name=name)
        for i, name in enumerate(["Циклы", "Циклы", "Функции"], 1)
    ]
    assert topics_text(questions) == "Циклы ×2, Функции"
    variant = Variant(None, None, 1, 3, questions)
    assert build_summary("Экзамен", [variant])[1][1][1][2] == "Циклы ×2, Функции"
