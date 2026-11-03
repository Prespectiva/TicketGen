"""Экспорт в DOCX и PDF."""

from abc import ABC, abstractmethod
from pathlib import Path
from xml.sax.saxutils import escape

from ticketgen.config import AppConfig
from ticketgen.domain.models import STUDENT_LINE_TEXT, Template, TicketGenError, Variant
from ticketgen.logic.generator import plain_header, ticket_title

# Блок — кортеж (вид, значение): ("title", str), ("text", str),
# ("table", список строк таблицы), ("break", None),
# ("logo_title", (путь к эмблеме, заголовок)) — эмблема в левом верхнем
# углу и заголовок рядом с ней, ("field", строка для заполнения от руки:
# ФИО студента, подпись преподавателя), ("ticket", None) — начало билета,
# ("gap", None) — линия отреза между двумя билетами на одном листе.

TICKETS_PER_PAGE = 2

# Оценка высоты билета в DOCX (в пунктах). Лист A4 с полями по 2,54 см
# даёт 698 pt; оценка высоты билета нарочно завышена — это и есть запас.
DOCX_PAGE_HEIGHT = 698
GAP_HEIGHT = 48
CHARS_PER_LINE = 70  # Times New Roman 14 pt на ширине текста A4
LINE_HEIGHT = 18
TITLE_LINE_HEIGHT = 22


