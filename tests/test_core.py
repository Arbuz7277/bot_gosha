"""Unit tests for the pure logic (no Telegram, no PostgreSQL needed).

Run:  python -m unittest discover -s tests -v
"""
import sys
import types
import unittest
from decimal import Decimal as D
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

try:  # asyncpg is only used for type hints inside ledger.py
    import asyncpg  # noqa: F401
except ImportError:  # pragma: no cover
    sys.modules["asyncpg"] = types.ModuleType("asyncpg")

from app import constants  # noqa: E402
from app.db import ledger, mining  # noqa: E402
from app.utils import calc, money, timeutils  # noqa: E402


class FakeConn:
    """Tiny in-memory stand-in for the few queries ledger.post() issues."""

    def __init__(self):
        self.accounts = {}      # code -> dict(id, code, balance, allow_negative)
        self.transactions = []
        self.entries = []

    def add_account(self, code, balance="0", allow_negative=False):
        self.accounts[code] = {"id": len(self.accounts) + 1, "code": code,
                               "balance": D(balance), "allow_negative": allow_negative}

    def transaction(self):
        conn = self

        class _Tx:
            async def __aenter__(self_inner):
                self_inner.snapshot = ({k: dict(v) for k, v in conn.accounts.items()},
                                       list(conn.transactions), list(conn.entries))

            async def __aexit__(self_inner, exc_type, exc, tb):
                if exc_type:  # rollback
                    conn.accounts, conn.transactions, conn.entries = (
                        self_inner.snapshot[0], self_inner.snapshot[1], self_inner.snapshot[2])
                return False
        return _Tx()

    async def fetch(self, sql, codes):
        rows = [self.accounts[c] for c in codes if c in self.accounts]
        return sorted(rows, key=lambda r: r["id"])

    async def execute(self, sql, *args):
        if sql.startswith("INSERT INTO transactions"):
            self.transactions.append(args)

    async def executemany(self, sql, rows):
        if sql.startswith("INSERT INTO ledger_entries"):
            self.entries.extend(rows)
        elif sql.startswith("UPDATE accounts"):
            by_id = {a["id"]: a for a in self.accounts.values()}
            for account_id, balance in rows:
                by_id[account_id]["balance"] = balance


class LedgerTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.con = FakeConn()
        self.con.add_account("bank", "100")
        self.con.add_account("emission", "-100", allow_negative=True)
        self.con.add_account("user:1", "10")
        self.con.add_account("user:2", "0")

    async def test_balanced_transfer_updates_cache_and_entries_sum_to_zero(self):
        tx = await ledger.post(self.con, "transfer",
                               {"user:1": D("-10"), "user:2": D("9.50"), "bank": D("0.50")})
        self.assertIsNotNone(tx)
        self.assertEqual(self.con.accounts["user:1"]["balance"], D("0"))
        self.assertEqual(self.con.accounts["user:2"]["balance"], D("9.50"))
        self.assertEqual(self.con.accounts["bank"]["balance"], D("100.50"))
        self.assertEqual(sum(e[2] for e in self.con.entries), D("0"))
        self.assertEqual(len(self.con.entries), 3)

    async def test_unbalanced_transaction_is_rejected(self):
        with self.assertRaises(ledger.LedgerError):
            await ledger.post(self.con, "bad", {"user:1": D("-5"), "user:2": D("4")})
        self.assertEqual(self.con.entries, [])

    async def test_insufficient_funds_changes_nothing(self):
        with self.assertRaises(ledger.InsufficientFunds):
            await ledger.post(self.con, "transfer", {"user:1": D("-10.01"), "user:2": D("10.01")})
        self.assertEqual(self.con.accounts["user:1"]["balance"], D("10"))
        self.assertEqual(self.con.entries, [])

    async def test_overdraft_is_explicit(self):
        await ledger.post(self.con, "borrow_repay", {"user:1": D("-25"), "user:2": D("25")},
                          overdraft=("user:1",))
        self.assertEqual(self.con.accounts["user:1"]["balance"], D("-15"))

    async def test_emission_may_go_negative(self):
        await ledger.post(self.con, "mining_reward", {"emission": D("-12.5"), "user:1": D("12.5")})
        self.assertEqual(self.con.accounts["emission"]["balance"], D("-112.5"))

    async def test_more_than_two_decimals_rejected(self):
        with self.assertRaises(ledger.LedgerError):
            await ledger.post(self.con, "x", {"user:1": D("-1.001"), "user:2": D("1.001")})

    async def test_zero_legs_dropped_and_single_leg_rejected(self):
        with self.assertRaises(ledger.LedgerError):
            await ledger.post(self.con, "x", {"user:1": D("0"), "user:2": D("0")})

    async def test_global_sum_stays_zero_after_many_operations(self):
        for i in range(20):
            await ledger.post(self.con, "bet", {"user:1": D("-1"), "bank": D("1")})
            await ledger.post(self.con, "win", {"bank": D("-1"), "user:1": D("1")})
        self.assertEqual(sum(e[2] for e in self.con.entries), D("0"))
        self.assertEqual(sum(a["balance"] for a in self.con.accounts.values()), D("10"))


