# TicketGen — генератор вариантов экзаменационных билетов

Десктопное приложение для преподавателей: банк вопросов по темам и сложности,
шаблоны билетов, генерация серий с одинаковым баллом, экспорт в DOCX и PDF.
Учебная практика УП.01, Репенко Я. А., ИСП-341.

## Стек

- Python 3.10+, PyQt6 (интерфейс), SQLite (база tickets.db)
- python-docx и reportlab (экспорт), Poetry (зависимости)
- pytest (тесты), black и flake8 (качество кода)

## Архитектура

Многослойная, паттерн MVC:
- `ticketgen/views` — окна и вкладки (View)
- `ticketgen/controllers` — AppController (Controller, сигналы = Observer)
- `ticketgen/logic` — генератор, подсчёт баллов, импорт CSV, экспорт (Factory)
- `ticketgen/data` — Database (Singleton) и репозитории (Repository)
- `ticketgen/domain` — сущности (dataclass)

## Установка и запуск

    pip install poetry
    poetry install
    poetry run python -m ticketgen.seed_data   # тестовые данные (необязательно)
    poetry run python main.py

## Тесты и проверка кода

    poetry run pytest
    poetry run black --check .
    poetry run flake8

## Импорт вопросов

Пример файла: `examples/questions_example.csv`
(столбцы: дисциплина;тема;сложность;тип;вопрос;ответ).

## Ссылки

- Макет в Figma: <https://www.figma.com/design/vfRLcnWpsTCRWL5SOfZpsi/TicketGen?node-id=3-2&t=4H77UXpki29i7iEi-1>
