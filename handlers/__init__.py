# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Arbuz.
# handlers/__init__.py

"""
Импортирует все модули.
Импорт нового модуля нужно писать вручную.
"""

# Инициализация commands
from handlers.commands import setup as commands_setup

# Инициализация модулей
pass


def setup_handlers(bot):
    """Инициализация всех обработчиков в функции"""

    commands_setup(bot)
