Примеры использования
=====================

Типовые сценарии
----------------

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Задача
     - Как сделать
   * - Экзамен: 30 билетов, в каждом теория, задача и практика
     - шаблон из трёх правил (например, «Циклы, лёгкий, 1»,
       «Функции, средний, 1», «Строки, сложный, 1»), генерация 30 билетов,
       экспорт билетов и файла ответов в DOCX
   * - Контрольная работа на два варианта, вопросы не должны повторяться
     - вид документа «Контрольная работа» в оформлении шаблона,
       генерация 2 билетов в режиме «Без пересечений». В файлах будет
       «Вариант № 1» и «Вариант № 2»
   * - Тот же комплект билетов для пересдачи
     - генерация по тому же шаблону с seed первой серии (виден на вкладке
       «Результаты»)
   * - Билеты на бланке колледжа
     - в «Оформлении билета…» выбрать эмблему, включить строку для ФИО
       студента и место для подписи преподавателя
   * - Тест в Moodle по каждому билету
     - «Экспорт в Moodle…» → вся серия → Moodle XML, затем в Moodle
       «Банк вопросов → Импорт»

Логика программы доступна и без интерфейса: все модули слоёв ``data``
и ``logic`` можно вызывать из своего скрипта или из тестов. Примеры ниже
запускаются из корня проекта командой
``py -m poetry run python пример.py`` и работают на временной базе
в памяти, рабочий ``tickets.db`` они не меняют.

Генерация серии
---------------

.. code-block:: python

   from ticketgen.data.database import Database
   from ticketgen.data.repositories import QuestionRepository, TemplateRepository
   from ticketgen.logic.generator import generate_variants, ticket_title
   from ticketgen.logic.scoring import score_formula
   from ticketgen.seed_data import fill_database

   db = Database(":memory:")          # временная база в памяти
   fill_database(db)                  # 4 темы, 96 вопросов, 1 шаблон

   template = TemplateRepository(db).get_all()[0]
   pool = QuestionRepository(db).find(only_active=True)

   print(template.template_name, "—", score_formula(template.rules))
   variants = generate_variants(template.rules, pool, variants_count=3, seed=42)
   for variant in variants:
       print(ticket_title(template.header_text, variant.variant_no))
       for number, question in enumerate(variant.questions, 1):
           print(f"  {number}. {question.question_text}")
       print("  Балл:", variant.total_score)

Результат (начало):

.. code-block:: text

   Экзамен ОАиП, 2 курс — 1×1 + 1×2 + 1×2 + 1×3 = 8
   Экзаменационный билет № 1 по дисциплине «ОАиП»
     1. Что такое цикл while? Приведите пример.
     2. Напишите программу, в которой используется функция def.
     3. Напишите программу, в которой используется сортировка списка.
     4. Объясните, когда применять метод join(), и найдите ошибку в коде преподавателя.
     Балл: 8

С тем же ``seed=42`` скрипт всегда печатает те же билеты.

Проверка банка перед генерацией
-------------------------------

.. code-block:: python

   from ticketgen.domain.models import NotEnoughQuestionsError
   from ticketgen.logic.scoring import check_rules, possible_tickets

   questions = QuestionRepository(db)
   available = questions.count_by_topic_and_difficulty()
   checks = check_rules(template.rules, available, variants_count=30, no_overlap=True)
   for check in checks:
       status = "хватает" if check.ok else f"не хватает {check.missing}"
       print(f"{check.rule.topic_name}, {check.rule.level_name}: "
             f"{check.available} из {check.required} — {status}")
   print("Разных билетов:", possible_tickets(template.rules, available))

   try:
       generate_variants(template.rules, questions.find(only_active=True),
                         30, seed=1, no_overlap=True)
   except NotEnoughQuestionsError as error:
       print("Ошибка:", error)

.. code-block:: text

   Циклы, лёгкий: 8 из 30 — не хватает 22
   Функции, средний: 8 из 30 — не хватает 22
   Списки, средний: 8 из 30 — не хватает 22
   Строки, сложный: 8 из 30 — не хватает 22
   Разных билетов: 4096
   Ошибка: Тема «Циклы», сложность «лёгкий»: нужно 30, в банке 8.

В обычном режиме из этого банка можно составить 4096 разных билетов,
а для 30 билетов без пересечений нужно по 30 вопросов на каждое правило.

Импорт вопросов из CSV
----------------------

.. code-block:: python

   from ticketgen.data.repositories import (
       DifficultyRepository, QuestionRepository, TopicRepository,
   )
   from ticketgen.logic.csv_importer import import_questions

   db = Database(":memory:")
   result = import_questions(
       "examples/questions_example.csv",
       TopicRepository(db), QuestionRepository(db), DifficultyRepository(db),
   )
   print("Загружено:", result.imported)
   for line_no, reason in result.errors:
       print(f"Строка {line_no}: {reason}")

.. code-block:: text

   Загружено: 7
   Строка 9: неизвестная сложность «очень сложный»
   Строка 10: пустой текст вопроса

Темы, которых ещё нет в базе, создаются при импорте автоматически.

Экспорт в DOCX, PDF и Moodle
----------------------------

.. code-block:: python

   from pathlib import Path
   from ticketgen.logic import moodle
   from ticketgen.logic.exporters import export_series

   variants = generate_variants(template.rules, pool, 4, seed=7)
   files = export_series(
       Path("export"), "серия_1", template.header_text, variants,
       formats=["docx", "pdf"], template=template,
   )
   print([file.name for file in files])
   moodle.save_tickets(Path("export/серия_1.xml"), "Экзамен ОАиП",
                       variants, "Билет", "xml")

.. code-block:: text

   ['серия_1_билеты.docx', 'серия_1_билеты.pdf', 'серия_1_ответы.docx',
    'серия_1_ведомость.docx']

Билеты сохраняются в каждом выбранном формате, а файл ответов
и ведомость — в первом. В файле Moodle XML каждый билет становится
категорией ``Экзамен ОАиП/Билет № N`` с вопросами типа «Эссе».
