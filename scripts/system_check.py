"""Системное тестирование TicketGen: проверка показателей и требований ТЗ.

Запуск из корня проекта::

    py -m poetry run python scripts/system_check.py

Скрипт работает на временной базе в памяти и во временной папке, рабочий
файл tickets.db не затрагивает. В конце печатает таблицу «требование ->
результат» в формате Markdown, которую можно перенести в отчёт.
"""

import ctypes
import sys
import tempfile
import time
from ctypes import wintypes
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ticketgen.data.database import Database  # noqa: E402
from ticketgen.data.repositories import (  # noqa: E402
    DifficultyRepository,
    QuestionRepository,
    SeriesRepository,
    TemplateRepository,
    TopicRepository,
)
from ticketgen.domain.models import (  # noqa: E402
    NotEnoughQuestionsError,
    Question,
    Series,
    TemplateRule,
)
from ticketgen.logic.csv_importer import import_questions  # noqa: E402
from ticketgen.logic.exporters import export_series  # noqa: E402
from ticketgen.logic.generator import generate_variants  # noqa: E402

LEVELS = ["лёгкий", "средний", "сложный"]
RESULTS = []  # строки итоговой таблицы: (требование, ожидание, факт, статус)


def peak_memory_mb() -> float:
    """Пиковый объём памяти процесса в мегабайтах (Windows и Linux)."""
    if sys.platform == "win32":

        class Counters(ctypes.Structure):
            _fields_ = [
                ("cb", wintypes.DWORD),
                ("PageFaultCount", wintypes.DWORD),
                ("PeakWorkingSetSize", ctypes.c_size_t),
                ("WorkingSetSize", ctypes.c_size_t),
                ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                ("PagefileUsage", ctypes.c_size_t),
                ("PeakPagefileUsage", ctypes.c_size_t),
            ]

        counters = Counters()
        counters.cb = ctypes.sizeof(Counters)
        kernel32 = ctypes.windll.kernel32
        kernel32.GetCurrentProcess.restype = wintypes.HANDLE
        psapi = ctypes.windll.psapi
        psapi.GetProcessMemoryInfo.argtypes = [
            wintypes.HANDLE,
            ctypes.POINTER(Counters),
            wintypes.DWORD,
        ]
        psapi.GetProcessMemoryInfo(
            kernel32.GetCurrentProcess(), ctypes.byref(counters), counters.cb
        )
        return counters.PeakWorkingSetSize / 1024 / 1024
    import resource

    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024


def check(requirement, expected, func):
    """Выполняет проверку func() -> (факт, ok) и записывает результат."""
    try:
        actual, ok = func()
    except Exception as error:  # проверка сама не должна ронять скрипт
        actual, ok = f"ошибка: {error}", False
    RESULTS.append((requirement, expected, actual, "Пройдено" if ok else "ПРОВАЛ"))
    print(f"[{'OK' if ok else 'FAIL'}] {requirement}: {actual}")


def timed(func):
    """Возвращает (результат, секунды)."""
    start = time.perf_counter()
    result = func()
    return result, time.perf_counter() - start


def build_bank(db, topics=10, per_group=34):
    """Банк на ~1000 вопросов: 10 тем x 3 сложности x 34 вопроса."""
    topic_repo, question_repo = TopicRepository(db), QuestionRepository(db)
    topic_ids = [topic_repo.add("ОАиП", f"Тема {n}") for n in range(1, topics + 1)]
    question_repo.add_many(
        [
            Question(None, topic_id, difficulty, "теория", f"Вопрос {t}-{d}-{i}", "О")
            for t, topic_id in enumerate(topic_ids, 1)
            for d in (1, 2, 3)
            for difficulty in (d,)
            for i in range(per_group)
        ]
    )
    return topic_ids


def rules_for(topic_ids, count_rules=10):
    """Десять правил по одному вопросу: билет из 10 вопросов."""
    return [
        TemplateRule(
            None,
            0,
            topic_ids[i],
            (i % 3) + 1,
            1,
            topic_name=f"Тема {i + 1}",
            level_name=LEVELS[i % 3],
            weight=(i % 3) + 1,
        )
        for i in range(count_rules)
    ]


