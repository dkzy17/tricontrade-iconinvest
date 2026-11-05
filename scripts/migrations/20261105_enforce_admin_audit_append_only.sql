BEGIN;

CREATE OR REPLACE FUNCTION prevent_admin_audit_log_mutation()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    RAISE EXCEPTION 'admin_audit_logs is append-only';
END;
$$;

DROP TRIGGER IF EXISTS trg_admin_audit_logs_no_update_delete
    ON admin_audit_logs;

CREATE TRIGGER trg_admin_audit_logs_no_update_delete
BEFORE UPDATE OR DELETE ON admin_audit_logs
FOR EACH ROW
EXECUTE FUNCTION prevent_admin_audit_log_mutation();

DROP TRIGGER IF EXISTS trg_admin_audit_logs_no_truncate
    ON admin_audit_logs;

CREATE TRIGGER trg_admin_audit_logs_no_truncate
BEFORE TRUNCATE ON admin_audit_logs
FOR EACH STATEMENT
EXECUTE FUNCTION prevent_admin_audit_log_mutation();

COMMIT;
