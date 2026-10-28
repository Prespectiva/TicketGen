"""Репозитории (паттерн Repository): весь SQL программы находится здесь.

Все запросы параметризованные: значения передаются через «?», а не
склейкой строк. Это защищает от SQL-инъекций.
"""

import sqlite3

from ticketgen.domain.models import (
    Difficulty,
    Question,
    Series,
    Template,
    TemplateRule,
    TicketGenError,
    Topic,
    Variant,
)


class BaseRepository:
    """Общий предок репозиториев: хранит подключение к базе."""

    def __init__(self, db):
        """Запоминает объект Database."""
        self.db = db

    def _query(self, sql, params=()):
        """Выполняет SELECT и возвращает все строки."""
        return self.db.connection.execute(sql, params).fetchall()

    def _execute(self, sql, params=()):
        """Выполняет изменяющий запрос в транзакции и возвращает курсор."""
        try:
            with self.db.connection:
                return self.db.connection.execute(sql, params)
        except sqlite3.IntegrityError as error:
            raise TicketGenError(_integrity_message(error)) from error


def _integrity_message(error):
    """Переводит ошибку ограничения SQLite в понятный текст."""
    text = str(error)
    if "FOREIGN KEY" in text:
        return "Запись используется в других данных, её нельзя удалить."
    if "UNIQUE" in text:
        return "Такая запись уже существует."
    return f"Данные не прошли проверку: {text}"


class TopicRepository(BaseRepository):
    """CRUD для таблицы tbl_topics."""

    def get_all(self) -> list[Topic]:
        """Возвращает все темы по алфавиту."""
        rows = self._query("SELECT * FROM tbl_topics ORDER BY discipline, topic_name")
        return [Topic(row["id"], row["discipline"], row["topic_name"]) for row in rows]

    def add(self, discipline: str, topic_name: str) -> int:
        """Добавляет тему и возвращает её id."""
        cursor = self._execute(
            "INSERT INTO tbl_topics (discipline, topic_name) VALUES (?, ?)",
            (discipline, topic_name),
        )
        return cursor.lastrowid

    def get_or_create(self, discipline: str, topic_name: str) -> int:
        """Возвращает id темы, при необходимости создаёт её (для импорта)."""
        rows = self._query(
            "SELECT id FROM tbl_topics WHERE discipline = ? AND topic_name = ?",
            (discipline, topic_name),
        )
        if rows:
            return rows[0]["id"]
        return self.add(discipline, topic_name)

    def update(self, topic: Topic):
        """Сохраняет новое название темы."""
        self._execute(
            "UPDATE tbl_topics SET discipline = ?, topic_name = ? WHERE id = ?",
            (topic.discipline, topic.topic_name, topic.id),
        )

    def delete(self, topic_id: int):
        """Удаляет тему. Тему с вопросами удалить нельзя."""
        self._execute("DELETE FROM tbl_topics WHERE id = ?", (topic_id,))


class DifficultyRepository(BaseRepository):
    """Чтение и изменение весов в справочнике tbl_difficulty."""

    def get_all(self) -> list[Difficulty]:
        """Возвращает уровни сложности от лёгкого к сложному."""
        rows = self._query("SELECT * FROM tbl_difficulty ORDER BY weight")
        return [Difficulty(row["id"], row["level_name"], row["weight"]) for row in rows]

    def update_weight(self, difficulty_id: int, weight: int):
        """Меняет вес уровня сложности в баллах."""
        self._execute(
            "UPDATE tbl_difficulty SET weight = ? WHERE id = ?", (weight, difficulty_id)
        )


QUESTION_SELECT = """
    SELECT q.*, t.topic_name, d.level_name, d.weight
    FROM tbl_questions q
    JOIN tbl_topics t ON t.id = q.topic_id
    JOIN tbl_difficulty d ON d.id = q.difficulty_id
"""


def _row_to_question(row) -> Question:
    """Превращает строку результата запроса в объект Question."""
    return Question(
        id=row["id"],
        topic_id=row["topic_id"],
        difficulty_id=row["difficulty_id"],
        q_type=row["q_type"],
        question_text=row["question_text"],
        answer_text=row["answer_text"] or "",
        is_active=bool(row["is_active"]),
        topic_name=row["topic_name"],
        level_name=row["level_name"],
        weight=row["weight"],
    )


