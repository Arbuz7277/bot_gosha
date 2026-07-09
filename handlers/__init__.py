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
from handlers.test import setup as test_setup
from handlers.casino import setup as casino_setup
from handlers.mine_history import setup as mine_history_setup
from handlers.farm import setup as farm_setup

def setup_handlers(bot):
    """Инициализация всех обработчиков в функции"""
    bot = commands_setup(bot)

    bot = test_setup(bot)
    bot = casino_setup(bot)
    bot = mine_history_setup(bot)
    bot = farm_setup(bot)


    return bot
