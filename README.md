# Icon Invest — FastAPI Phase 2

This is the second-stage backend migration from the original Express/Mongoose API.

## Run

1. Create a Python 3.12 virtual environment.
2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Copy `.env.example` to `.env` and set real values.
4. Start:

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Swagger:
`http://127.0.0.1:8000/docs`

## Security rules

- Passwords are hashed.
- Passwords are never returned to clients.
- Admin endpoints require a verified JWT role.
- Wallet mutation endpoints require admin authentication.
- Financial requests are authenticated from the JWT rather than trusting a browser-supplied email.
- Deposits and withdrawals start as `pending`.
- Investment debits use an atomic balance condition.
- Secrets are loaded from environment variables.

## Important migration note

This backend does not yet automatically migrate or modify the existing MongoDB data. Back up the database before any migration script is introduced.

Payment provider webhooks and email delivery are deliberately separated from the core accounting logic and should be implemented only after the transaction/ledger rules are finalized.


## Phase 3 — database + frontend migration

### 1. Back up MongoDB

Do this before touching production data.

### 2. Dry run

From the backend directory:

```bash
python scripts/migrate_legacy.py
```

This only reports what would be normalized.

### 3. Apply normalization

Only after confirming the backup:

```bash
python scripts/migrate_legacy.py --apply
```

The script does not delete records and keeps the original `_id`.

### 4. Frontend

Copy `frontend-migration/src/lib/api.js` into the Next.js project and add:

```env
NEXT_PUBLIC_API_URL=http://localhost:8000
```

The frontend should gradually be changed to use `apiFetch()` instead of hard-coded `https://iconinvest.onrender.com`.

### Important

Do not switch the production frontend to FastAPI yet. First run FastAPI locally against a copy/staging database and test login, registration, plans, deposits, investments, withdrawals, wallets, and admin operations.
