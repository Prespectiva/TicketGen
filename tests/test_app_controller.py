"""Интеграционные тесты контроллера: контроллер + репозитории + SQLite.

Каждый тест работает с настоящей базой в памяти, заполненной тестовыми
данными (4 темы, 96 вопросов, 1 шаблон), и проверяет и результат в базе,
и сигналы, по которым обновляются вкладки интерфейса.
"""

import pytest

from ticketgen.config import AppConfig
from ticketgen.controllers.app_controller import AppController
from ticketgen.data.database import Database
from ticketgen.domain.models import Question, TemplateRule, TicketGenError
from ticketgen.logic.generator import generate_variants

HEADER = "дисциплина;тема;сложность;тип;вопрос;ответ\n"


@pytest.fixture
def controller(filled_db):
    """Контроллер поверх заполненной базы."""
    return AppController(filled_db)


@pytest.fixture
def signals(controller):
    """Запоминает, какие сигналы контроллер отправил во время теста."""
    sent = []
    controller.questions_changed.connect(lambda: sent.append("questions"))
    controller.templates_changed.connect(lambda: sent.append("templates"))
    controller.series_changed.connect(lambda: sent.append("series"))
    return sent


def _make_series(controller, count=3, no_overlap=False):
    """Генерирует и сохраняет серию по шаблону из тестовых данных."""
    template = controller.get_templates()[0]
    variants = generate_variants(
        template.rules, controller.active_pool(), count, seed=42, no_overlap=no_overlap
    )
    return template, controller.save_series(template, 42, no_overlap, variants)


# ----- Темы -----


def test_topic_add_rename_delete(controller, signals):
    """Тему можно создать, переименовать и удалить через контроллер."""
    controller.add_topic("ОАиП", "Словари")
    topic = next(t for t in controller.get_topics() if t.topic_name == "Словари")
    assert topic.title == "ОАиП: Словари"

    topic.topic_name = "Словари и множества"
    controller.rename_topic(topic)
    names = [t.topic_name for t in controller.get_topics()]
    assert "Словари и множества" in names

    controller.delete_topic(topic.id)
    assert len(controller.get_topics()) == 4
    # Изменение банка обновляет и вкладку «Банк», и цифры в шаблонах.
    assert signals.count("questions") == 3
    assert signals.count("templates") == 3


def test_delete_topic_with_questions_fails(controller, signals):
    """Тема с вопросами не удаляется, сигнал не отправляется."""
    topic_id = controller.get_topics()[0].id
    with pytest.raises(TicketGenError):
        controller.delete_topic(topic_id)
    assert len(controller.get_topics()) == 4
    assert signals == []


# ----- Банк вопросов -----


def test_question_save_toggle_delete(controller, signals):
    """Новый вопрос добавляется, правится, отключается и удаляется."""
    topic_id = controller.get_topics()[0].id
    controller.save_question(
        Question(None, topic_id, 1, "теория", "Уникальный вопрос", "Ответ")
    )
    question = controller.find_questions(text="Уникальный вопрос")[0]
    assert question.answer_text == "Ответ"
    assert question.is_active

    question.question_text = "Уникальный вопрос, новая редакция"
    controller.save_question(question)
    assert controller.find_questions(text="новая редакция")[0].id == question.id

    controller.toggle_question(question)
    found = controller.find_questions(text="новая редакция")[0]
    assert not found.is_active
    assert found not in controller.active_pool()

    controller.delete_question(question.id)
    assert controller.find_questions(text="новая редакция") == []
    assert signals.count("questions") == 4


def test_find_questions_by_filters(controller):
    """Фильтры по теме и сложности доходят до репозитория."""
    topic_id = controller.get_topics()[0].id
    found = controller.find_questions(topic_id=topic_id, difficulty_id=3)
    assert len(found) == 8
    assert {q.level_name for q in found} == {"сложный"}


def test_difficulties(controller):
    """Справочник сложностей: 1, 2 и 3 балла."""
    weights = [d.weight for d in controller.get_difficulties()]
    assert weights == [1, 2, 3]


def test_import_csv(controller, signals, tmp_path):
    """Импорт CSV добавляет корректные строки и сообщает об ошибочных."""
    path = tmp_path / "import.csv"
    path.write_text(
        HEADER
        + "ОАиП;Словари;лёгкий;теория;Что такое dict?;Словарь\n"
        + "ОАиП;Словари;очень;теория;Ошибочная сложность;\n",
        encoding="utf-8",
    )
    result = controller.import_csv(path)
    assert result.imported == 1
    assert [line for line, _ in result.errors] == [3]
    assert len(controller.find_questions()) == 97
    assert "questions" in signals


def test_available_counts(controller):
    """По каждой паре (тема, сложность) в тестовой базе 8 вопросов."""
    counts = controller.available_counts()
    assert len(counts) == 12
    assert set(counts.values()) == {8}


# ----- Шаблоны -----


