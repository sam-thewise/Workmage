# Tests

- **Unit tests** (`test_action_infra.py`): Policy and trust helpers; no database required.
- **Integration tests** (`test_action_infra_endpoints.py`): Action-infra API endpoints; require a running Postgres (see `DATABASE_URL`). If the database is unreachable, these tests are skipped.

Run all tests:

```bash
python -m pytest tests/ -v
```

Run with a local Postgres (e.g. Docker):

```bash
docker compose up -d postgres
# set DATABASE_URL if needed, e.g. postgresql+asyncpg://postgres:postgres@localhost:5432/agentfoundry
python -m pytest tests/ -v
```
