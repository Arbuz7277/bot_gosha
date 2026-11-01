"""Static game/economy parameters. Money values are Decimal (2 places)."""
from decimal import Decimal as D

VERSION = "2.0.0"
EMAIL = "gosha.telegrambot@gmail.com"
GITHUB = "https://github.com/Arbuz7277/bot_gosha"

# ---- economy ---------------------------------------------------------------
GENESIS_BANK = D("10000")          # initial bank funding (minted once)
COMMISSION_PAY = D("5")            # % taken from transfers
COMMISSION_DICE = D("5")           # % taken from the dice winner
COMMISSION_MORELESS = D("1")       # % taken from moreless winnings
COMMISSION_GUESS = D("1")          # % taken from guess winnings
COMMISSION_CASINO = D("0")         # % of casino profit that feeds the jackpot
REFERRAL_BONUS = D("20")           # per side

MIN_AMOUNT_PAY = D("1")
MIN_DONATE = D("1")

# ---- farm ------------------------------------------------------------------
FARM_COOLDOWN = 60 * 60 * 2        # seconds
FARM_RANGE_CENTS = (200, 1000)     # [200, 1000) cents -> 2.00 .. 9.99
FARM_MULTI = 4
FARM_MULTI_CHANCE = 0.01
FARM_MAX_BALANCE = D("1000")       # farming is allowed only up to this balance
FARM_MIN_BANK = D("50")

# ---- casino ----------------------------------------------------------------
MAX_BET_CASINO = D("1000")
MIN_BET_CASINO = D("0.1")
MAX_MULTI_CASINO = D("100")
MIN_MULTI_CASINO = D("1.1")
RTP_CASINO = D("0.95")
JACKPOT_MIN = D("200")
JACKPOT_CHANCE = 0.01

# ---- other games -----------------------------------------------------------
MIN_BID = D("0.1")
GUESS_MULTI = D("8")
MORELESS_WIN_CHANCE = 0.45
KD_ROULETTE = 30                   # seconds since the first open bet
KD_NUMBER = 1.5                    # base cooldown of /number (seconds)
NUMBER_MAX = 999
NUMBER_POT_GROWTH = D("1")         # added to the pot from the bank every hour
NUMBER_POT_MAX = D("500")
KD_FEEDBACK = 600
ACTION_TTL = 60 * 60               # lifetime of confirmation buttons (seconds)

# ---- borrow ----------------------------------------------------------------
MIN_AMOUNT_BORROW = D("10")
MAX_AMOUNT_BORROW = D("10000")
MIN_TERM_BORROW = 1                # hours
MAX_TERM_BORROW = 336
MIN_PERCENT_BORROW = 0
MAX_PERCENT_BORROW = 100
BORROW_REQUEST_TTL_HOURS = 24

# ---- mining ----------------------------------------------------------------
MINE_REWARD = D("12.5")
MINE_TARGET_TIME = 60 * 5
MINE_MEDIAN_WINDOW = 5
MINE_MAX_TARGET = (2 ** 16 - 1) << 216

# ---- misc ------------------------------------------------------------------
QUOTES_PER_PAGE = 6
QUOTE_MAX_LEN = 1500
TZ_NAME = "Europe/Moscow"

BALL_VARIABLES = ("Да, ", "Нет, ", "Возможно, ", "Скорее всего, ", "Не уверен, ", "Маловероятно, ")
MESSAGE_GOSHA = ("Я тут!", "Всегда здесь!", "Слушаю!", "Привет!", "На месте!")

# European wheel order; colours follow the standard layout.
_RED = {1, 3, 5, 7, 9, 12, 14, 16, 18, 19, 21, 23, 25, 27, 30, 32, 34, 36}
_WHEEL = (0, 32, 15, 19, 4, 21, 2, 25, 17, 34, 6, 27, 13, 36, 11, 30, 8, 23, 10, 5,
          24, 16, 33, 1, 20, 14, 31, 9, 22, 18, 29, 7, 28, 12, 35, 3, 26)
ROULETTE_NUMBERS = tuple(
    (n, "green" if n == 0 else ("red" if n in _RED else "black")) for n in _WHEEL
)
COLOR_ALIASES = {
    "black": ("black", "черный", "черная", "черное", "чёрное", "чёрный", "чёрная", "ч", "b"),
    "red": ("red", "красный", "красная", "красное", "к", "r"),
    "green": ("green", "зеленый", "зеленая", "зеленое", "зелёный", "зелёная", "зелёное", "з", "g"),
}
ALL_WORDS = frozenset({"all", "все", "всё", "вся", "весь"})