class MoneyTests(unittest.TestCase):
    def test_parse_amount(self):
        self.assertEqual(money.parse_amount("12,5"), D("12.50"))
        self.assertEqual(money.parse_amount("все", all_value=D("7.456")), D("7.46"))
        for bad in ("-5", "1e5", "inf", "nan", "abc", "", "1.2.3", "9" * 20):
            self.assertIsNone(money.parse_amount(bad), bad)

    def test_coin_form(self):
        expected = {1: "коин", 2: "коина", 5: "коинов", 11: "коинов", 12: "коинов", 14: "коинов",
                    21: "коин", 22: "коина", 111: "коинов", 0: "коинов"}
        for number, word in expected.items():
            self.assertEqual(money.coin_form(number), word, number)
        self.assertEqual(money.coin_form(D("1.5")), "коина")

    def test_fmt(self):
        self.assertEqual(money.fmt(D("12.50")), "12.5")
        self.assertEqual(money.fmt(10), "10")


class CalcTests(unittest.TestCase):
    def test_ok(self):
        self.assertEqual(calc.safe_calc("2^10"), 1024)
        self.assertAlmostEqual(calc.safe_calc("pi*2"), 6.283185307)

    def test_rejected(self):
        for bad in ("9**9**9**9", "__import__('os')", "1/0", "a+1", "2**5000", "", "1" * 300):
            with self.assertRaises(calc.CalcError, msg=bad):
                calc.safe_calc(bad)


class TimeTests(unittest.TestCase):
    def test_parse_duration(self):
        self.assertEqual(timeutils.parse_duration("30m"), 30)
        self.assertEqual(timeutils.parse_duration("2h"), 120)
        self.assertEqual(timeutils.parse_duration("1w"), 7 * 24 * 60)
        for bad in ("", "0m", "abc", "-5m", "999999d"):
            self.assertIsNone(timeutils.parse_duration(bad), bad)


class MiningTests(unittest.TestCase):
    def test_nonce_check_matches_documented_rule(self):
        import hashlib
        seed, nonce = "abc", "42"
        digest = hashlib.sha256((seed + nonce).encode()).hexdigest()
        ok, got = mining.check_nonce(seed, nonce, int(digest, 16) + 1)
        self.assertTrue(ok)
        self.assertEqual(got, digest)
        self.assertFalse(mining.check_nonce(seed, nonce, int(digest, 16))[0])

    def test_retarget_handles_zero_deltas_and_is_bounded(self):
        target = constants.MINE_MAX_TARGET // 8
        new = mining._retarget(target, [100.0] * 6)       # identical timestamps -> no ZeroDivisionError
        self.assertLessEqual(new, constants.MINE_MAX_TARGET)
        self.assertGreaterEqual(new, target // 4)
        slow = mining._retarget(target, [0, 3000, 6000, 9000, 12000, 15000])
        self.assertGreater(slow, target)                  # slow blocks -> easier target


class ConstantsTests(unittest.TestCase):
    def test_roulette_wheel(self):
        self.assertEqual(len(constants.ROULETTE_NUMBERS), 37)
        colors = [c for _, c in constants.ROULETTE_NUMBERS]
        self.assertEqual((colors.count("green"), colors.count("red"), colors.count("black")), (1, 18, 18))

    def test_casino_win_probability_below_one(self):
        self.assertLess(constants.RTP_CASINO / constants.MIN_MULTI_CASINO, 1)


if __name__ == "__main__":
    unittest.main()