def main():
    """Запускает все проверки и печатает итоговую таблицу."""
    db = Database(":memory:")
    topic_ids = build_bank(db)
    question_repo = QuestionRepository(db)
    pool = question_repo.find(only_active=True)
    rules = rules_for(topic_ids)
    print(f"Банк: {len(pool)} вопросов, правил в шаблоне: {len(rules)}\n")

    # ---------- 4.1.3 Показатели назначения ----------
    def generation_time():
        variants, seconds = timed(lambda: generate_variants(rules, pool, 30, seed=1))
        ok = seconds <= 3 and len(variants) == 30
        return f"{seconds * 1000:.0f} мс", ok

    check(
        "4.1.3 Генерация 30 билетов по 10 вопросов из 1000",
        "не более 3 с",
        generation_time,
    )

    def big_bank():
        big = Database(":memory:")
        build_bank(big, topics=10, per_group=334)  # 10 020 вопросов
        repo = QuestionRepository(big)
        found, seconds = timed(lambda: repo.find(text="вопрос 5-2"))
        everything, seconds_all = timed(lambda: repo.find())
        big.close()
        ok = len(everything) >= 10_000 and seconds < 0.5 and seconds_all < 1.5
        return (
            f"{len(everything)} записей: полный список {seconds_all * 1000:.0f} мс, "
            f"поиск {seconds * 1000:.0f} мс ({len(found)} найдено)",
            ok,
        )

    check("4.1.3 Банк до 10 000 записей", "без заметного замедления", big_bank)

    variants30 = generate_variants(rules, pool, 30, seed=1)

    def docx_time():
        with tempfile.TemporaryDirectory() as folder:
            _, seconds = timed(
                lambda: export_series(
                    Path(folder), "серия", "Экзамен", variants30, ["docx"]
                )
            )
        return f"{seconds * 1000:.0f} мс", seconds <= 10

    check("4.1.3 Экспорт 30 билетов в DOCX", "не более 10 с", docx_time)

    # ---------- 4.3.1 / 4.2.1 Генерация ----------
    def no_repeat_in_ticket():
        bad = [
            v.variant_no
            for v in variants30
            if len({q.id for q in v.questions}) != len(v.questions)
        ]
        return ("повторов нет" if not bad else f"повторы в билетах {bad}"), not bad

    check(
        "4.2.1 Вопросы не повторяются внутри билета",
        "0 повторов",
        no_repeat_in_ticket,
    )

    def unique_tickets():
        sets = {frozenset(q.id for q in v.questions) for v in variants30}
        return f"{len(sets)} разных из {len(variants30)}", len(sets) == len(variants30)

    check(
        "4.2.1 Одинаковые по составу билеты не допускаются", "30 из 30", unique_tickets
    )

    def equal_scores():
        scores = {v.total_score for v in variants30}
        return f"баллы билетов: {sorted(scores)}", len(scores) == 1

    check("6.1 Суммарный балл билетов одинаков", "один балл у всех", equal_scores)

    def same_seed():
        again = generate_variants(rules, pool, 30, seed=1)
        other = generate_variants(rules, pool, 30, seed=2)
        same = [[q.id for q in v.questions] for v in variants30] == [
            [q.id for q in v.questions] for v in again
        ]
        differ = [[q.id for q in v.questions] for v in variants30] != [
            [q.id for q in v.questions] for v in other
        ]
        return (
            f"seed 1 повторяется: {same}; seed 2 отличается: {differ}",
            same and differ,
        )

    check(
        "4.2.1 Воспроизводимость по seed", "тот же seed -> тот же результат", same_seed
    )

    def no_overlap():
        few = generate_variants(rules, pool, 20, seed=5, no_overlap=True)
        ids = [q.id for v in few for q in v.questions]
        return f"{len(ids)} вопросов, уникальных {len(set(ids))}", len(ids) == len(
            set(ids)
        )

    check("4.2.1 Режим «без пересечений»", "вопрос только один раз", no_overlap)

    def not_enough():
        try:
            generate_variants(rules, pool, 40, seed=1, no_overlap=True)
        except NotEnoughQuestionsError as error:
            return f"отказ с сообщением: «{error}»", "нужно" in str(error)
        return "генерация запустилась без проверки", False

    check(
        "4.1.4 Нехватка вопросов: генерация не запускается",
        "сообщение, каких вопросов не хватает",
        not_enough,
    )

    # ---------- 4.1.4 / 4.1.5 Надёжность и безопасность ----------
    def bad_csv():
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "bad.csv"
            path.write_bytes(b"\xff\xfe\x00garbage\x00\x01")
            try:
                result = import_questions(
                    path,
                    TopicRepository(db),
                    question_repo,
                    DifficultyRepository(db),
                )
            except Exception as error:  # TicketGenError с текстом для пользователя
                return f"понятное сообщение: «{error}»", type(error).__name__ == (
                    "TicketGenError"
                )
            return f"импортировано {result.imported}", False

    check(
        "4.1.4 Повреждённый файл импорта",
        "программа не падает, есть сообщение",
        bad_csv,
    )

    def csv_100():
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "q100.csv"
            lines = ["дисциплина;тема;сложность;тип;вопрос;ответ"]
            lines += [
                f"ОАиП;Импорт;средний;теория;Импортированный вопрос {i};Ответ"
                for i in range(100)
            ]
            lines.append("ОАиП;Импорт;очень;теория;Строка с ошибкой;")
            path.write_text("\n".join(lines), encoding="utf-8")
            result = import_questions(
                path, TopicRepository(db), question_repo, DifficultyRepository(db)
            )
        return (
            f"добавлено {result.imported}, пропущено строк с ошибкой: "
            f"{len(result.errors)}",
            result.imported == 100 and len(result.errors) == 1,
        )

    check("6.1 Импорт CSV со 100 вопросами", "100 добавлено, ошибки в отчёте", csv_100)

    def injection():
        before = question_repo.count()
        question_repo.find(text="'; DROP TABLE tbl_questions; --")
        question_repo.find(text="' OR 1=1 --")
        return f"вопросов до: {before}, после: {question_repo.count()}", (
            question_repo.count() == before
        )

    check("4.1.5 Защита от SQL-инъекций", "данные не изменились", injection)

    def transaction_rollback():
        template_repo = TemplateRepository(db)
        series_repo = SeriesRepository(db)
        template_id = template_repo.add("Откат", "Билет")
        before = series_repo.count()
        broken = generate_variants(rules, pool, 2, seed=9)
        broken[1].questions[0].id = -1  # несуществующий вопрос
        try:
            series_repo.save(
                Series(None, template_id, "2026-11-02 12:00", 9, False, 2), broken
            )
        except Exception:
            pass
        return f"серий до: {before}, после: {series_repo.count()}", (
            series_repo.count() == before
        )

    check(
        "4.1.4 Транзакции: ошибка не оставляет частичных данных",
        "серия не сохранена",
        transaction_rollback,
    )

    def backup():
        with tempfile.TemporaryDirectory() as folder:
            path = db.backup(Path(folder), keep=5)
            return f"{path.name}, {path.stat().st_size // 1024} КБ", path.exists()

    check("4.1.4 Резервная копия базы", "файл создан", backup)

    # ---------- 4.2.1 Экспорт ----------
    def export_all():
        with tempfile.TemporaryDirectory() as folder:
            files = export_series(
                Path(folder), "серия", "Экзамен", variants30, ["docx", "pdf"]
            )
            names = sorted(p.name for p in files)
            sizes_ok = all(p.stat().st_size > 0 for p in files)
        return f"{len(files)} файла: {', '.join(names)}", len(files) == 4 and sizes_ok

    check(
        "4.2.1 Экспорт DOCX, PDF, ответов и ведомости",
        "4 непустых файла",
        export_all,
    )

    # ---------- Память ----------
    peak = peak_memory_mb()
    RESULTS.append(
        (
            "Расход памяти",
            "оценка (норматива в ТЗ нет)",
            f"пик {peak:.0f} МБ при банке 10 000 вопросов, генерации и экспорте",
            "Измерено",
        )
    )
    print(f"\nПиковая память процесса: {peak:.0f} МБ")

    print("\n| Требование | Ожидание | Результат | Статус |")
    print("|---|---|---|---|")
    for requirement, expected, actual, status in RESULTS:
        print(f"| {requirement} | {expected} | {actual} | {status} |")

    failed = [row for row in RESULTS if row[3] == "ПРОВАЛ"]
    db.close()
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
