"""Тесты предметов, оформления билета, шаблона CSV и выгрузки в Moodle."""

import sqlite3
import struct
import zlib
import xml.etree.ElementTree as ET

from docx import Document

from ticketgen.data.database import Database
from ticketgen.domain.models import Question
from ticketgen.logic import moodle
from ticketgen.logic.csv_importer import parse_csv, read_text, write_template
from ticketgen.logic.exporters import build_answers, build_tickets, export_series
from ticketgen.logic.generator import generate_variants, ticket_title

LEVELS = {"лёгкий": 1, "средний": 2, "сложный": 3}


def test_find_by_subject(repos):
    """Фильтр по предмету оставляет только вопросы его тем."""
    topic_id = repos["topics"].add("Базы данных", "SQL")
    repos["questions"].add(Question(None, topic_id, 1, "теория", "Что такое JOIN?"))
    assert repos["topics"].disciplines() == ["Базы данных", "ОАиП"]
    found = repos["questions"].find(discipline="Базы данных")
    assert [q.question_text for q in found] == ["Что такое JOIN?"]
    assert found[0].discipline == "Базы данных"
    assert len(repos["questions"].find(discipline="ОАиП")) == 96


def test_old_database_gets_style_columns(tmp_path):
    """В базе первой версии при открытии появляются столбцы оформления."""
    path = tmp_path / "old.db"
    connection = sqlite3.connect(path)
    connection.execute(
        "CREATE TABLE tbl_templates (id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "template_name TEXT UNIQUE NOT NULL, header_text TEXT DEFAULT '')"
    )
    connection.execute(
        "INSERT INTO tbl_templates (template_name, header_text) VALUES ('Старый', '')"
    )
    connection.commit()
    connection.close()

    db = Database(path)
    row = db.connection.execute("SELECT * FROM tbl_templates").fetchone()
    assert row["template_name"] == "Старый"
    assert row["doc_kind"] == "Экзаменационный билет"
    assert row["teacher_sign"] == 0
    db.close()


def test_template_style_is_saved(repos):
    """Вид документа, эмблема и подписи сохраняются в шаблоне."""
    template = repos["templates"].get_all()[0]
    template.subject = "ОАиП"
    template.doc_kind = "Контрольная работа"
    template.logo_path = "logos/emblem.png"
    template.teacher_sign = True
    template.student_line = True
    repos["templates"].update(template)
    saved = repos["templates"].get(template.id)
    assert saved.doc_kind == "Контрольная работа"
    assert saved.number_word == "Вариант"
    assert saved.logo_path == "logos/emblem.png"
    assert saved.teacher_sign and saved.student_line


def test_ticket_title_uses_kind_word():
    """Без метки {N} номер выводится второй строкой с нужным словом."""
    assert ticket_title("Контрольная работа", 2, "Вариант").endswith("Вариант № 2")
    assert ticket_title("Билет № {N}", 2, "Вариант") == "Билет № 2"


def _logo(tmp_path):
    """Маленькая синяя PNG-картинка 8×8 для эмблемы (без сторонних библиотек)."""

    def chunk(kind: bytes, data: bytes) -> bytes:
        body = kind + data
        return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body))

    rows = b"".join(b"\x00" + b"\x25\x63\xeb" * 8 for _ in range(8))
    png = (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", 8, 8, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(rows))
        + chunk(b"IEND", b"")
    )
    path = tmp_path / "logo.png"
    path.write_bytes(png)
    return path


def test_styled_export(tmp_path, repos):
    """Эмблема, строка студента и подпись попадают в DOCX и PDF."""
    template = repos["templates"].get_all()[0]
    template.doc_kind = "Контрольная работа"
    template.logo_path = str(_logo(tmp_path))
    template.teacher_sign = True
    template.student_line = True
    pool = repos["questions"].find(only_active=True)
    variants = generate_variants(template.rules, pool, 2, seed=1)

    blocks = build_tickets("Контрольная работа по ОАиП", variants, template)
    kinds = [kind for kind, _ in blocks]
    assert kinds.count("logo_title") == 2
    assert kinds.count("field") == 4
    logo_path, title = next(value for kind, value in blocks if kind == "logo_title")
    assert title == "Контрольная работа по ОАиП\nВариант № 1"

    files = export_series(
        tmp_path / "out",
        "кр",
        "Контрольная работа по ОАиП",
        variants,
        ["docx", "pdf"],
        template=template,
    )
    assert [path.name for path in files] == [
        "кр_билеты.docx",
        "кр_билеты.pdf",
        "кр_ответы.docx",
        "кр_ведомость.docx",
    ]
    document = Document(files[0])
    assert len(document.inline_shapes) == 2
    # Эмблема в левой ячейке, заголовок — в правой ячейке той же строки.
    first_row = document.tables[0].rows[0].cells
    assert first_row[1].text.endswith("Вариант № 1")
    text = "\n".join(p.text for p in document.paragraphs)
    assert "ФИО студента" in text and "Преподаватель" in text


