# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Arbuz.
# config.py


VERSION = "1.11.0"


OWNER = (8400317551,)


REFERAL_FILE = 'dp/referal.json'
USERS_DATA = 'dp/users.json'
FILE_CHATID = 'dp/chat_id.json'
BANK = 'dp/bank.json'
SHOP_ITEMS = 'dp/shop_items.json'
DICE_PATH = 'dp/dice.json'
OTHER_DATA = 'dp/other_data.json'
ROULETTE_DATA = 'dp/roulette.json'
TRANSFER_DATA = 'dp/transfers.json'
MINE_DATA = 'dp/mine_data.json'
MINE_HISTORY = 'dp/mine_history.json'


FARM_TIME = 60 * 60 * 2    # seconds
MULTI_FARM = 4
FARM_RANGE = (200, 1000)
MAX_BALANCE_FARM = 1000

QUOTES_PER_PAGE = 6

KD_ROULETTE = 30       # seconds
KD_NUMBER = 1.5        # seconds
KD_FEEDBACK = 600      # seconds

COMMISION_PAY = 5      # procent
CASINO_COMISSION = 0   # procent
COMMISION_DICE = 5     # procent
COMMISION_MORELESS = 1

MORELESS_RTP = 90      # procent
MAX_BID = 200          # coins

MIN_AMOUNT_PAY = 1

MAX_BET_CASINO = 1000
MIN_BET_CASINO = 0.1
MAX_MULTI_CASINO = 100
MIN_MULTI_CASINO = 1.1
RTP_CASINO = 0.95



BALL_VARIABLES = ('Да, ', 'Нет, ', 'Возможно, ', 'Скорее всего, ', 'Не уверен, ', 'Маловероятно, ')
MESSAGE_GOSHA = ('Я тут!', 'Всегда здесь!', 'Слушаю!', 'Привет!', 'На месте!')


ROULETTE_NUMBERS = [
    {"number": 0,  "color": "green"},
    {"number": 32, "color": "red"},
    {"number": 15, "color": "black"},
    {"number": 19, "color": "red"},
    {"number": 4,  "color": "black"},
    {"number": 21, "color": "red"},
    {"number": 2,  "color": "black"},
    {"number": 25, "color": "red"},
    {"number": 17, "color": "black"},
    {"number": 34, "color": "red"},
    {"number": 6,  "color": "black"},
    {"number": 27, "color": "red"},
    {"number": 13, "color": "black"},
    {"number": 36, "color": "red"},
    {"number": 11, "color": "black"},
    {"number": 30, "color": "red"},
    {"number": 8,  "color": "black"},
    {"number": 23, "color": "red"},
    {"number": 10, "color": "black"},
    {"number": 5,  "color": "red"},
    {"number": 24, "color": "black"},
    {"number": 16, "color": "red"},
    {"number": 33, "color": "black"},
    {"number": 1,  "color": "red"},
    {"number": 20, "color": "black"},
    {"number": 14, "color": "red"},
    {"number": 31, "color": "black"},
    {"number": 9,  "color": "red"},
    {"number": 22, "color": "black"},
    {"number": 18, "color": "red"},
    {"number": 29, "color": "black"},
    {"number": 7,  "color": "red"},
    {"number": 28, "color": "black"},
    {"number": 12, "color": "red"},
    {"number": 35, "color": "black"},
    {"number": 3,  "color": "red"},
    {"number": 26, "color": "black"}
]


other_time = {}
user_buttons = {}
time_roulette = {}
other_data = {}
