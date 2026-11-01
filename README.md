# Gosha bot (aiogram 3 + PostgreSQL)

Telegram-бот с экономикой коинов. Переписан с pyTelegramBotAPI + JSON-файлов на **aiogram 3 + asyncpg + PostgreSQL**.

## Запуск

```bash
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env            # впишите TOKEN, DATABASE_DSN, OWNER_IDS

# PostgreSQL 13+ (нужна функция gen_random_uuid()):
#   createuser gosha && createdb -O gosha gosha
#   psql -c "ALTER USER gosha PASSWORD 'gosha'"

python3 main.py                 # или ./run.sh
```

Схема БД создаётся автоматически при старте (`app/db/migrations/*.sql`, учёт в `schema_migrations`).
Тесты чистой логики: `python -m unittest discover -s tests -v`.

## Структура

```
main.py                 подключение к БД, сборка бота и запуск polling
app/
  config.py             .env -> Settings        constants.py   параметры игр и экономики
  logging_setup.py      логи (консоль + logs/bot.log)
  callbacks.py          фабрики callback_data
  db/                   pool, migrate, ledger (двойная запись), репозитории (users, chats, ...)
  handlers/__init__.py  ВСЕ роутеры подключаются здесь (порядок важен)
  handlers/*.py         start, settings, economy, games, roulette, dice, borrow, social,
                        quotes, mining, shop, feedback, admin, utility, chat_tools, actions
  middlewares/          трекинг чатов/активности, загрузка пользователя, RequireUser
  services/             фоновые задачи, runtime-состояние, клавиатуры, представления
  utils/                деньги, время, безопасный калькулятор, графики, фильтры
```

## Деньги: как это устроено

* **Источник истины** — `ledger_entries` (только добавление: UPDATE/DELETE/TRUNCATE запрещены триггером).
* Любое движение средств — одна запись в `transactions` + проводки в `ledger_entries`.
  **Сумма проводок каждой транзакции равна нулю** (проверяется в Python и отложенным constraint-триггером
  БД на COMMIT).
* `accounts.balance` — **кэш**. Он обновляется в той же транзакции под `SELECT ... FOR UPDATE`
  (блокировки в порядке id, без дедлоков) и пересчитывается командой `/audit repair`.
* Системные счета: `bank`, `emission` (источник/сток монет: награды за майнинг, рефералы, админ-правки,
  стартовые 10 000 в банке), `jackpot`, `number_pot`, `roulette_escrow` (ставки рулетки).
  Сумма всех счетов, включая `emission`, всегда 0.
* Суммы — `NUMERIC(20,2)` / `Decimal`, никаких float.
* Отрицательный баланс возможен только при списании просроченного займа (`/borrow`), как в оригинале.

## Основные исправления относительно оригинала

* Падения: `call.mesage`, `get_coin_form` не импортирован в `farm.py`, `bot` не определён в `msg_all`,
  `json.dump(..., j)`, `NameError` в `/spin` (`databack`), `casino` читал `users[id]` до проверки регистрации.
* `register()` затирал только что созданного пользователя устаревшим словарём; реферальная ссылка при
  первом `/start` не начисляла бонус.
* Деньги «пропадали»: ставки рулетки списывались, но не попадали в банк; казино/кости/guess правили
  баланс без записи; `moreless` округлял выигрыш до целого.
* Гонки: весь JSON перезаписывался из разных потоков; теперь транзакции и блокировки в БД.
  Кнопки подтверждения одноразовые (`pending_actions`, `DELETE ... RETURNING`), данные не лежат в callback.
* `/mute` игнорировал время; `/top` падал на `len//5 == 0` и превышал лимит подписи к фото; настройка
  `transfer_check` получателя игнорировалась; `/info` для обычных пользователей не работал (дубль команды).
* `safe_calc`: регулярка пропускала `**` (DoS). Теперь AST-калькулятор без `eval`/`numexpr`.
* Склонение «коин/коина/коинов» (11–14, дробные числа).
* Мёртвый код удалён: `bank.py`, `credit.py`, `bot_control.py`, `checks.json`, `bot_stat.txt`, `/update`.
  `/exec` (исполнение кода от имени владельца) не перенесён намеренно.

## Что изменилось в поведении

* Флаг техобслуживания: `/maintenance on|off` (вместо `bot_stat.txt`).
* `/info` — информация о чате (для всех), экономика для владельца — `/stats`.
* `/logs` — последние операции из ledger (вместо текстовых файлов `Logs/*.txt`).
* `/number`: банк раз в час добавляет в банк призов `NUMBER_POT_GROWTH` (в оригинале приз никогда не рос).
* Новые команды: `/audit [repair]`, `/qverify`, `/qdel`, `/shop_add` (магазин теперь реально продаёт: цена идёт в банк).
* Рулетка: ставки лежат в escrow, при нехватке средств в банке раунд отменяется с возвратом ставок.
* Удаление аккаунта — «мягкое»: остаток уходит в банк, история ledger сохраняется.
