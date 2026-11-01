-- =============================================================================
-- Gosha bot: initial schema
-- Source of truth for money: ledger_entries (append-only, every transaction
-- sums to zero). accounts.balance is only a cache maintained by the ledger
-- service and can be rebuilt at any time (see /audit).
-- =============================================================================

CREATE TABLE accounts (
    id             BIGSERIAL PRIMARY KEY,
    code           TEXT        NOT NULL UNIQUE,            -- 'bank', 'user:<tg id>', ...
    kind           TEXT        NOT NULL CHECK (kind IN ('user', 'system')),
    balance        NUMERIC(20, 2) NOT NULL DEFAULT 0,      -- CACHE of SUM(ledger_entries.amount)
    allow_negative BOOLEAN     NOT NULL DEFAULT FALSE,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE users (
    id              BIGINT PRIMARY KEY,                    -- Telegram user id
    gid             BIGINT GENERATED ALWAYS AS IDENTITY UNIQUE,
    account_id      BIGINT      NOT NULL UNIQUE REFERENCES accounts (id),
    name            TEXT        NOT NULL,
    username        TEXT,
    registered_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_farm_at    TIMESTAMPTZ,
    is_admin        BOOLEAN     NOT NULL DEFAULT FALSE,
    is_deleted      BOOLEAN     NOT NULL DEFAULT FALSE,
    transfer_check  BOOLEAN     NOT NULL DEFAULT TRUE,
    hide_username   BOOLEAN     NOT NULL DEFAULT TRUE,
    hide_balance    BOOLEAN     NOT NULL DEFAULT FALSE,
    hide_top        BOOLEAN     NOT NULL DEFAULT FALSE,
    casino_warning  BOOLEAN     NOT NULL DEFAULT TRUE
);
CREATE UNIQUE INDEX users_username_key ON users (lower(username)) WHERE username IS NOT NULL;

CREATE TABLE transactions (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    kind         TEXT        NOT NULL,
    initiator_id BIGINT,
    comment      TEXT,
    meta         JSONB       NOT NULL DEFAULT '{}'::jsonb,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX transactions_kind_idx ON transactions (kind, created_at DESC);

CREATE TABLE ledger_entries (
    id             BIGSERIAL PRIMARY KEY,
    transaction_id UUID           NOT NULL REFERENCES transactions (id),
    account_id     BIGINT         NOT NULL REFERENCES accounts (id),
    amount         NUMERIC(20, 2) NOT NULL CHECK (amount <> 0),
    balance_after  NUMERIC(20, 2) NOT NULL,
    created_at     TIMESTAMPTZ    NOT NULL DEFAULT now()
);
CREATE INDEX ledger_entries_account_idx ON ledger_entries (account_id, id DESC);
CREATE INDEX ledger_entries_tx_idx ON ledger_entries (transaction_id);

-- Every transaction must sum to zero (checked at COMMIT time).
CREATE FUNCTION ledger_check_zero_sum() RETURNS trigger AS $$
DECLARE
    total NUMERIC;
BEGIN
    SELECT COALESCE(SUM(amount), 0) INTO total
      FROM ledger_entries WHERE transaction_id = NEW.transaction_id;
    IF total <> 0 THEN
        RAISE EXCEPTION 'ledger transaction % is unbalanced (sum = %)', NEW.transaction_id, total
            USING ERRCODE = '23514';
    END IF;
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

CREATE CONSTRAINT TRIGGER ledger_zero_sum
    AFTER INSERT ON ledger_entries
    DEFERRABLE INITIALLY DEFERRED
    FOR EACH ROW EXECUTE FUNCTION ledger_check_zero_sum();

-- The ledger is append-only.
CREATE FUNCTION ledger_append_only() RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION 'table % is append-only', TG_TABLE_NAME USING ERRCODE = '42501';
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER ledger_entries_immutable BEFORE UPDATE OR DELETE ON ledger_entries
    FOR EACH ROW EXECUTE FUNCTION ledger_append_only();
CREATE TRIGGER ledger_entries_no_truncate BEFORE TRUNCATE ON ledger_entries
    FOR EACH STATEMENT EXECUTE FUNCTION ledger_append_only();
CREATE TRIGGER transactions_immutable BEFORE UPDATE OR DELETE ON transactions
    FOR EACH ROW EXECUTE FUNCTION ledger_append_only();
CREATE TRIGGER transactions_no_truncate BEFORE TRUNCATE ON transactions
    FOR EACH STATEMENT EXECUTE FUNCTION ledger_append_only();

-- ---- chats -----------------------------------------------------------------
CREATE TABLE chats (
    id         BIGINT PRIMARY KEY,
    type       TEXT        NOT NULL,
    title      TEXT,
    first_seen TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_seen  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE user_chats (
    user_id BIGINT NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    chat_id BIGINT NOT NULL,
    PRIMARY KEY (user_id, chat_id)
);
CREATE INDEX user_chats_chat_idx ON user_chats (chat_id);

CREATE TABLE chat_activity (
    chat_id  BIGINT NOT NULL,
    day      DATE   NOT NULL,
    user_id  BIGINT NOT NULL,
    messages INT    NOT NULL DEFAULT 0,
    PRIMARY KEY (chat_id, day, user_id)
);

-- ---- single-use confirmation buttons ---------------------------------------
CREATE TABLE pending_actions (
    id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    kind       TEXT        NOT NULL,
    owner_id   BIGINT      NOT NULL,
    chat_id    BIGINT,
    payload    JSONB       NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ---- referrals -------------------------------------------------------------
CREATE TABLE referral_codes (
    user_id BIGINT PRIMARY KEY REFERENCES users (id) ON DELETE CASCADE,
    code    INT    NOT NULL UNIQUE
);
CREATE TABLE referral_uses (
    invitee_id BIGINT PRIMARY KEY REFERENCES users (id) ON DELETE CASCADE,
    inviter_id BIGINT NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    tx_id      UUID REFERENCES transactions (id),
    used_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ---- borrow ----------------------------------------------------------------
CREATE TABLE borrow_requests (
    id           BIGSERIAL PRIMARY KEY,
    borrower_id  BIGINT         NOT NULL REFERENCES users (id),
    lender_id    BIGINT         NOT NULL REFERENCES users (id),
    amount       NUMERIC(20, 2) NOT NULL,
    percent      INT            NOT NULL,
    term_hours   INT            NOT NULL,
    amount_due   NUMERIC(20, 2) NOT NULL,
    status       TEXT           NOT NULL DEFAULT 'pending'
                 CHECK (status IN ('pending', 'active', 'repaid', 'expired', 'cancelled')),
    created_at   TIMESTAMPTZ    NOT NULL DEFAULT now(),
    activated_at TIMESTAMPTZ,
    due_at       TIMESTAMPTZ,
    settled_at   TIMESTAMPTZ,
    issue_tx     UUID REFERENCES transactions (id),
    repay_tx     UUID REFERENCES transactions (id)
);
CREATE INDEX borrow_due_idx ON borrow_requests (due_at) WHERE status = 'active';

-- ---- quotes ----------------------------------------------------------------
CREATE TABLE quotes (
    id          BIGSERIAL PRIMARY KEY,
    author_id   BIGINT      NOT NULL,
    author_name TEXT        NOT NULL,
    text        TEXT        NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    verified    BOOLEAN                                -- NULL: new, TRUE: approved, FALSE: reported
);
CREATE TABLE quote_votes (
    quote_id BIGINT   NOT NULL REFERENCES quotes (id) ON DELETE CASCADE,
    user_id  BIGINT   NOT NULL,
    vote     SMALLINT NOT NULL CHECK (vote IN (-1, 1)),
    PRIMARY KEY (quote_id, user_id)
);

-- ---- roulette --------------------------------------------------------------
CREATE TABLE roulette_bets (
    id         BIGSERIAL PRIMARY KEY,
    chat_id    BIGINT         NOT NULL,
    user_id    BIGINT         NOT NULL REFERENCES users (id),
    amount     NUMERIC(20, 2) NOT NULL,
    bet_type   TEXT           NOT NULL,
    multiplier INT            NOT NULL,
    created_at TIMESTAMPTZ    NOT NULL DEFAULT now(),
    stake_tx   UUID REFERENCES transactions (id)
);
CREATE INDEX roulette_bets_chat_idx ON roulette_bets (chat_id);

-- ---- mining ----------------------------------------------------------------
CREATE TABLE mining_state (
    id         SMALLINT PRIMARY KEY CHECK (id = 1),
    seed       TEXT NOT NULL,
    target_hex TEXT NOT NULL
);
CREATE TABLE mining_blocks (
    id         BIGSERIAL PRIMARY KEY,
    seed       TEXT        NOT NULL,
    hash       TEXT        NOT NULL,
    nonce      TEXT        NOT NULL,
    target_hex TEXT        NOT NULL,
    difficulty BIGINT      NOT NULL,
    user_id    BIGINT      NOT NULL,
    found_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    reward_tx  UUID REFERENCES transactions (id)
);

-- ---- feedback --------------------------------------------------------------
CREATE TABLE feedback_pending (
    user_id    BIGINT PRIMARY KEY,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE feedback_messages (
    id          BIGSERIAL PRIMARY KEY,
    user_id     BIGINT      NOT NULL,
    text        TEXT        NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    answered_at TIMESTAMPTZ
);

-- ---- shop ------------------------------------------------------------------
CREATE TABLE shop_categories (
    id   SERIAL PRIMARY KEY,
    name TEXT NOT NULL UNIQUE
);
CREATE TABLE shop_items (
    id          SERIAL PRIMARY KEY,
    category_id INT            NOT NULL REFERENCES shop_categories (id) ON DELETE CASCADE,
    name        TEXT           NOT NULL,
    price       NUMERIC(20, 2) NOT NULL CHECK (price > 0),
    UNIQUE (category_id, name)
);
CREATE TABLE purchases (
    id         BIGSERIAL PRIMARY KEY,
    user_id    BIGINT         NOT NULL REFERENCES users (id),
    item_id    INT            NOT NULL REFERENCES shop_items (id),
    price      NUMERIC(20, 2) NOT NULL,
    tx_id      UUID REFERENCES transactions (id),
    created_at TIMESTAMPTZ    NOT NULL DEFAULT now()
);

-- ---- misc ------------------------------------------------------------------
CREATE TABLE kv (
    key   TEXT PRIMARY KEY,
    value JSONB NOT NULL
);
CREATE TABLE balance_snapshots (
    taken_at    TIMESTAMPTZ PRIMARY KEY DEFAULT now(),
    total       NUMERIC(20, 2) NOT NULL,
    users_count INT            NOT NULL
);
