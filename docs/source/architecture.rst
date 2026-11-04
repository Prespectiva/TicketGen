Архитектура
===========

Слои приложения
---------------

Приложение многослойное и построено по паттерну MVC. Каждый слой лежит
в своём пакете и обращается только к слоям ниже себя:

.. code-block:: text

   ┌──────────────────────────────────────────────────────────┐
   │  views        окна, вкладки, диалоги (PyQt6)       View  │
   ├──────────────────────────────────────────────────────────┤
   │  controllers  AppController: действия пользователя       │
   │               и сигналы об изменениях        Controller  │
   ├───────────────────────────┬──────────────────────────────┤
   │  logic                    │  workers                     │
   │  генератор, баллы,        │  BackgroundWorker:           │
   │  импорт CSV, экспорт,     │  долгие операции в фоне      │
   │  Moodle                   │                              │
   ├───────────────────────────┴──────────────────────────────┤
   │  data         Database, репозитории (весь SQL)    Model  │
   ├──────────────────────────────────────────────────────────┤
   │  domain       сущности (dataclass) и ошибки              │
   └──────────────────────────────────────────────────────────┘
                     SQLite: tickets.db

.. list-table::
   :header-rows: 1
   :widths: 22 78

   * - Пакет
     - Ответственность
   * - ``ticketgen.domain``
     - классы-данные ``Topic``, ``Difficulty``, ``Question``,
       ``Template``, ``TemplateRule``, ``Series``, ``Variant`` и ошибки
       ``TicketGenError``, ``NotEnoughQuestionsError``. Не зависит ни от
       чего, кроме стандартной библиотеки.
   * - ``ticketgen.data``
     - подключение к SQLite, создание схемы, резервное копирование
       (``Database``) и репозитории с операциями CRUD. Только здесь
       есть SQL.
   * - ``ticketgen.logic``
     - алгоритмы без интерфейса: генерация серии, подсчёт баллов
       и проверка банка, импорт CSV, экспорт в DOCX и PDF, выгрузка
       в Moodle. Работает с сущностями и репозиториями.
   * - ``ticketgen.workers``
     - ``BackgroundWorker`` — запуск функции в отдельном потоке ``QThread``.
   * - ``ticketgen.controllers``
     - ``AppController`` — единая точка входа для окон. Создаёт
       репозитории, вызывает логику и сообщает об изменениях сигналами.
   * - ``ticketgen.views``
     - главное окно, четыре вкладки, диалоги, стили и анимированные
       виджеты. Не содержит SQL и расчётов.

Главное правило зависимостей: окна знают только контроллер, контроллер
знает репозитории и логику, логика не знает об окнах. Поэтому всё,
кроме окон, проверяется автоматическими тестами без запуска интерфейса.

Паттерны проектирования
-----------------------

.. list-table::
   :header-rows: 1
   :widths: 18 32 50

   * - Паттерн
     - Где
     - Зачем
   * - MVC
     - ``views`` — ``controllers`` — ``data``/``logic``
     - окна отделены от данных и алгоритмов, логику можно тестировать
       без интерфейса и менять интерфейс, не трогая логику
   * - Singleton
     - :class:`~ticketgen.config.AppConfig`,
       :meth:`Database.instance() <ticketgen.data.database.Database.instance>`
     - одни настройки путей и одно подключение к базе на всю программу.
       В тестах ``Database(":memory:")`` создаётся напрямую, поэтому
       у каждого теста своя база
   * - Repository
     - :mod:`ticketgen.data.repositories`
     - SQL собран в одном месте, запросы параметризованы (защита от
       SQL-инъекций), ошибки SQLite переводятся в понятный текст
   * - Factory
     - :class:`~ticketgen.logic.exporters.ExporterFactory`
     - экспортёр выбирается по названию формата. Новый формат
       добавляется одним классом-наследником ``BaseExporter``
   * - Observer
     - сигналы ``questions_changed``, ``templates_changed``,
       ``series_changed`` контроллера
     - вкладки сами обновляются после любого изменения данных
       и не знают друг о друге

Сценарий «сгенерировать серию»
------------------------------

Последовательность вызовов показывает, как слои работают вместе:

1. ``GenerationTab`` при смене параметров вызывает
   ``AppController.check_template()``. Тот берёт из
   ``QuestionRepository.count_by_topic_and_difficulty()`` число вопросов
   и передаёт его в :func:`ticketgen.logic.scoring.check_rules` и
   :func:`~ticketgen.logic.scoring.possible_tickets`. Вкладка показывает
   результат проверки.
2. По кнопке «Сгенерировать» вкладка получает от контроллера активные
   вопросы (``active_pool()``) и запускает
   :func:`ticketgen.logic.generator.generate_variants` в
   ``BackgroundWorker``. Процент выполнения приходит сигналом
   ``progress``.