class QuestionRepository(BaseRepository):
    """CRUD для банка вопросов (tbl_questions)."""

    def find(
        self,
        text="",
        topic_id=None,
        difficulty_id=None,
        q_type=None,
        only_active=False,
    ) -> list[Question]:
        """Ищет вопросы по тексту и фильтрам.

        Пустые фильтры не применяются. Условия собираются из готовых строк,
        а значения передаются параметрами.
        """
        conditions, params = [], []
        if text:
            conditions.append("q.question_text LIKE ?")
            params.append(f"%{text}%")
        if topic_id:
            conditions.append("q.topic_id = ?")
            params.append(topic_id)
        if difficulty_id:
            conditions.append("q.difficulty_id = ?")
            params.append(difficulty_id)
        if q_type:
            conditions.append("q.q_type = ?")
            params.append(q_type)
        if only_active:
            conditions.append("q.is_active = 1")
        sql = QUESTION_SELECT
        if conditions:
            sql += " WHERE " + " AND ".join(conditions)
        sql += " ORDER BY q.id"
        return [_row_to_question(row) for row in self._query(sql, params)]

    def get(self, question_id: int) -> Question | None:
        """Возвращает вопрос по id или None."""
        rows = self._query(QUESTION_SELECT + " WHERE q.id = ?", (question_id,))
        return _row_to_question(rows[0]) if rows else None

    def add(self, question: Question) -> int:
        """Добавляет вопрос и возвращает его id."""
        cursor = self._execute(
            "INSERT INTO tbl_questions (topic_id, difficulty_id, q_type, "
            "question_text, answer_text, is_active) VALUES (?, ?, ?, ?, ?, ?)",
            _question_values(question),
        )
        return cursor.lastrowid

    def add_many(self, questions: list[Question]):
        """Добавляет много вопросов в одной транзакции (для импорта)."""
        with self.db.connection:
            self.db.connection.executemany(
                "INSERT INTO tbl_questions (topic_id, difficulty_id, q_type, "
                "question_text, answer_text, is_active) VALUES (?, ?, ?, ?, ?, ?)",
                [_question_values(question) for question in questions],
            )

    def update(self, question: Question):
        """Сохраняет изменения вопроса."""
        self._execute(
            "UPDATE tbl_questions SET topic_id = ?, difficulty_id = ?, q_type = ?, "
            "question_text = ?, answer_text = ?, is_active = ? WHERE id = ?",
            (*_question_values(question), question.id),
        )

    def set_active(self, question_id: int, active: bool):
        """Включает или отключает участие вопроса в генерации."""
        self._execute(
            "UPDATE tbl_questions SET is_active = ? WHERE id = ?",
            (int(active), question_id),
        )

    def delete(self, question_id: int):
        """Удаляет вопрос. Вопрос из сохранённых билетов удалить нельзя."""
        self._execute("DELETE FROM tbl_questions WHERE id = ?", (question_id,))

    def count(self) -> int:
        """Возвращает общее число вопросов."""
        return self._query("SELECT COUNT(*) FROM tbl_questions")[0][0]

    def count_by_topic_and_difficulty(self) -> dict[tuple[int, int], int]:
        """Считает активные вопросы для каждой пары (тема, сложность)."""
        rows = self._query(
            "SELECT topic_id, difficulty_id, COUNT(*) AS cnt FROM tbl_questions "
            "WHERE is_active = 1 GROUP BY topic_id, difficulty_id"
        )
        return {(row["topic_id"], row["difficulty_id"]): row["cnt"] for row in rows}


def _question_values(question: Question) -> tuple:
    """Значения полей вопроса в порядке столбцов INSERT/UPDATE."""
    return (
        question.topic_id,
        question.difficulty_id,
        question.q_type,
        question.question_text,
        question.answer_text,
        int(question.is_active),
    )


class TemplateRepository(BaseRepository):
    """CRUD для шаблонов (tbl_templates) и их правил (tbl_template_rules)."""

    def get_all(self) -> list[Template]:
        """Возвращает все шаблоны вместе с правилами."""
        rows = self._query("SELECT * FROM tbl_templates ORDER BY template_name")
        return [self._build(row) for row in rows]

    def get(self, template_id: int) -> Template | None:
        """Возвращает шаблон с правилами или None."""
        rows = self._query("SELECT * FROM tbl_templates WHERE id = ?", (template_id,))
        return self._build(rows[0]) if rows else None

    def _build(self, row) -> Template:
        """Собирает объект Template и загружает его правила."""
        template = Template(row["id"], row["template_name"], row["header_text"] or "")
        template.rules = self.get_rules(template.id)
        return template

    def get_rules(self, template_id: int) -> list[TemplateRule]:
        """Возвращает правила шаблона с названиями темы и сложности."""
        rows = self._query(
            "SELECT r.*, t.topic_name, d.level_name, d.weight "
            "FROM tbl_template_rules r "
            "JOIN tbl_topics t ON t.id = r.topic_id "
            "JOIN tbl_difficulty d ON d.id = r.difficulty_id "
            "WHERE r.template_id = ? ORDER BY r.id",
            (template_id,),
        )
        return [
            TemplateRule(
                id=row["id"],
                template_id=row["template_id"],
                topic_id=row["topic_id"],
                difficulty_id=row["difficulty_id"],
                questions_count=row["questions_count"],
                topic_name=row["topic_name"],
                level_name=row["level_name"],
                weight=row["weight"],
            )
            for row in rows
        ]

    def add(self, template_name: str, header_text: str = "") -> int:
        """Создаёт шаблон и возвращает его id."""
        cursor = self._execute(
            "INSERT INTO tbl_templates (template_name, header_text) VALUES (?, ?)",
            (template_name, header_text),
        )
        return cursor.lastrowid

    def update(self, template: Template):
        """Сохраняет название и заголовок шаблона."""
        self._execute(
            "UPDATE tbl_templates SET template_name = ?, header_text = ? WHERE id = ?",
            (template.template_name, template.header_text, template.id),
        )

    def delete(self, template_id: int):
        """Удаляет шаблон (правила удаляются каскадно)."""
        self._execute("DELETE FROM tbl_templates WHERE id = ?", (template_id,))

    def add_rule(self, rule: TemplateRule) -> int:
        """Добавляет правило в шаблон."""
        cursor = self._execute(
            "INSERT INTO tbl_template_rules "
            "(template_id, topic_id, difficulty_id, questions_count) "
            "VALUES (?, ?, ?, ?)",
            (rule.template_id, rule.topic_id, rule.difficulty_id, rule.questions_count),
        )
        return cursor.lastrowid

    def update_rule_count(self, rule_id: int, questions_count: int):
        """Меняет количество вопросов в правиле."""
        self._execute(
            "UPDATE tbl_template_rules SET questions_count = ? WHERE id = ?",
            (questions_count, rule_id),
        )

    def update_rule_target(self, rule_id: int, topic_id: int, difficulty_id: int):
        """Меняет тему и сложность правила."""
        self._execute(
            "UPDATE tbl_template_rules SET topic_id = ?, difficulty_id = ? "
            "WHERE id = ?",
            (topic_id, difficulty_id, rule_id),
        )

    def delete_rule(self, rule_id: int):
        """Удаляет правило."""
        self._execute("DELETE FROM tbl_template_rules WHERE id = ?", (rule_id,))