def test_csv_template_is_empty(tmp_path):
    """Шаблон CSV — только строка заголовков, импорт его принимает."""
    path = tmp_path / "шаблон.csv"
    write_template(path)
    assert path.read_bytes().startswith(b"\xef\xbb\xbf")  # BOM для Excel
    text = read_text(path)
    assert text.strip() == "дисциплина;тема;сложность;тип;вопрос;ответ"
    assert parse_csv(text, LEVELS) == ([], [])


def test_answers_table(tmp_path, repos):
    """Ответы — одна таблица: билет, номер вопроса, ответ."""
    template = repos["templates"].get_all()[0]
    pool = repos["questions"].find(only_active=True)
    variants = generate_variants(template.rules, pool, 3, seed=8)
    blocks = build_answers("Экзамен", variants)
    kind, rows = blocks[1]
    assert kind == "answers"
    assert rows[0] == ["Билет", "№", "Ответ"]
    assert len(rows) == 1 + 3 * len(template.rules)
    assert rows[1][:2] == ["1", "1"] and rows[2][0] == ""
    files = export_series(
        tmp_path, "s", "Экзамен", variants, ["docx"], with_summary=False
    )
    document = Document(files[1])
    table = document.tables[0]
    assert table.cell(1, 0).text == "1"
    assert table.cell(1, 2).text == rows[1][2]


def test_subject_column_alias():
    """Первый столбец можно назвать «предмет»."""
    text = (
        "предмет;тема;сложность;тип;вопрос;ответ\nБД;SQL;лёгкий;теория;Что такое SQL?;"
    )
    rows, errors = parse_csv(text, LEVELS)
    assert not errors and rows[0].discipline == "БД"


def test_moodle_tickets_xml(repos):
    """Moodle XML: категория на каждый билет, вопросы — эссе, текст экранирован."""
    template = repos["templates"].get_all()[0]
    pool = repos["questions"].find(only_active=True)
    variants = generate_variants(template.rules, pool, 3, seed=2)
    variants[0].questions[0].question_text = "Сравните a < b & c > d"
    groups = moodle.ticket_groups("Экзамен по ОАиП", variants, "Билет")
    root = ET.fromstring(moodle.to_moodle_xml(groups).encode("utf-8"))
    categories = [
        q.find("category/text").text for q in root if q.get("type") == "category"
    ]
    assert categories == [
        f"$course$/top/Экзамен по ОАиП/Билет № {n}" for n in (1, 2, 3)
    ]
    essays = [q for q in root if q.get("type") == "essay"]
    assert len(essays) == 3 * len(template.rules)
    assert "a &lt; b &amp; c" in essays[0].find("questiontext/text").text


def test_moodle_one_ticket(tmp_path, repos):
    """Один выбранный билет — один тест (одна категория)."""
    template = repos["templates"].get_all()[0]
    pool = repos["questions"].find(only_active=True)
    variant = generate_variants(template.rules, pool, 2, seed=4)[1]
    path = tmp_path / "один.xml"
    moodle.save_tickets(path, "КР", [variant], "Вариант", "xml")
    root = ET.parse(path).getroot()
    categories = [q for q in root if q.get("type") == "category"]
    assert len(categories) == 1
    assert categories[0].find("category/text").text.endswith("КР/Вариант № 2")


def test_gift_escapes_special_chars():
    """В GIFT служебные символы экранируются, ответ идёт в отзыв."""
    question = Question(7, 1, 1, "теория", "Что вернёт {1: 2}?", "Словарь")
    text = moodle.to_gift([("$course$/top/КР/Вариант № 1", [question])])
    assert "$CATEGORY: $course$/top/КР/Вариант № 1" in text
    assert "Что вернёт \\{1\\: 2\\}?{####Словарь}" in text


def test_two_tickets_per_page(repos):
    """Билеты идут парами: между билетами пары — линия отреза, пары с нового листа."""
    template = repos["templates"].get_all()[0]
    pool = repos["questions"].find(only_active=True)
    variants = generate_variants(template.rules, pool, 5, seed=6)
    kinds = [kind for kind, _ in build_tickets("Экзамен", variants)]
    separators = [kind for kind in kinds if kind in ("gap", "break")]
    assert separators == ["gap", "break", "gap", "break"]
    assert kinds.count("ticket") == 5
