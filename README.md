# DGC API

FastAPI + SQLAlchemy 2 (async) + Alembic scaffold. Generated from the same
structure as the reference app with all feature code removed — it keeps the
app bootstrap, auth (users / roles / permissions + JWT), DB layer,
observability, and migration setup so you can build features on top.

## Layout

```
main.py                     # FastAPI app: middleware, lifespan, /health, /api/hello
config/                     # settings (env-driven)
api/
  router.py                 # aggregates v1 routers (auth registered)
  dependencies.py           # get_db, get_current_user, has_permission
  v1/auth.py                # login / refresh / logout / me
domain/
  base.py                   # Declarative Base + Id/Timestamp mixins
  user/ role/ permission/   # auth models + schemas
  auth/                     # auth request/response schemas
integrations/db/            # engine, session, repositories/ (user_repo)
services/                   # jwt_service, auth_service, security (hashing)
observability/             # logging, request-id + access-log middleware, exceptions
alembic/                    # env.py + (empty) versions/
```

## Run

```bash
# deps (uv or pip)
uv sync                     # or: pip install -r requirements.txt
cp .env.example .env        # set DATABASE_URL, JWT secret, etc.

# create the initial schema (users/roles/permissions are defined; no
# migration ships with the scaffold — generate one against your DB):
alembic revision --autogenerate -m "initial auth schema"
alembic upgrade head

uvicorn main:app --reload   # http://localhost:8000  (/docs when DEBUG)
```

## Adding a feature

1. `domain/<feature>/{model,schema}.py` — register the model module in
   `integrations/db/engine.py` and `alembic/env.py` so it's mapped + migratable.
2. `integrations/db/repositories/<feature>_repo.py`.
3. `services/<feature>_service.py` for business logic.
4. `api/v1/<feature>.py` and include it in `api/router.py`.
5. `alembic revision --autogenerate` + `alembic upgrade head`.

Permissions are checked via `Depends(has_permission("<resource>.<action>"))`;
seed permission rows + role grants in a migration (admin/owner bypass via `*`).
