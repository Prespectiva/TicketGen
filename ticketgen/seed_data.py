"""Наполнение базы тестовыми данными.

Запуск: ``poetry run python -m ticketgen.seed_data``.
Создаёт 4 темы, 96 вопросов и шаблон «Экзамен ОАиП, 2 курс».
"""

from ticketgen.data.database import Database
from ticketgen.data.repositories import (
    QuestionRepository,
    TemplateRepository,
    TopicRepository,
)
from ticketgen.domain.models import Question, TemplateRule

DISCIPLINE = "ОАиП"

TOPICS = {
    "Циклы": [
        "цикл for",
        "цикл while",
        "операторы break и continue",
        "вложенные циклы",
        "функция range()",
        "бесконечный цикл",
        "цикл с else",
        "счётчик цикла",
    ],
    "Функции": [
        "функция def",
        "аргументы по умолчанию",
        "оператор return",
        "рекурсия",
        "lambda-функция",
        "область видимости",
        "*args и **kwargs",
        "docstring",
    ],
    "Списки": [
        "список list",
        "срезы списка",
        "метод append()",
        "генератор списка",
        "сортировка списка",
        "вложенные списки",
        "функция len()",
        "кортеж tuple",
    ],
    "Строки": [
        "строка str",
        "f-строки",
        "метод split()",
        "метод join()",
        "индексация строк",
        "метод replace()",
        "кодировка UTF-8",
        "метод strip()",
    ],
}

PATTERNS = {
    1: ("теория", "Что такое {c}? Приведите пример.", "Определение и пример: {c}."),
    2: ("практика", "Напишите программу, в которой используется {c}.", "Пример: {c}."),
    3: (
        "практика",
        "Объясните, когда применять {c}, и найдите ошибку в коде преподавателя.",
        "Разбор применения: {c}.",
    ),
}


def fill_database(db: Database) -> int:
    """Заполняет пустую базу тестовыми данными.

    Returns:
        Количество добавленных вопросов (0, если в базе уже есть вопросы).
    """
    topic_repo = TopicRepository(db)
    question_repo = QuestionRepository(db)
    template_repo = TemplateRepository(db)
    if question_repo.count() > 0:
        return 0

    questions = []
    topic_ids = {}
    for topic_name, concepts in TOPICS.items():
        topic_id = topic_repo.get_or_create(DISCIPLINE, topic_name)
        topic_ids[topic_name] = topic_id
        for difficulty_id, (q_type, question, answer) in PATTERNS.items():
            for concept in concepts:
                questions.append(
                    Question(
                        id=None,
                        topic_id=topic_id,
                        difficulty_id=difficulty_id,
                        q_type=q_type,
                        question_text=question.format(c=concept),
                        answer_text=answer.format(c=concept),
                    )
                )
    question_repo.add_many(questions)

    template_id = template_repo.add(
        "Экзамен ОАиП, 2 курс",
        "Экзаменационный билет № {N} по дисциплине «ОАиП»",
    )
    for topic_name, difficulty_id in [
        ("Циклы", 1),
        ("Функции", 2),
        ("Списки", 2),
        ("Строки", 3),
    ]:
        template_repo.add_rule(
            TemplateRule(None, template_id, topic_ids[topic_name], difficulty_id, 1)
        )
    return len(questions)


if __name__ == "__main__":
    added = fill_database(Database.instance())
    print(f"Добавлено вопросов: {added}")