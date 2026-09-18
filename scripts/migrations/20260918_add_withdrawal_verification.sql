BEGIN;

CREATE TABLE IF NOT EXISTS withdrawal_verifications (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id),
    issued_by INTEGER NOT NULL REFERENCES users(id),
    code_hash VARCHAR(128) NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMPTZ NOT NULL,
    used_at TIMESTAMPTZ NULL,
    token_used_at TIMESTAMPTZ NULL
);

CREATE INDEX IF NOT EXISTS ix_withdrawal_verifications_user_id
    ON withdrawal_verifications (user_id);

CREATE INDEX IF NOT EXISTS ix_withdrawal_verifications_status
    ON withdrawal_verifications (status);

CREATE INDEX IF NOT EXISTS ix_withdrawal_verifications_expires_at
    ON withdrawal_verifications (expires_at);

COMMIT;
