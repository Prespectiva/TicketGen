"""Тесты импорта вопросов из CSV."""

import pytest

from ticketgen.domain.models import TicketGenError
from ticketgen.logic.csv_importer import import_questions, parse_csv

DIFFICULTY = {"лёгкий": 1, "средний": 2, "сложный": 3}
HEADER = "дисциплина;тема;сложность;тип;вопрос;ответ\n"


def test_good_row():
    """Корректная строка разбирается без ошибок."""
    rows, errors = parse_csv(
        HEADER + "ОАиП;Циклы;средний;задача;Вопрос;Ответ", DIFFICULTY
    )
    assert len(rows) == 1 and not errors
    assert rows[0].difficulty_id == 2


def test_bad_rows_are_reported():
    """Ошибочные строки пропускаются и попадают в отчёт с номером строки."""
    text = HEADER + "ОАиП;Циклы;средний;задача;;\nОАиП;Циклы;очень;теория;Вопрос;\n"
    rows, errors = parse_csv(text, DIFFICULTY)
    assert rows == []
    assert [line for line, _ in errors] == [2, 3]


def test_wrong_header():
    """Файл без нужного заголовка не импортируется."""
    with pytest.raises(TicketGenError):
        parse_csv("a;b;c\n1;2;3", DIFFICULTY)


def test_import_cp1251_file(tmp_path, repos):
    """Файл в кодировке Windows-1251 читается и попадает в базу."""
    path = tmp_path / "questions.csv"
    text = HEADER + "ОАиП;Словари;легкий;теория;Что такое dict?;Словарь\n"
    path.write_bytes(text.encode("cp1251"))
    result = import_questions(
        path, repos["topics"], repos["questions"], repos["difficulty"]
    )
    assert result.imported == 1
    assert repos["questions"].count() == 97
