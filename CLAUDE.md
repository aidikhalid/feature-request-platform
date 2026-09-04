# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project context

A feature-request and voting platform built as a **take-home assessment** (Senior Full-Stack,
Gamuda Tech) under a stated 6–8 hour timebox. The scope is a deliberately narrow but complete
vertical slice, and the omissions are the deliverable as much as the code is.

Two consequences for any work here:

- **Do not add deferred features.** `ARCHITECTURE.md` §5 lists what was intentionally left out
  (real-time, caching layer, notifications, audit log, rate limiting, full-text search, cursor
  pagination, E2E tests). Adding one contradicts a graded, written trade-off.
- **`README.md` and `ARCHITECTURE.md` are graded deliverables.** If a change alters behaviour,
  a documented command, a test count, or a stated trade-off, update them in the same change.

## Commands

Everything runs in Docker; `./api` and `./web` are volume-mounted, so edits hot-reload without a
rebuild. Rebuild only when dependencies change (`docker compose up -d --build <service>`).

```bash
cp .env.example .env && docker compose up --build   # first run: migrates + seeds
docker compose down -v                              # full reset (drops the database)
docker compose logs -f api                          # tail a service
```

| Task | Command |
|---|---|
| Backend tests | `docker compose exec api pytest -q` |
| One backend test | `docker compose exec api pytest tests/test_voting.py::test_voting_twice_is_a_no_op -v` |
| Frontend tests | `docker compose exec web npm test` |
| One frontend test | `docker compose exec web npx vitest run src/components/VoteButton.test.tsx -t "rolls back"` |
| Typecheck | `docker compose exec web npm run typecheck` |
| Production build | `docker compose exec web npm run build` |
| psql | `docker compose exec db psql -U frp -d frp` |
| New migration | `docker compose exec api alembic revision --autogenerate -m "message"` |
| CI | `.github/workflows/ci.yml` runs the tests, typecheck and build rows above on every push and PR |

There is no linter or formatter configured. Match the surrounding style.

## Architecture

**Backend layering is `routes → services → models`, and it is load-bearing.** Routes
(`api/app/api/routes/`) resolve authentication and shape HTTP only. Services
(`api/app/services/`) hold every business rule and own transaction boundaries. Presenters
(`api/app/api/presenters.py`) map models to response schemas so `has_voted` is computed one way
everywhere. **Never put business logic in a route handler** — the tests call services directly,
which is what makes the concurrency tests possible.

**One request = one session = one transaction.** `get_db` in `api/app/db.py` yields a
request-scoped session; services commit explicitly and anything unhandled rolls the request back.

**Errors:** services raise `AppError` subclasses from `api/app/errors.py` (`NotFound`,
`Forbidden`, `Unauthorized`, `Conflict`, `BadRequest`); handlers registered in `main.py` turn
those and Pydantic failures into one envelope, `{"error": {code, message, details}}`. The frontend
parses exactly that shape into `ApiError` (`web/src/api/client.ts`). Keep the envelope intact —
both sides depend on it, and `422` details drive inline field errors.

**Frontend:** React Query owns all server state; React state holds only form fields and local UI
flags. Every query key lives in the `keys` object in `web/src/api/hooks.ts` — add new ones there.
Browse filters live in the URL (`BrowsePage` + `useSearchParams`), not component state. Pages
fetch and compose; components in `web/src/components/` are presentational and take props, which is
why `VoteButton` is unit-testable.

## Invariants that must not be broken

These implement the assessment's business rules. Each is covered by a test that fails if the
mechanism is removed.

1. **All vote writes go through `api/app/services/vote_service.py`.** Uniqueness is a database
   constraint (`uq_votes_user_request`), inserts use `ON CONFLICT DO NOTHING`, and both vote
   endpoints are idempotent — the frontend's optimistic update depends on that.
2. **Denormalised counters (`vote_count`, `comment_count`) move with atomic SQL** —
   `vote_count = vote_count + 1` evaluated by Postgres — in the same transaction as the row, and
   only when `rowcount == 1`. A Python read-modify-write loses updates under concurrency; it was
   measured at 2 recorded votes out of 25. Never recompute a counter in application code.
3. **The admin router declares `dependencies=[Depends(require_admin)]` at router level**
   (`api/app/api/routes/admin.py`), so new admin endpoints are protected by default. Do not
   replace it with per-handler checks.
4. **Ownership checks load the resource first, so 404 precedes 403** (see
   `request_service.update_request`) — otherwise the endpoint reveals which ids exist.
5. **Merged requests are read-only, hidden from the board, and excluded from stats.** Anything
   querying `feature_requests` for user-facing lists must filter `merged_into_id IS NULL`.
   `merge_service.py` locks both rows `FOR UPDATE` ordered by id, deletes duplicate votes before
   moving the rest, re-points earlier duplicates at the new survivor, and recomputes counters
   from the rows — do not add the old counters together. **`merged_into_id` must always resolve
   to a live request in one hop.**
6. **Any write that first checks `is_merged` must hold a row lock across that check** — use
   `request_service.get_request_for_update`, not `db.get`. Otherwise a merge commits in the gap
   and the row is stranded on a retired request. Lock exactly one row so it cannot deadlock
   against the merge's ordered two-row lock.
7. **User input going into `LIKE`/`ILIKE` must escape `\`, `%` and `_`** and pass `escape="\\"`;
   see `request_service.list_requests`.
8. **`role` is never accepted from a client.** Registration always creates a standard user.

## Test harness specifics

- **Backend tests run against a real Postgres** (`frp_test`, created and migrated automatically),
  never SQLite: the guarantees under test are a unique index and row-level locking, which SQLite
  cannot express. `api/tests/conftest.py` rewrites `DATABASE_URL` **before** importing any `app`
  module — keep new imports below that block.
- Isolation is `TRUNCATE` between tests, not a wrapping rollback, because services commit their
  own transactions. Concurrency tests open their own `SessionLocal` per thread.
- Helpers `make_user`, `make_request`, `sign_in` and the `user`/`admin`/`feature_request` fixtures
  live in `conftest.py`.
- **Frontend tests that seed the query cache must set `staleTime: Infinity`** on the test
  `QueryClient`, or a background refetch fires and `fetch` assertions see an unexpected GET.
- **Never hand-set a cookie on a `TestClient` that has already signed in.** `cookies.set()` adds
  a second jar entry rather than replacing the login cookie, and which one is sent is undefined.
  Auth-failure tests use a client that never logged in (see `tests/test_auth.py`).

## Gotchas

- **New Postgres enums in migrations** must use `postgresql.ENUM(..., create_type=False)` plus an
  explicit `.create(bind, checkfirst=True)`. Without `create_type=False`, `create_table` also
  emits `CREATE TYPE` and the second one fails. See `alembic/versions/0001_initial_schema.py`.
- Migrations run from the `api` container's command, not from `create_all()`. `alembic/env.py`
  takes its URL from `app.config.settings`, ignoring `alembic.ini`.
- CORS runs with `allow_credentials=True`, so `CORS_ORIGINS` must be an explicit list — `*` is
  incompatible and will break the session cookie.
- The session cookie name comes from `settings.cookie_name` (`frp_session`); tests that tamper
  with it hardcode that string.
