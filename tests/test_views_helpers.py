"""Тесты вспомогательных функций интерфейса (без окон)."""

import pytest

from ticketgen.views.common import plural
from ticketgen.views.question_tab import page_numbers

FORMS = ("билет", "билета", "билетов")


@pytest.mark.parametrize(
    "number, expected",
    [
        (1, "1 билет"),
        (2, "2 билета"),
        (5, "5 билетов"),
        (11, "11 билетов"),
        (21, "21 билет"),
        (112, "112 билетов"),
    ],
)
def test_plural(number, expected):
    assert plural(number, FORMS) == expected


def test_page_numbers_short_and_long():
    assert page_numbers(1, 3) == [1, 2, 3]
    result = page_numbers(5, 20)
    assert result[0] == 1 and result[-1] == 20 and None in result


def test_page_numbers_first_and_last():
    assert page_numbers(1, 17) == [1, 2, 3, None, 17]
    assert page_numbers(17, 17) == [1, None, 15, 16, 17]
    assert page_numbers(8, 17) == [1, None, 7, 8, 9, None, 17]