def _lines(text: str, chars_per_line: int = CHARS_PER_LINE) -> int:
    """Сколько строк займёт текст с переносами."""
    return sum(max(1, -(-len(line) // chars_per_line)) for line in text.split("\n"))


def ticket_heights(blocks: list[tuple]) -> list[float]:
    """Примерная высота каждого билета в пунктах (для раскладки по листам)."""
    heights: list[float] = []
    for kind, value in blocks:
        if kind == "ticket":
            heights.append(0)
        elif not heights:
            continue
        elif kind == "title":
            heights[-1] += _lines(value, 50) * TITLE_LINE_HEIGHT + 30
        elif kind == "logo_title":
            title_height = _lines(value[1], 40) * TITLE_LINE_HEIGHT + 30
            heights[-1] += max(LOGO_WIDTH_CM * 28.35 + 12, title_height)
        elif kind == "field":
            heights[-1] += _lines(value) * LINE_HEIGHT + 18 + 10
        elif kind == "text":
            heights[-1] += _lines(value) * LINE_HEIGHT + 10
    return heights


LOGO_WIDTH_CM = 3.0


def logo_file(template: Template | None) -> Path | None:
    """Путь к эмблеме шаблона, если она задана и файл существует."""
    if template and template.logo_path:
        path = Path(template.logo_path)
        if path.is_file():
            return path
    return None


def build_tickets(
    header: str, variants: list[Variant], template: Template | None = None
) -> list[tuple]:
    """Блоки файла с билетами (без ответов).

    Если передан шаблон, учитывается его оформление: эмблема над
    заголовком, слово «Билет» или «Вариант», строка для ФИО студента
    и место для подписи преподавателя.
    """
    word = template.number_word if template else "Билет"
    logo = logo_file(template)
    blocks = []
    for index, variant in enumerate(variants):
        # Билеты идут парами: второй билет пары ставится на тот же лист
        # под линией отреза, если помещается целиком (иначе — на новый
        # лист); следующая пара всегда начинается с нового листа.
        if index % TICKETS_PER_PAGE:
            blocks.append(("gap", None))
        elif index:
            blocks.append(("break", None))
        blocks.append(("ticket", None))
        title = ticket_title(header, variant.variant_no, word)
        if logo:
            blocks.append(("logo_title", (logo, title)))
        else:
            blocks.append(("title", title))
        if template and template.student_line:
            blocks.append(("field", STUDENT_LINE_TEXT))
        for number, question in enumerate(variant.questions, 1):
            blocks.append(("text", f"{number}. {question.question_text}"))
        if template and template.teacher_sign and template.sign_text.strip():
            blocks.append(("field", template.sign_text.strip()))
    return blocks


def topics_text(questions) -> str:
    """Темы билета со счётчиком: «Циклы ×2, Функции»."""
    counts: dict[str, int] = {}
    for question in questions:
        counts[question.topic_name] = counts.get(question.topic_name, 0) + 1
    return ", ".join(
        f"{name} ×{count}" if count > 1 else name for name, count in counts.items()
    )


def build_answers(
    header: str, variants: list[Variant], word: str = "Билет"
) -> list[tuple]:
    """Блоки файла с эталонными ответами: одна компактная таблица.

    Столбцы: номер билета, номер вопроса, ответ. Номер билета пишется в
    первой строке билета, остальные ячейки столбца объединяются с ней.
    """
    rows = [[word, "№", "Ответ"]]
    for variant in variants:
        for number, question in enumerate(variant.questions, 1):
            rows.append(
                [
                    str(variant.variant_no) if number == 1 else "",
                    str(number),
                    question.answer_text or "—",
                ]
            )
    title = f"{plain_header(header)}\nОтветы для преподавателя"
    return [("title", title), ("answers", rows)]


def build_summary(
    header: str, variants: list[Variant], word: str = "Билет"
) -> list[tuple]:
    """Блоки сводной ведомости: билет, состав, балл."""
    rows = [[word, "Вопросы (id)", "Темы", "Балл"]]
    for variant in variants:
        rows.append(
            [
                str(variant.variant_no),
                ", ".join(str(question.id) for question in variant.questions),
                topics_text(variant.questions),
                str(variant.total_score),
            ]
        )
    title = f"{plain_header(header)}\nСводная ведомость"
    return [("title", title), ("table", rows)]


class BaseExporter(ABC):
    """Общий интерфейс экспортёров."""

    extension = ""

    @abstractmethod
    def save(self, blocks: list[tuple], path: Path):
        """Сохраняет блоки в файл.

        Args:
            blocks: содержимое документа.
            path: путь к файлу без расширения.
        """


class DocxExporter(BaseExporter):
    """Сохранение в Word (.docx) через python-docx."""

    extension = ".docx"

    def save(self, blocks, path):
        """Создаёт документ Word из блоков."""
        from docx import Document
        from docx.shared import Cm, Pt

        document = Document()
        # Шаблон python-docx по умолчанию — американский Letter; ставим A4.
        section = document.sections[0]
        section.page_width, section.page_height = Cm(21), Cm(29.7)
        style = document.styles["Normal"]
        style.font.name = "Times New Roman"
        style.font.size = Pt(14)
        heights = ticket_heights(blocks)
        ticket_no = -1
        for kind, value in blocks:
            if kind == "ticket":
                ticket_no += 1
            elif kind == "logo_title":
                self._logo_title(document, *value)
            elif kind == "title":
                document.add_heading(value, level=1)
            elif kind == "field":
                paragraph = document.add_paragraph(value)
                paragraph.paragraph_format.space_before = Pt(18)
            elif kind == "text":
                document.add_paragraph(value)
            elif kind == "gap":
                # Word сам не умеет переносить билет целиком, поэтому высоту
                # пары оцениваем заранее: не помещается — новый лист.
                pair = heights[ticket_no] + heights[ticket_no + 1] + GAP_HEIGHT
                if pair <= DOCX_PAGE_HEIGHT:
                    self._cut_line(document)
                else:
                    document.add_page_break()
            elif kind == "break":
                document.add_page_break()
            elif kind == "table":
                table = document.add_table(rows=0, cols=len(value[0]))
                table.style = "Table Grid"
                for row in value:
                    cells = table.add_row().cells
                    for cell, text in zip(cells, row):
                        cell.text = text
            elif kind == "answers":
                self._answers_table(document, value)
        document.save(path.with_suffix(self.extension))

    @staticmethod
    def _answers_table(document, rows: list[list[str]]):
        """Ответы одной таблицей: шрифт 11 pt, узкие столбцы номеров.

        Ячейки номера билета объединяются по всем вопросам билета, строка
        заголовков повторяется на каждом листе.
        """
        from docx.oxml import OxmlElement
        from docx.oxml.ns import qn
        from docx.shared import Cm, Pt

        table = document.add_table(rows=len(rows), cols=3)
        table.style = "Table Grid"
        table.autofit = False
        section = document.sections[-1]
        text_width = section.page_width - section.left_margin - section.right_margin
        widths = (Cm(2), Cm(1), text_width - Cm(3))
        for row_index, (row_cells, values) in enumerate(zip(table.rows, rows)):
            for column, (cell, text) in enumerate(zip(row_cells.cells, values)):
                cell.width = widths[column]
                paragraph = cell.paragraphs[0]
                paragraph.paragraph_format.space_after = Pt(0)
                run = paragraph.add_run(text)
                run.font.size = Pt(11)
                run.bold = row_index == 0
        for column, width in zip(table.columns, widths):
            column.width = width
        header = table.rows[0]._tr.get_or_add_trPr()
        repeat = OxmlElement("w:tblHeader")
        repeat.set(qn("w:val"), "true")
        header.append(repeat)
        # Объединяем ячейки номера билета: от строки с номером до следующего.
        starts = [index for index, row in enumerate(rows) if index and row[0]]
        for start, end in zip(starts, starts[1:] + [len(rows)]):
            if end - 1 > start:
                text = table.cell(start, 0).text
                merged = table.cell(start, 0).merge(table.cell(end - 1, 0))
                for paragraph in merged.paragraphs[1:]:
                    paragraph._p.getparent().remove(paragraph._p)
                if merged.text != text:
                    merged.paragraphs[0].runs[0].text = text

    @staticmethod
    def _cut_line(document):
        """Пунктирная линия отреза между двумя билетами на одном листе."""
        from docx.oxml import OxmlElement
        from docx.oxml.ns import qn
        from docx.shared import Pt

        paragraph = document.add_paragraph()
        paragraph.paragraph_format.space_before = Pt(12)
        paragraph.paragraph_format.space_after = Pt(18)
        borders = OxmlElement("w:pBdr")
        bottom = OxmlElement("w:bottom")
        for name, value in (
            ("w:val", "dashed"),
            ("w:sz", "6"),
            ("w:space", "1"),
            ("w:color", "999999"),
        ):
            bottom.set(qn(name), value)
        borders.append(bottom)
        paragraph._p.get_or_add_pPr().append(borders)

    @staticmethod
    def _logo_title(document, logo: Path, title: str):
        """Эмблема в левом верхнем углу, заголовок по центру справа от неё.

        Строится таблицей из двух ячеек без рамок: так эмблема не сдвигает
        заголовок вниз.
        """
        from docx.enum.table import WD_CELL_VERTICAL_ALIGNMENT
        from docx.enum.text import WD_ALIGN_PARAGRAPH
        from docx.shared import Cm

        table = document.add_table(rows=1, cols=2)
        table.autofit = False
        logo_cell, title_cell = table.rows[0].cells
        page = document.sections[-1]
        text_width = page.page_width - page.left_margin - page.right_margin
        widths = (Cm(LOGO_WIDTH_CM + 0.5), text_width - Cm(LOGO_WIDTH_CM + 0.5))
        # Ширину задаём и столбцам, и ячейкам: Word смотрит на ячейки,
        # LibreOffice — на столбцы.
        for column, cell, width in zip(table.columns, (logo_cell, title_cell), widths):
            column.width = width
            cell.width = width
        logo_paragraph = logo_cell.paragraphs[0]
        logo_paragraph.alignment = WD_ALIGN_PARAGRAPH.LEFT
        logo_paragraph.add_run().add_picture(str(logo), width=Cm(LOGO_WIDTH_CM))
        title_paragraph = title_cell.paragraphs[0]
        title_paragraph.style = document.styles["Heading 1"]
        title_paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
        title_paragraph.add_run(title)
        title_cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER


class PdfExporter(BaseExporter):
    """Сохранение в PDF через reportlab с кириллическим шрифтом."""

    extension = ".pdf"
    font_name = "TicketGenFont"

    def save(self, blocks, path):
        """Создаёт PDF из блоков."""
        from reportlab.lib.enums import TA_CENTER
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
        from reportlab.lib.units import cm, inch
        from reportlab.lib.utils import ImageReader
        from reportlab.platypus import (
            HRFlowable,
            Image,
            KeepTogether,
            PageBreak,
            Paragraph,
            SimpleDocTemplate,
            Spacer,
            Table,
        )

        self._register_font()
        styles = getSampleStyleSheet()
        for style in styles.byName.values():
            style.fontName = self.font_name
        story = []
        main_story = story
        for kind, value in blocks:
            if kind in ("ticket", "gap", "break") and story is not main_story:
                # Билет целиком: если не помещается на остаток листа,
                # переносится на следующий.
                main_story.append(KeepTogether(story))
                story = main_story
            if kind == "ticket":
                story = []
            elif kind == "gap":
                story += [
                    Spacer(1, 12),
                    HRFlowable(width="100%", dash=(4, 3), color="#999999"),
                    Spacer(1, 18),
                ]
            elif kind == "logo_title":
                logo, title = value
                image_width, image_height = ImageReader(str(logo)).getSize()
                width = LOGO_WIDTH_CM * cm
                image = Image(str(logo), width, width * image_height / image_width)
                text = escape(title).replace("\n", "<br/>")
                heading = ParagraphStyle(
                    "centered", parent=styles["Heading2"], alignment=TA_CENTER
                )
                row = Table(
                    [[image, Paragraph(text, heading)]],
                    # Поля страницы SimpleDocTemplate — по 1 дюйму.
                    colWidths=[width + 0.5 * cm, A4[0] - 2 * inch - width - 0.5 * cm],
                )
                row.setStyle(
                    [
                        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                        ("LEFTPADDING", (0, 0), (0, 0), 0),
                    ]
                )
                story += [row, Spacer(1, 8)]
            elif kind == "title":
                text = escape(value).replace("\n", "<br/>")
                story += [Paragraph(text, styles["Heading2"]), Spacer(1, 8)]
            elif kind == "field":
                story += [Spacer(1, 18), Paragraph(escape(value), styles["Normal"])]
            elif kind == "text":
                story.append(Paragraph(escape(value), styles["Normal"]))
            elif kind == "break":
                story.append(PageBreak())
            elif kind == "table":
                cells = [
                    [Paragraph(escape(text), styles["Normal"]) for text in row]
                    for row in value
                ]
                table = Table(cells, colWidths=[40, 130, 220, 40])
                table.setStyle([("GRID", (0, 0), (-1, -1), 0.5, "black")])
                story.append(table)
            elif kind == "answers":
                story.append(self._answers_table(value, styles))
        if story is not main_story:
            main_story.append(KeepTogether(story))
        SimpleDocTemplate(str(path.with_suffix(self.extension)), pagesize=A4).build(
            main_story
        )

    @staticmethod
    def _answers_table(rows, styles):
        """Ответы одной таблицей мелким шрифтом; номер билета объединён."""
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import ParagraphStyle
        from reportlab.lib.units import inch
        from reportlab.platypus import Paragraph, Table

        small = ParagraphStyle("small", parent=styles["Normal"], fontSize=9, leading=11)
        cells = [[Paragraph(escape(text), small) for text in row] for row in rows]
        table = Table(
            cells,
            colWidths=[45, 25, A4[0] - 2 * inch - 70],
            repeatRows=1,
        )
        commands = [
            ("GRID", (0, 0), (-1, -1), 0.5, "black"),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("BACKGROUND", (0, 0), (-1, 0), "#F1F5F9"),
            ("TOPPADDING", (0, 0), (-1, -1), 1),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ]
        starts = [index for index, row in enumerate(rows) if index and row[0]]
        for start, end in zip(starts, starts[1:] + [len(rows)]):
            if end - 1 > start:
                commands.append(("SPAN", (0, start), (0, end - 1)))
        table.setStyle(commands)
        return table

    def _register_font(self):
        """Подключает TTF-шрифт с русскими буквами.

        Без него reportlab выводит кириллицу квадратиками.
        """
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont

        if self.font_name in pdfmetrics.getRegisteredFontNames():
            return
        candidates = [
            AppConfig().base_dir / "fonts" / "DejaVuSans.ttf",
            Path("C:/Windows/Fonts/arial.ttf"),
            Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
        ]
        for font_path in candidates:
            if font_path.exists():
                pdfmetrics.registerFont(TTFont(self.font_name, str(font_path)))
                return
        raise TicketGenError("Не найден шрифт с кириллицей для PDF.")


class ExporterFactory:
    """Фабрика: возвращает экспортёр по названию формата."""

    _exporters = {"docx": DocxExporter, "pdf": PdfExporter}

    @classmethod
    def create(cls, file_format: str) -> BaseExporter:
        """Создаёт экспортёр для формата «docx» или «pdf»."""
        if file_format not in cls._exporters:
            raise TicketGenError(f"Неизвестный формат: {file_format}")
        return cls._exporters[file_format]()


def export_series(
    folder: Path,
    base_name: str,
    header: str,
    variants: list[Variant],
    formats: list[str],
    with_answers: bool = True,
    with_summary: bool = True,
    progress=None,
    with_tickets: bool = True,
    template: Template | None = None,
) -> list[Path]:
    """Сохраняет серию: билеты в каждом формате, ответы и ведомость.

    Ответы и ведомость сохраняются в первом выбранном формате. Если
    передан шаблон, билеты оформляются по нему (эмблема, вид документа,
    места для подписей).

    Returns:
        Список созданных файлов.
    """
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    word = template.number_word if template else "Билет"
    jobs = []
    if with_tickets:
        jobs = [
            (fmt, "билеты", build_tickets(header, variants, template))
            for fmt in formats
        ]
    if with_answers:
        jobs.append((formats[0], "ответы", build_answers(header, variants, word)))
    if with_summary:
        jobs.append((formats[0], "ведомость", build_summary(header, variants, word)))

    created = []
    for done, (fmt, suffix, blocks) in enumerate(jobs, 1):
        exporter = ExporterFactory.create(fmt)
        path = folder / f"{base_name}_{suffix}"
        try:
            exporter.save(blocks, path)
        except PermissionError as error:
            raise TicketGenError(
                f"Нет доступа к файлу {path.name}{exporter.extension}. "
                "Возможно, он открыт в Word — закройте его."
            ) from error
        created.append(path.with_suffix(exporter.extension))
        if progress:
            progress(int(done * 100 / len(jobs)))
    return created
