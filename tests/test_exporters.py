"""Тесты экспорта в DOCX и PDF."""

from ticketgen.logic.exporters import export_series
from ticketgen.logic.generator import generate_variants


def test_export_creates_files(tmp_path, repos):
    """Экспорт создаёт билеты в двух форматах, ответы и ведомость."""
    template = repos["templates"].get_all()[0]
    pool = repos["questions"].find(only_active=True)
    variants = generate_variants(template.rules, pool, 5, seed=3)
    files = export_series(tmp_path, "серия_1", "Экзамен", variants, ["docx", "pdf"])
    assert len(files) == 4
    assert all(path.exists() and path.stat().st_size > 0 for path in files)