def test_template_and_rules_crud(controller, signals):
    """Шаблон и его правила создаются, изменяются и удаляются."""
    template_id = controller.create_template("Зачёт", "Билет № {N}")
    template = controller.get_template(template_id)
    assert template.header_text == "Билет № {N}"

    template.template_name = "Зачёт по ОАиП"
    controller.update_template(template)
    assert controller.get_template(template_id).template_name == "Зачёт по ОАиП"

    topics = controller.get_topics()
    controller.add_rule(TemplateRule(None, template_id, topics[0].id, 1, 1))
    rule = controller.get_template(template_id).rules[0]

    controller.update_rule_count(rule.id, 2)
    controller.update_rule_target(rule.id, topics[1].id, 3)
    rule = controller.get_template(template_id).rules[0]
    assert (rule.topic_id, rule.difficulty_id, rule.questions_count) == (
        topics[1].id,
        3,
        2,
    )

    controller.delete_rule(rule.id)
    assert controller.get_template(template_id).rules == []

    controller.delete_template(template_id)
    assert controller.get_template(template_id) is None
    assert len(controller.get_templates()) == 1
    assert signals.count("templates") == 7


def test_check_template_enough_questions(controller):
    """Для шаблона из тестовых данных вопросов хватает: 8⁴ разных билетов."""
    template = controller.get_templates()[0]
    checks, possible = controller.check_template(template, count=5)
    assert all(check.ok for check in checks)
    assert possible == 8**4


def test_check_template_no_overlap_shortage(controller):
    """В режиме «без пересечений» на 10 билетов не хватает по 2 вопроса."""
    template = controller.get_templates()[0]
    checks, _ = controller.check_template(template, count=10, no_overlap=True)
    assert not any(check.ok for check in checks)
    assert {check.missing for check in checks} == {2}


# ----- Серии -----


def test_series_full_cycle(controller, signals):
    """Сценарий: сгенерировать, сохранить, открыть, заменить вопрос, удалить."""
    template, series_id = _make_series(controller, count=3)

    series = controller.get_series()[0]
    assert series.id == series_id
    assert series.template_name == template.template_name
    assert series.variants_count == 3
    assert series.seed == 42

    variants = controller.get_variants(series_id)
    assert [v.variant_no for v in variants] == [1, 2, 3]
    assert all(len(v.questions) == 4 for v in variants)

    variant = variants[0]
    old = variant.questions[0]
    candidates = controller.replacement_candidates(variant, old)
    assert len(candidates) == 7  # 8 вопросов той же темы и сложности минус текущий
    assert all(c.id not in {q.id for q in variant.questions} for c in candidates)

    new = candidates[0]
    controller.replace_question(variant.id, old.id, new.id)
    updated = controller.get_variants(series_id)[0]
    assert updated.questions[0].id == new.id  # позиция вопроса не изменилась

    controller.delete_series(series_id)
    assert controller.get_series() == []
    assert signals.count("series") == 3


def test_series_no_overlap_saved(controller):
    """Серия «без пересечений» сохраняется, вопросы не повторяются."""
    _, series_id = _make_series(controller, count=4, no_overlap=True)
    assert controller.get_series()[0].no_overlap is True
    ids = [q.id for v in controller.get_variants(series_id) for q in v.questions]
    assert len(ids) == len(set(ids)) == 16


def test_template_with_series_is_protected(controller):
    """Шаблон, по которому есть серия, контроллер не удаляет."""
    template, _ = _make_series(controller, count=1)
    with pytest.raises(TicketGenError):
        controller.delete_template(template.id)
    assert controller.get_template(template.id) is not None


# ----- Служебное -----


def test_stats(controller):
    """Строка состояния показывает число вопросов и шаблонов."""
    question = controller.find_questions()[0]
    controller.toggle_question(question)
    text = controller.stats()
    assert "Вопросов: 96 (активных 95)" in text
    assert "Шаблонов: 1" in text


def test_backup_skipped_for_memory_db(controller):
    """Для базы в памяти резервная копия не создаётся."""
    assert controller.backup() is None


def test_backup_of_file_db(tmp_path, monkeypatch):
    """Для файловой базы создаётся копия, хранятся только последние."""
    config = AppConfig()
    monkeypatch.setattr(config, "backup_dir", tmp_path / "backup")
    monkeypatch.setattr(config, "backups_to_keep", 2)
    db = Database(tmp_path / "tickets.db")
    try:
        controller = AppController(db)
        old = config.backup_dir
        old.mkdir()
        for stamp in ("20200101_000000", "20200102_000000"):
            (old / f"tickets_{stamp}.db").write_bytes(b"")
        copy_path = controller.backup()
        assert copy_path.exists()
        assert copy_path.stat().st_size > 0
        copies = sorted(p.name for p in old.glob("tickets_*.db"))
        assert len(copies) == 2
        assert copy_path.name in copies
    finally:
        db.close()