class SeriesRepository(BaseRepository):
    """Сохранение и чтение серий билетов (tbl_series, tbl_variants, ...)."""

    def save(self, series: Series, variants: list[Variant]) -> int:
        """Сохраняет серию со всеми билетами в одной транзакции.

        Если на любом шаге произойдёт ошибка, в базу не попадёт ничего.

        Returns:
            id новой серии.
        """
        connection = self.db.connection
        with connection:
            cursor = connection.execute(
                "INSERT INTO tbl_series (template_id, created_at, seed, no_overlap, "
                "variants_count) VALUES (?, ?, ?, ?, ?)",
                (
                    series.template_id,
                    series.created_at,
                    series.seed,
                    int(series.no_overlap),
                    series.variants_count,
                ),
            )
            series_id = cursor.lastrowid
            for variant in variants:
                cursor = connection.execute(
                    "INSERT INTO tbl_variants (series_id, variant_no, total_score) "
                    "VALUES (?, ?, ?)",
                    (series_id, variant.variant_no, variant.total_score),
                )
                variant_id = cursor.lastrowid
                connection.executemany(
                    "INSERT INTO tbl_variant_questions "
                    "(variant_id, question_id, position) VALUES (?, ?, ?)",
                    [
                        (variant_id, question.id, position)
                        for position, question in enumerate(variant.questions, 1)
                    ],
                )
        return series_id

    def get_all(self) -> list[Series]:
        """Возвращает все серии, новые сверху."""
        rows = self._query(
            "SELECT s.*, t.template_name, t.header_text FROM tbl_series s "
            "JOIN tbl_templates t ON t.id = s.template_id ORDER BY s.id DESC"
        )
        return [
            Series(
                id=row["id"],
                template_id=row["template_id"],
                created_at=row["created_at"],
                seed=row["seed"],
                no_overlap=bool(row["no_overlap"]),
                variants_count=row["variants_count"],
                template_name=row["template_name"],
                header_text=row["header_text"] or "",
            )
            for row in rows
        ]

    def get_variants(self, series_id: int) -> list[Variant]:
        """Возвращает билеты серии вместе с вопросами по порядку."""
        variant_rows = self._query(
            "SELECT * FROM tbl_variants WHERE series_id = ? ORDER BY variant_no",
            (series_id,),
        )
        variants = []
        for row in variant_rows:
            question_rows = self._query(
                QUESTION_SELECT
                + " JOIN tbl_variant_questions vq ON vq.question_id = q.id "
                "WHERE vq.variant_id = ? ORDER BY vq.position",
                (row["id"],),
            )
            variants.append(
                Variant(
                    id=row["id"],
                    series_id=series_id,
                    variant_no=row["variant_no"],
                    total_score=row["total_score"],
                    questions=[_row_to_question(q_row) for q_row in question_rows],
                )
            )
        return variants

    def replace_question(self, variant_id: int, old_id: int, new_id: int):
        """Заменяет вопрос в билете, порядковый номер сохраняется."""
        self._execute(
            "UPDATE tbl_variant_questions SET question_id = ? "
            "WHERE variant_id = ? AND question_id = ?",
            (new_id, variant_id, old_id),
        )

    def delete(self, series_id: int):
        """Удаляет серию (билеты и их вопросы удаляются каскадно)."""
        self._execute("DELETE FROM tbl_series WHERE id = ?", (series_id,))

    def count(self) -> int:
        """Возвращает число сохранённых серий."""
        return self._query("SELECT COUNT(*) FROM tbl_series")[0][0]