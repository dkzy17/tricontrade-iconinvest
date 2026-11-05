BEGIN;

CREATE TABLE IF NOT EXISTS admin_audit_logs (
    id SERIAL PRIMARY KEY,
    actor_id INTEGER NOT NULL REFERENCES users(id),
    actor_email VARCHAR(255) NOT NULL,
    actor_role VARCHAR(20) NOT NULL,
    action VARCHAR(100) NOT NULL,
    target_user_id INTEGER NULL REFERENCES users(id),
    target_email VARCHAR(255) NULL,
    details JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_admin_audit_logs_actor_id
    ON admin_audit_logs(actor_id);

CREATE INDEX IF NOT EXISTS ix_admin_audit_logs_target_user_id
    ON admin_audit_logs(target_user_id);

CREATE INDEX IF NOT EXISTS ix_admin_audit_logs_action
    ON admin_audit_logs(action);

CREATE INDEX IF NOT EXISTS ix_admin_audit_logs_created_at
    ON admin_audit_logs(created_at);

COMMIT;
