"""Импорт вопросов из CSV."""
import csv
import io
from dataclasses import dataclass, field
from pathlib import Path

from ticketgen.domain.models import QUESTION_TYPES, Question, TicketGenError

COLUMNS = ["дисциплина", "тема", "сложность", "тип", "вопрос", "ответ"]


@dataclass
class ParsedRow:
    """Корректная строка CSV, готовая к добавлению в базу."""

    discipline: str
    topic_name: str
    difficulty_id: int
    q_type: str
    question_text: str
    answer_text: str


@dataclass
class ImportResult:
    """Итог импорта: сколько добавлено и какие строки пропущены."""

    imported: int = 0
    errors: list[tuple[int, str]] = field(default_factory=list)


def read_text(path: Path) -> str:
    """Читает файл в UTF-8, а если не получилось — в Windows-1251.

    Excel на русской Windows часто сохраняет CSV в кодировке cp1251.
    """
    raw = Path(path).read_bytes()
    for encoding in ("utf-8-sig", "cp1251"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise TicketGenError("Файл не похож на текстовый CSV.")


def parse_csv(text: str, difficulty_ids: dict[str, int]):
    """Разбирает текст CSV и проверяет каждую строку.

    Args:
        text: содержимое файла.
        difficulty_ids: соответствие «название сложности → id».

    Returns:
        Кортеж (список ParsedRow, список ошибок (номер строки, причина)).

    Raises:
        TicketGenError: если файл пустой или в заголовке не те столбцы.
    """
    lines = text.splitlines()
    if not lines:
        raise TicketGenError("Файл пустой.")
    delimiter = ";" if ";" in lines[0] else ","
    reader = csv.reader(io.StringIO(text), delimiter=delimiter)
    header = [cell.strip().lower() for cell in next(reader)]
    if header[:5] != COLUMNS[:5]:
        raise TicketGenError(
            "Неверный заголовок. Нужны столбцы: " + delimiter.join(COLUMNS)
        )

    rows, errors = [], []
    for line_no, cells in enumerate(reader, start=2):
        if not any(cell.strip() for cell in cells):
            continue  # пустые строки просто пропускаем
        try:
            rows.append(_parse_row(cells, difficulty_ids))
        except ValueError as error:
            errors.append((line_no, str(error)))
    return rows, errors


def _parse_row(cells: list[str], difficulty_ids: dict[str, int]) -> ParsedRow:
    """Проверяет одну строку и превращает её в ParsedRow.

    Raises:
        ValueError: с описанием ошибки, если строка некорректна.
    """
    cells = [cell.strip() for cell in cells] + [""] * len(COLUMNS)
    discipline, topic, level, q_type, question, answer = cells[: len(COLUMNS)]
    if not discipline or not topic:
        raise ValueError("не указана дисциплина или тема")
    if not question:
        raise ValueError("пустой текст вопроса")
    level = level.lower().replace("легкий", "лёгкий")
    if level not in difficulty_ids:
        raise ValueError(f"неизвестная сложность «{level}»")
    q_type = q_type.lower() or "теория"
    if q_type not in QUESTION_TYPES:
        raise ValueError(f"неизвестный тип «{q_type}»")
    return ParsedRow(discipline, topic, difficulty_ids[level], q_type, question, answer)


def import_questions(path, topic_repo, question_repo, difficulty_repo) -> ImportResult:
    """Загружает вопросы из CSV в базу.

    Строки с ошибками пропускаются и попадают в отчёт, все корректные
    строки добавляются одной транзакцией.
    """
    difficulty_ids = {d.level_name: d.id for d in difficulty_repo.get_all()}
    rows, errors = parse_csv(read_text(path), difficulty_ids)
    questions = []
    for row in rows:
        topic_id = topic_repo.get_or_create(row.discipline, row.topic_name)
        questions.append(
            Question(
                id=None,
                topic_id=topic_id,
                difficulty_id=row.difficulty_id,
                q_type=row.q_type,
                question_text=row.question_text,
                answer_text=row.answer_text,
            )
        )
    question_repo.add_many(questions)
    return ImportResult(imported=len(questions), errors=errors)