3. По сигналу ``finished_ok`` вкладка вызывает
   ``AppController.save_series()``. ``SeriesRepository.save()`` записывает
   серию, билеты и их вопросы одной транзакцией.
4. Контроллер отправляет ``series_changed``: вкладка «Результаты»
   перечитывает историю, строка состояния обновляется.

База данных
-----------

База SQLite из восьми таблиц создаётся при первом запуске
(константа ``SCHEMA`` модуля :mod:`ticketgen.data.database`). Внешние ключи включены
(``PRAGMA foreign_keys = ON``), правила шаблона и состав билетов
удаляются каскадно вместе с шаблоном и серией.

.. list-table::
   :header-rows: 1
   :widths: 27 73

   * - Таблица
     - Содержимое
   * - ``tbl_topics``
     - темы: предмет (``discipline``) и название, пара уникальна
   * - ``tbl_difficulty``
     - уровни сложности и вес в баллах: лёгкий 1, средний 2, сложный 3
   * - ``tbl_questions``
     - вопросы: тема, сложность, тип, текст, ответ, признак активности
   * - ``tbl_templates``
     - шаблоны: название, заголовок и оформление (предмет, вид
       документа, эмблема, подписи)
   * - ``tbl_template_rules``
     - правила шаблона: тема, сложность, число вопросов
   * - ``tbl_series``
     - серии: шаблон, дата, seed, режим без пересечений, число билетов
   * - ``tbl_variants``
     - билеты серии: номер и суммарный балл
   * - ``tbl_variant_questions``
     - вопросы билета и их порядок

Для быстрого отбора вопросов по правилам есть индекс
``(topic_id, difficulty_id)``. Поиск без учёта регистра идёт через
функцию ``py_lower``, зарегистрированную в подключении: встроенная
функция ``LOWER()`` SQLite не обрабатывает кириллицу.

Внутренний API
--------------

Окна обращаются к данным только через методы
:class:`~ticketgen.controllers.app_controller.AppController`. Это и есть
внутренний API приложения:

.. list-table::
   :header-rows: 1
   :widths: 25 75

   * - Группа
     - Методы
   * - Темы
     - ``get_topics``, ``get_disciplines``, ``add_topic``,
       ``rename_topic``, ``delete_topic``
   * - Банк вопросов
     - ``get_difficulties``, ``find_questions``, ``save_question``,
       ``toggle_question``, ``delete_question``, ``import_csv``,
       ``write_csv_template``, ``available_counts``
   * - Шаблоны
     - ``get_templates``, ``get_template``, ``create_template``,
       ``update_template``, ``delete_template``, ``add_rule``,
       ``update_rule_count``, ``update_rule_target``, ``delete_rule``,
       ``check_template``, ``store_logo``, ``last_logo``
   * - Серии
     - ``active_pool``, ``save_series``, ``get_series``, ``get_variants``,
       ``replacement_candidates``, ``replace_question``,
       ``delete_series``, ``export_moodle``
   * - Служебные
     - ``stats``, ``backup``

Ошибки, которые нужно показать пользователю, передаются исключением
:class:`~ticketgen.domain.models.TicketGenError`. Окно ловит его и
выводит текст в сообщении, а не закрывается с ошибкой.

Потоки
------

Генерация и экспорт могут занимать заметное время, поэтому выполняются
в :class:`~ticketgen.workers.background_worker.BackgroundWorker`. Поток
не трогает виджеты: в Qt это можно делать только из главного потока.
Результат, процент выполнения и ошибка передаются сигналами
``finished_ok``, ``progress`` и ``failed``. Пока поток работает, ссылка
на него хранится в ``BackgroundWorker._running``: иначе Python может
удалить объект потока раньше, чем Qt его завершит.

Структура проекта
-----------------

.. code-block:: text

   TicketGen/
   ├── main.py                  точка входа
   ├── pyproject.toml           зависимости и настройки (Poetry, black, pytest)
   ├── poetry.lock              точные версии зависимостей
   ├── build.bat                сборка TicketGen.exe (PyInstaller)
   ├── README.md
   ├── ticketgen/
   │   ├── config.py            AppConfig: пути к базе, backup, export
   │   ├── seed_data.py         демонстрационные данные
   │   ├── domain/models.py     сущности и ошибки
   │   ├── data/                database.py, repositories.py
   │   ├── logic/               generator, scoring, csv_importer,
   │   │                        exporters, moodle
   │   ├── workers/             background_worker.py
   │   ├── controllers/         app_controller.py
   │   └── views/               окна, вкладки, диалоги, стили, иконки
   ├── tests/                   тесты pytest
   ├── scripts/system_check.py  системная проверка требований ТЗ
   ├── examples/                пример CSV с вопросами
   └── docs/                    эта документация (Sphinx)
