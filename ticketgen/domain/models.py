"""Сущности предметной области (классы-данные) и ошибки приложения."""

from dataclasses import dataclass, field

QUESTION_TYPES = ["теория", "задача", "практика"]

# Вид документа → слово перед номером («Билет № 3», «Вариант № 3»).
DOC_KINDS = {
    "Экзаменационный билет": "Билет",
    "Зачётный билет": "Билет",
    "Контрольная работа": "Вариант",
    "Самостоятельная работа": "Вариант",
    "Тест": "Вариант",
}
DEFAULT_DOC_KIND = "Экзаменационный билет"
DEFAULT_SIGN_TEXT = "Преподаватель ________________ / ________________"
STUDENT_LINE_TEXT = "ФИО студента ________________________  Группа ________"


def kind_number_word(doc_kind: str) -> str:
    """Слово перед номером для вида документа; для своего вида — «Вариант»."""
    return DOC_KINDS.get(doc_kind, "Вариант")


class TicketGenError(Exception):
    """Ошибка, текст которой можно показать пользователю."""


class NotEnoughQuestionsError(TicketGenError):
    """В банке не хватает вопросов для шаблона."""


@dataclass
class Topic:
    """Тема дисциплины (таблица tbl_topics)."""

    id: int | None
    discipline: str
    topic_name: str

    @property
    def title(self) -> str:
        """Название для списков: «Дисциплина: тема»."""
        return f"{self.discipline}: {self.topic_name}"


@dataclass
class Difficulty:
    """Уровень сложности с весом в баллах (таблица tbl_difficulty)."""

    id: int
    level_name: str
    weight: int


@dataclass
class Question:
    """Вопрос из банка (таблица tbl_questions).

    Поля topic_name, level_name и weight заполняются из связанных таблиц
    при чтении и нужны только для отображения.
    """

    id: int | None
    topic_id: int
    difficulty_id: int
    q_type: str
    question_text: str
    answer_text: str = ""
    is_active: bool = True
    topic_name: str = ""
    level_name: str = ""
    weight: int = 0
    discipline: str = ""


@dataclass
class TemplateRule:
    """Правило шаблона: тема + сложность + количество вопросов."""

    id: int | None
    template_id: int
    topic_id: int
    difficulty_id: int
    questions_count: int
    topic_name: str = ""
    level_name: str = ""
    weight: int = 0


@dataclass
class Template:
    """Шаблон билета (таблица tbl_templates) со списком правил.

    Кроме правил шаблон хранит оформление: предмет, вид документа
    (экзамен, контрольная...), эмблему и места для подписей.
    """

    id: int | None
    template_name: str
    header_text: str = ""
    rules: list[TemplateRule] = field(default_factory=list)
    subject: str = ""
    doc_kind: str = DEFAULT_DOC_KIND
    logo_path: str = ""
    teacher_sign: bool = False
    sign_text: str = DEFAULT_SIGN_TEXT
    student_line: bool = False

    @property
    def number_word(self) -> str:
        """«Билет» или «Вариант» в зависимости от вида документа."""
        return kind_number_word(self.doc_kind)


@dataclass
class Series:
    """Серия билетов, созданных за одну генерацию (таблица tbl_series)."""

    id: int | None
    template_id: int
    created_at: str
    seed: int
    no_overlap: bool
    variants_count: int
    template_name: str = ""
    header_text: str = ""


@dataclass
class Variant:
    """Один билет серии со списком вопросов (tbl_variants)."""

    id: int | None
    series_id: int | None
    variant_no: int
    total_score: int
    questions: list[Question] = field(default_factory=list)
