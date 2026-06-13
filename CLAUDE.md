# CLAUDE.md

Guidance for Claude Code (claude.ai/code) when working in this repository.

## What this is

The backend for the **Insurance Core POC**: an in-house policy administration
core that replaces legacy PAS functionality one product at a time. It exposes a
**headless rating engine** plus product/quote/policy APIs. The frontend is the
sibling `dgc_front` repo.

**Status — repurposed scaffold.** This started as a generic business-API
template (FastAPI + async SQLAlchemy + Alembic, with JWT auth and RBAC). The
*infrastructure* (DB layer, migrations, observability, auth/JWT, app bootstrap)
is real and stays. The *business domain* is being replaced: anything referencing
control centers, install centers, installers, jobs, finance, dispatch, coin
history, LINE notify, or image/PDF generation is **leftover template scaffold
to be removed**, not insurance requirements. Don't model insurance around
center-scoping. The auth tables (`users`/`roles`/`permissions`) are kept.

## Architecture principles (do not violate)

- **Rating is table-driven, never computed.** Actuarial math is OUT of scope.
  Premiums come from versioned rate tables loaded from regulatory filings.
- **Products declare their rating dimensions** (e.g. age, sex). Adding a product
  is data + config, **never** a schema migration.
- **Effective-dating everywhere.** A policy binds to the rate *version* in effect
  on its **effective date**, not its quote date.
- **Rate tables are immutable, versioned reference data** tied to a filing
  `source_ref`. Never edit rates in place — load a new version.
- **The rating engine is headless.** It lives behind its own API route and knows
  nothing about customers or policies — given (product, dimensions, effective
  date) it returns a premium.

## Stack

- Python 3.11+, **FastAPI** ≥0.115, **SQLAlchemy 2.0 (async)**, **Alembic**,
  **Pydantic v2** / pydantic-settings.
- **Database: PostgreSQL via `asyncpg`** (async throughout). Default
  `DATABASE_URL=postgresql+asyncpg://dgc:password@localhost:5432/dgc`.
  > Note: this supersedes any earlier "SQLite dev / SQL Server prod" note — the
  > real scaffold is async Postgres. Keep it.
- Auth: `python-jose` (JWT) + `passlib[bcrypt]`.
- Lint/format: **ruff** (line length 100). Tests: **pytest** (`asyncio_mode=auto`).
- Some heavy deps (boto3, pillow/pillow-heif, weasyprint, fastapi-mail,
  apscheduler, openpyxl) are scaffold carryover; `openpyxl` is the one likely
  reused — for loading xlsx rate tables.

## Commands

```bash
uv sync                                   # or: pip install -r requirements.txt
cp .env.example .env                      # set DATABASE_URL, JWT secret, etc.
uvicorn main:app --reload                 # http://localhost:8000 (/docs when DEBUG=true)
alembic revision --autogenerate -m "msg"  # generate a migration
alembic upgrade head                      # apply migrations
pytest                                    # run tests
ruff check .                              # lint
```

`alembic/versions/` ships **empty** — generate the initial schema yourself.

## Layout

```
main.py                 # FastAPI app: CORS, request-id + access-log middleware,
                        #   exception handlers, lifespan (disposes engine), /health, /api/hello
config/                 # env-driven settings, composed in settings.py
                        #   (database, jwt, email, line_notify, storage, parameters)
api/
  router.py             # aggregates v1 routers under /api
  dependencies.py       # get_db, get_current_user, has_permission(code) / has_any_permission()
  v1/                   # route modules (auth.py today; add products/quotes/policies)
domain/
  base.py               # DeclarativeBase + NAMING_CONVENTION + IdMixin / TimestampMixin
  user/ role/ permission/   # auth models + Pydantic schemas (KEEP)
  auth/                 # auth request/response schemas
integrations/db/
  engine.py             # async engine; IMPORTS every model module so mappers resolve
  session.py            # async_session_factory + get_session() FastAPI dep
  unit_of_work.py       # UnitOfWork — atomic multi-repository transactions
  repositories/         # one module per aggregate (user_repo today)
services/               # business logic (jwt_service, auth_service, security/hashing)
observability/          # structlog logging, request-id + access-log middleware, exception handlers
alembic/                # async env.py (auto-discovers models) + empty versions/
```

## Conventions

- **All schema changes go through Alembic** — never `create_all` in app code.
- **`Decimal` for money, never `float`** — use SQLAlchemy `Numeric` columns.
- Models inherit `Base` + `IdMixin`/`TimestampMixin` from `domain/base.py`. The
  metadata `NAMING_CONVENTION` keeps autogenerate diffs stable — don't bypass it.
- **Register every new model module in BOTH `integrations/db/engine.py` and
  `alembic/env.py`** or the mapper won't resolve it / autogenerate won't see it.
- DB access: routes depend on `get_db` (commits on success, rolls back on error).
  Use `UnitOfWork` only when one business operation spans multiple repositories
  and must commit atomically.
- Pages/routes never touch the engine directly — go API route → service →
  repository → session.
- Permissions are enforced at the route:
  `dependencies=[Depends(has_permission("rate_table.load"))]`. Seed permission
  rows + role grants in a migration; `admin`/`owner` bypass via `*`.
- Loaders validate xlsx dimensions against the product's **declared** rating
  dimensions before inserting a rate version.

## Building the insurance domain (recipe)

Follow the scaffold's add-a-feature flow for each aggregate:

1. `domain/<x>/{model,schema}.py`, then register the model in
   `integrations/db/engine.py` **and** `alembic/env.py`.
2. `integrations/db/repositories/<x>_repo.py`.
3. `services/<x>.py` for business logic.
4. `api/v1/<x>.py`, included in `api/router.py`.
5. `alembic revision --autogenerate -m "..."` + `alembic upgrade head`.

Target aggregates and their homes:

- **products** + **product_rating_dimensions** → `domain/product/`
- **rate_table_versions** + **rate_cells** (immutable, versioned, `source_ref`) →
  `domain/rate/`; xlsx ingestion in `services/rate_loader.py` (validates xlsx
  columns against the product's declared dimensions).
- **policies** (bind to a rate version by effective date) → `domain/policy/`
- **headless rating engine** → `services/rating.py` exposing `quote(...)`, wired
  to its own route in `api/v1/quotes.py`.

Commit your actual premium table (e.g. `data/Premium_Table.xlsx`) as seed data.
