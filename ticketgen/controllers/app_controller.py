"""Контроллер (MVC)."""
from datetime import datetime
from pathlib import Path

from PyQt6.QtCore import QObject, pyqtSignal

from ticketgen.config import AppConfig
from ticketgen.data.database import Database
from ticketgen.data.repositories import (
    DifficultyRepository,
    QuestionRepository,
    SeriesRepository,
    TemplateRepository,
    TopicRepository,
)
from ticketgen.domain.models import Question, Series, Template, TemplateRule, Topic
from ticketgen.logic import csv_importer, scoring


class AppController(QObject):
    """Единая точка входа для всех действий пользователя."""

    questions_changed = pyqtSignal()
    templates_changed = pyqtSignal()
    series_changed = pyqtSignal()

    def __init__(self, db: Database):
        """Создаёт репозитории поверх подключения к базе."""
        super().__init__()
        self.db = db
        self.topics = TopicRepository(db)
        self.difficulty = DifficultyRepository(db)
        self.questions = QuestionRepository(db)
        self.templates = TemplateRepository(db)
        self.series = SeriesRepository(db)
        # Если банк меняется, меняются и цифры «В банке» у шаблонов.
        self.questions_changed.connect(self.templates_changed.emit)

    # ----- Темы -----

    def get_topics(self) -> list[Topic]:
        """Список всех тем."""
        return self.topics.get_all()

    def add_topic(self, discipline: str, topic_name: str):
        """Создаёт тему."""
        self.topics.add(discipline, topic_name)
        self.questions_changed.emit()

    def rename_topic(self, topic: Topic):
        """Сохраняет новое название темы."""
        self.topics.update(topic)
        self.questions_changed.emit()

    def delete_topic(self, topic_id: int):
        """Удаляет тему без вопросов."""
        self.topics.delete(topic_id)
        self.questions_changed.emit()

    # ----- Банк вопросов -----

    def get_difficulties(self):
        """Уровни сложности."""
        return self.difficulty.get_all()

    def find_questions(self, **filters) -> list[Question]:
        """Поиск вопросов (фильтры передаются в репозиторий)."""
        return self.questions.find(**filters)

    def save_question(self, question: Question):
        """Добавляет новый вопрос или сохраняет изменённый."""
        if question.id is None:
            self.questions.add(question)
        else:
            self.questions.update(question)
        self.questions_changed.emit()

    def toggle_question(self, question: Question):
        """Включает или отключает вопрос."""
        self.questions.set_active(question.id, not question.is_active)
        self.questions_changed.emit()

    def delete_question(self, question_id: int):
        """Удаляет вопрос."""
        self.questions.delete(question_id)
        self.questions_changed.emit()

    def import_csv(self, path) -> csv_importer.ImportResult:
        """Импортирует вопросы из CSV-файла."""
        result = csv_importer.import_questions(
            path, self.topics, self.questions, self.difficulty
        )
        self.questions_changed.emit()
        return result

    def available_counts(self) -> dict:
        """Число активных вопросов по парам (тема, сложность)."""
        return self.questions.count_by_topic_and_difficulty()

    # ----- Шаблоны -----

    def get_templates(self) -> list[Template]:
        """Все шаблоны с правилами."""
        return self.templates.get_all()

    def get_template(self, template_id: int) -> Template | None:
        """Один шаблон с правилами."""
        return self.templates.get(template_id)

    def create_template(self, name: str, header: str = "") -> int:
        """Создаёт шаблон."""
        template_id = self.templates.add(name, header)
        self.templates_changed.emit()
        return template_id

    def update_template(self, template: Template):
        """Сохраняет название и заголовок шаблона."""
        self.templates.update(template)
        self.templates_changed.emit()

    def delete_template(self, template_id: int):
        """Удаляет шаблон."""
        self.templates.delete(template_id)
        self.templates_changed.emit()

    def add_rule(self, rule: TemplateRule):
        """Добавляет правило в шаблон."""
        self.templates.add_rule(rule)
        self.templates_changed.emit()

    def update_rule_count(self, rule_id: int, count: int):
        """Меняет число вопросов в правиле."""
        self.templates.update_rule_count(rule_id, count)
        self.templates_changed.emit()

    def update_rule_target(self, rule_id: int, topic_id: int, difficulty_id: int):
        """Меняет тему и сложность правила."""
        self.templates.update_rule_target(rule_id, topic_id, difficulty_id)
        self.templates_changed.emit()

    def delete_rule(self, rule_id: int):
        """Удаляет правило."""
        self.templates.delete_rule(rule_id)
        self.templates_changed.emit()

    def check_template(self, template: Template, count=1, no_overlap=False):
        """Проверяет шаблон: результат по каждому правилу и число билетов."""
        available = self.available_counts()
        checks = scoring.check_rules(template.rules, available, count, no_overlap)
        possible = scoring.possible_tickets(template.rules, available)
        return checks, possible

    # ----- Серии -----

    def active_pool(self) -> list[Question]:
        """Все активные вопросы для генератора."""
        return self.questions.find(only_active=True)

    def save_series(self, template: Template, seed, no_overlap, variants) -> int:
        """Сохраняет созданную серию в историю."""
        series = Series(
            id=None,
            template_id=template.id,
            created_at=datetime.now().strftime("%Y-%m-%d %H:%M"),
            seed=seed,
            no_overlap=no_overlap,
            variants_count=len(variants),
        )
        series_id = self.series.save(series, variants)
        self.series_changed.emit()
        return series_id

    def get_series(self) -> list[Series]:
        """История серий."""
        return self.series.get_all()

    def get_variants(self, series_id: int):
        """Билеты серии."""
        return self.series.get_variants(series_id)

    def replacement_candidates(self, variant, question) -> list[Question]:
        """Вопросы той же темы и сложности, которых ещё нет в билете."""
        used = {q.id for q in variant.questions}
        same = self.questions.find(
            topic_id=question.topic_id,
            difficulty_id=question.difficulty_id,
            only_active=True,
        )
        return [q for q in same if q.id not in used]

    def replace_question(self, variant_id: int, old_id: int, new_id: int):
        """Заменяет вопрос в билете."""
        self.series.replace_question(variant_id, old_id, new_id)
        self.series_changed.emit()

    def delete_series(self, series_id: int):
        """Удаляет серию."""
        self.series.delete(series_id)
        self.series_changed.emit()

    # ----- Служебное -----

    def stats(self) -> str:
        """Текст для строки состояния."""
        total = self.questions.count()
        active = len(self.questions.find(only_active=True))
        return (
            f"База: {Path(self.db.path).name} · Вопросов: {total} "
            f"(активных {active}) · Шаблонов: {len(self.templates.get_all())}"
        )

    def backup(self):
        """Создаёт резервную копию базы (вызывается при закрытии)."""
        config = AppConfig()
        if self.db.path != ":memory:":
            return self.db.backup(config.backup_dir, config.backups_to_keep)
        return None