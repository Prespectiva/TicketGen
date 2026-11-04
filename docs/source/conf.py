"""Настройки Sphinx для документации TicketGen.

Сборка HTML из корня проекта::

    poetry run sphinx-build -b html docs/source docs/build/html
"""

import sys
from pathlib import Path

# Корень проекта в sys.path, чтобы autodoc импортировал пакет ticketgen.
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

project = "TicketGen"
author = "Репенко Я. А."
copyright = "2026, Репенко Я. А., группа ИСП-341, ГБПОУ НСО «НЭМК»"
version = "1.0"
release = "1.0.0"
language = "ru"

extensions = [
    "sphinx.ext.autodoc",  # документация из docstrings
    "sphinx.ext.napoleon",  # разделы Args/Returns/Raises в docstrings
    "sphinx.ext.viewcode",  # ссылка «[исходный код]» у каждого объекта
]

# Для сборки документации не нужны окна и библиотеки экспорта: autodoc
# подставляет вместо них заглушки. Так документацию можно собрать, даже
# если PyQt6, python-docx и reportlab не установлены.
autodoc_mock_imports = ["PyQt6", "docx", "reportlab"]
autodoc_default_options = {
    "members": True,
    "show-inheritance": True,
    "member-order": "bysource",
}
autodoc_typehints = "description"
autoclass_content = "both"
napoleon_google_docstring = True
napoleon_numpy_docstring = False

templates_path = ["_templates"]
exclude_patterns = []

try:
    import sphinx_rtd_theme  # noqa: F401

    html_theme = "sphinx_rtd_theme"
    html_theme_options = {"navigation_depth": 3, "collapse_navigation": False}
except ImportError:  # тема не установлена — встроенная тема Sphinx
    html_theme = "alabaster"

html_title = "TicketGen 1.0 — документация"
html_short_title = "TicketGen"
html_static_path = ["_static"]
html_css_files = ["custom.css"]
html_logo = "_static/app_icon.png"
html_favicon = "_static/app_icon.ico"
html_show_sourcelink = False
html_last_updated_fmt = "%d.%m.%Y"
