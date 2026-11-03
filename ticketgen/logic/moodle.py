"""Выгрузка билетов в форматы Moodle: Moodle XML и GIFT.

Каждый билет становится категорией вопросов «Серия / Билет № N», из
которой в Moodle собирается тест. Вопросы открытые (ответ пишет студент),
поэтому в Moodle это вопросы типа «Эссе». Эталонный ответ попадает в
«Информацию для оценщика» (XML) или в общий отзыв (GIFT) — студент его
не видит. Вес сложности становится баллом вопроса.

Файл импортируется в Moodle через «Банк вопросов → Импорт».
"""

from pathlib import Path
from xml.sax.saxutils import escape

from ticketgen.domain.models import Question, TicketGenError, Variant

NAME_LENGTH = 60  # длина короткого названия вопроса в Moodle


def short_name(question: Question) -> str:
    """Короткое название вопроса для списка в Moodle: номер и начало текста."""
    text = " ".join(question.question_text.split())
    if len(text) > NAME_LENGTH:
        text = text[: NAME_LENGTH - 1].rstrip() + "…"
    return f"{question.id}. {text}" if question.id else text


def _category_path(*parts: str) -> str:
    """Путь категории Moodle: «$course$/top/Предмет/Тема».

    Косая черта внутри названия удваивается, иначе Moodle примет её за
    разделитель уровней.
    """
    clean = [part.replace("/", "//").strip() for part in parts if part.strip()]
    return "/".join(["$course$/top", *clean])


def _html(text: str) -> str:
    """Текст для поля HTML: спецсимволы экранируются, переносы строк сохраняются."""
    return escape(text).replace("\n", "<br>")


def _xml_category(path: str) -> str:
    """Служебный «вопрос» Moodle XML, задающий категорию для следующих вопросов."""
    return (
        '  <question type="category">\n'
        f"    <category><text>{escape(path)}</text></category>\n"
        "  </question>\n"
    )


def _xml_essay(question: Question) -> str:
    """Один вопрос типа «Эссе» в формате Moodle XML."""
    grade = question.weight or 1
    return (
        '  <question type="essay">\n'
        f"    <name><text>{escape(short_name(question))}</text></name>\n"
        '    <questiontext format="html">\n'
        f"      <text>{escape(_html(question.question_text))}</text>\n"
        "    </questiontext>\n"
        '    <generalfeedback format="html"><text></text></generalfeedback>\n'
        f"    <defaultgrade>{grade}</defaultgrade>\n"
        "    <penalty>0</penalty>\n"
        "    <hidden>0</hidden>\n"
        "    <responseformat>editor</responseformat>\n"
        "    <responserequired>1</responserequired>\n"
        "    <responsefieldlines>10</responsefieldlines>\n"
        "    <attachments>0</attachments>\n"
        '    <graderinfo format="html">\n'
        f"      <text>{escape(_html(question.answer_text))}</text>\n"
        "    </graderinfo>\n"
        '    <responsetemplate format="html"><text></text></responsetemplate>\n'
        f"    <tags><tag><text>{escape(question.level_name)}</text></tag></tags>\n"
        "  </question>\n"
    )


def _xml_document(groups: list[tuple[str, list[Question]]]) -> str:
    """Файл Moodle XML: для каждой группы категория, затем её вопросы."""
    parts = ['<?xml version="1.0" encoding="UTF-8"?>\n<quiz>\n']
    for category, questions in groups:
        parts.append(_xml_category(category))
        parts.extend(_xml_essay(question) for question in questions)
    parts.append("</quiz>\n")
    return "".join(parts)


def ticket_groups(
    title: str, variants: list[Variant], word: str
) -> list[tuple[str, list[Question]]]:
    """Категории для билетов: «Название серии / Билет № N» и вопросы билета."""
    series_title = " ".join(title.split()) or "Серия билетов"
    return [
        (
            _category_path(series_title, f"{word} № {variant.variant_no}"),
            variant.questions,
        )
        for variant in variants
    ]


def to_moodle_xml(groups: list[tuple[str, list[Question]]]) -> str:
    """Билеты в формате Moodle XML: категория билета, затем его вопросы."""
    return _xml_document(groups)


def _gift_escape(text: str) -> str:
    """Экранирует служебные символы GIFT: ~ = # { } :."""
    for char in "\\~=#{}:":
        text = text.replace(char, "\\" + char)
    return text.replace("\n", "\\n")


def to_gift(groups: list[tuple[str, list[Question]]]) -> str:
    """Билеты в формате GIFT (текстовый формат Moodle).

    Пустые фигурные скобки означают вопрос-эссе, эталонный ответ записан
    как общий отзыв после «####».
    """
    lines = []
    for category, questions in groups:
        lines += [f"$CATEGORY: {category}", ""]
        for question in questions:
            feedback = (
                f"####{_gift_escape(question.answer_text)}"
                if question.answer_text
                else ""
            )
            lines.append(
                f"::{_gift_escape(short_name(question))}::"
                f"{_gift_escape(question.question_text)}{{{feedback}}}"
            )
            lines.append("")
    return "\n".join(lines)


def _write(path: Path, text: str):
    """Сохраняет текст в UTF-8; понятная ошибка, если файл занят."""
    try:
        Path(path).write_text(text, encoding="utf-8")
    except PermissionError as error:
        raise TicketGenError(
            f"Нет доступа к файлу {Path(path).name}. "
            "Возможно, он открыт в другой программе — закройте его."
        ) from error


def save_tickets(
    path: Path, title: str, variants: list[Variant], word: str, file_format: str
):
    """Сохраняет билеты для импорта в Moodle.

    Каждый билет попадает в свою категорию «Серия / Билет № N»: из неё в
    Moodle собирается отдельный тест. Если передан один билет, получается
    один тест.

    Args:
        path: файл для сохранения.
        title: название серии (заголовок без номера).
        variants: все билеты серии или один выбранный.
        word: «Билет» или «Вариант».
        file_format: «xml» (Moodle XML) или «gift».
    """
    if not variants:
        raise TicketGenError("Нет билетов для выгрузки.")
    groups = ticket_groups(title, variants, word)
    if file_format == "xml":
        _write(path, to_moodle_xml(groups))
    elif file_format == "gift":
        _write(path, to_gift(groups))
    else:
        raise TicketGenError(f"Неизвестный формат Moodle: {file_format}")
