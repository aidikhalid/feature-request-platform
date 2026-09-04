# Feature Request & Voting Platform

A product-feedback board: users submit feature requests, vote, comment and follow
progress; administrators triage status, publish official responses, merge duplicates and
review usage statistics.

Built as a take-home assessment. The scope is a deliberately **narrow but complete
vertical slice** — every layer from migrations to accessibility is finished for the
features that are present, and what was left out is listed explicitly in
[ARCHITECTURE.md](ARCHITECTURE.md#5-scope-what-is-complete-partial-and-deferred).

**Stack:** React 18 + TypeScript + Vite · FastAPI (Python 3.12) · PostgreSQL 16 ·
SQLAlchemy 2 + Alembic · Docker Compose

---

## 1. Quick start

**Prerequisites:** Docker Desktop (or Docker Engine + Compose v2). Nothing else — Python
and Node run inside the containers.

```bash
cp .env.example .env      # local placeholders only; no real secrets in this repo
docker compose up --build
```

Then open **http://localhost:5173**.

| Service | URL | Notes |
|---|---|---|
| Web app | http://localhost:5173 | Vite dev server |
| API | http://localhost:8000 | FastAPI |
| API docs | http://localhost:8000/docs | OpenAPI, generated from the same schemas that validate requests |
| Health check | http://localhost:8000/health | Used by Compose |
| Database | `localhost:5432` | Postgres, exposed for convenience |

On first start the `api` container runs `alembic upgrade head` and then seeds the
database. The seed is idempotent, so restarting never duplicates data.

### Demo accounts

All seeded accounts use the password **`Password123!`** (the sign-in page lists them and
will fill the form for you).

| Email | Role | Use for |
|---|---|---|
| `admin@example.com` | administrator | status changes, official responses, merging, statistics |
| `pm@example.com` | administrator | a second admin |
| `shinji@example.com` | standard user | voting, commenting, submitting, editing own request |
| `rei@example.com` | standard user | testing that one user cannot edit another's request |

### Stopping and resetting

```bash
docker compose down          # stop, keep the database
docker compose down -v       # stop and delete the database volume (full reset)
```

---

## 2. Running the tests

**Backend — 56 tests, against a real PostgreSQL database:**

```bash
docker compose exec api pytest -v
```

The suite creates and migrates a separate `frp_test` database on the same Postgres
instance, so it never touches your development data.

**Frontend — 16 tests:**

```bash
docker compose exec web npm test
```

Or on the host, if you have Node 22:

```bash
cd web && npm install && npm test && npm run typecheck
```

### What the tests actually cover

The assignment's six business rules were used directly as the test checklist:

| Business rule | Where it is tested |
|---|---|
| A user may vote only once per request | `api/tests/test_voting.py` |
| Repeated API requests must not create duplicate votes | `api/tests/test_voting.py::test_voting_twice_is_a_no_op` |
| Concurrent votes must not produce incorrect totals | `api/tests/test_voting_concurrency.py` |
| Only administrators may change status | `api/tests/test_authorization.py` |
| A user cannot edit another user's request | `api/tests/test_authorization.py` |
| Merging must preserve votes and comments | `api/tests/test_merge.py` |
| A write must not land on a request being merged away | `api/tests/test_merge_concurrency.py` |

The concurrency tests use real threads and real separate database connections, and both
were checked against deliberately broken implementations rather than assumed to work. With
a read-modify-write counter instead of an atomic SQL increment, 25 concurrent votes record
**2**. With the row lock removed from voting and commenting, a write raced against a merge
is left stranded on the retired request.

---

## 3. What you can do in the app

**As a visitor (not signed in)** — browse the board, search, filter by status, sort by
most voted / newest / most discussed, read requests and comments. Vote buttons prompt
sign-in rather than failing.

**As a signed-in user** — submit a request, vote and un-vote, comment, and edit your own
requests.

**As an administrator** — everything above, plus on any request detail page: change
status, publish an official response, and merge the request into another one. The
*Statistics* link in the header shows counts by status, totals and the most-requested
list.

### A tour worth taking

1. Sign in as `shinji@example.com` and vote on a request. **Click the vote button
   rapidly several times** — the count never goes above one. The endpoint is idempotent.
2. Sign out and try to vote → you are sent to sign-in. Sign in as `rei@example.com` and
   open a request written by someone else → no Edit control, and the API returns 403 if
   you call it directly.
3. Sign in as `admin@example.com`, open a request, set its status and publish an official
   response.
4. Still as admin, pick two similar requests. Vote on **both** as the same user first,
   then merge one into the other. The surviving request keeps every comment, and the
   double-voter is counted **once** — see
   [the merge walk-through](ARCHITECTURE.md#43-merging-duplicates-one-transaction).

---

## 4. Project layout

```
.
├── api/                       FastAPI service
│   ├── app/
│   │   ├── main.py            app factory, CORS, error handlers
│   │   ├── config.py          settings, entirely environment-driven
│   │   ├── db.py              engine and request-scoped session
│   │   ├── errors.py          AppError types + the single error envelope
│   │   ├── models/            SQLAlchemy models (the schema)
│   │   ├── schemas/           Pydantic request/response models (validation + OpenAPI)
│   │   ├── core/              password hashing, JWT, auth dependencies
│   │   ├── services/          business logic — voting, merging, stats, admin actions
│   │   ├── api/routes/        HTTP layer: auth, requests, admin
│   │   └── seed.py            idempotent demo data
│   ├── alembic/versions/      migrations
│   └── tests/                 pytest
├── web/                       React + TypeScript client
│   └── src/
│       ├── api/               typed fetch client, types, React Query hooks
│       ├── components/        presentational components + their tests
│       ├── pages/             route-level components that fetch
│       └── lib/               query client, formatting
├── docker-compose.yml
├── .env.example
├── README.md
└── ARCHITECTURE.md            decisions, trade-offs, limitations, next steps
```

The backend is layered **routes → services → models**. Routes resolve authentication and
shape HTTP; services hold the business rules and own transaction boundaries; models are
the schema. Business logic is never written in a route handler, which is what makes the
rules testable without going through HTTP.

---

## 5. API reference

Full interactive documentation at http://localhost:8000/docs.

| Method | Path | Auth | Purpose |
|---|---|---|---|
| `POST` | `/api/auth/register` | — | Create an account (always a standard user) |
| `POST` | `/api/auth/login` | — | Sign in; sets the session cookie |
| `POST` | `/api/auth/logout` | — | Clear the session cookie |
| `GET` | `/api/auth/me` | user | Current user |
| `GET` | `/api/requests` | optional | Browse: `q`, `status`, `sort` (`top`, `new`, `discussed`), `page`, `page_size` |
| `POST` | `/api/requests` | user | Submit a request |
| `GET` | `/api/requests/{id}` | optional | Request detail |
| `PATCH` | `/api/requests/{id}` | owner or admin | Edit title/description |
| `POST` | `/api/requests/{id}/vote` | user | Cast a vote (**idempotent**) |
| `DELETE` | `/api/requests/{id}/vote` | user | Withdraw a vote (**idempotent**) |
| `GET` | `/api/requests/{id}/comments` | optional | List comments |
| `POST` | `/api/requests/{id}/comments` | user | Add a comment |
| `PATCH` | `/api/admin/requests/{id}/status` | **admin** | Change status |
| `PUT` | `/api/admin/requests/{id}/response` | **admin** | Publish an official response |
| `POST` | `/api/admin/requests/{id}/merge` | **admin** | Merge this request into `target_id` |
| `GET` | `/api/admin/stats` | **admin** | Usage statistics |

Every failure returns the same envelope, so the client has one thing to parse:

```json
{
  "error": {
    "code": "validation_error",
    "message": "The submitted data is invalid",
    "details": [{ "field": "title", "message": "String should have at least 5 characters" }]
  }
}
```

Status codes are used consistently: `401` "we don't know who you are", `403` "we know and
no", `404` unknown resource, `409` a rule conflict (already merged, duplicate email),
`422` failed validation.

---

## 6. Configuration

Everything comes from the environment; see [.env.example](.env.example) for the full list.

| Variable | Purpose |
|---|---|
| `DATABASE_URL` | Postgres connection string used by the API and Alembic |
| `JWT_SECRET` | Signs session tokens — **generate a real one for any deployment** (`openssl rand -hex 32`) |
| `JWT_EXPIRE_MINUTES` | Session lifetime |
| `COOKIE_SECURE` | `true` in production so the cookie is HTTPS-only; `false` for local http |
| `CORS_ORIGINS` | Comma-separated allowed origins (cannot be `*` — credentials are enabled) |
| `VITE_API_URL` | API base URL the browser calls |

No secrets are committed. `.env` is gitignored; `.env.example` holds obvious local
placeholders, and the default `JWT_SECRET` is deliberately named so a misconfigured
deployment is loud rather than silent.

---

## 7. Troubleshooting

**`docker compose up` fails on the `api` container** — the database may not have been
ready. Compose waits on a Postgres health check, so simply retry: `docker compose up`.

**"Could not reach the server. Is the API running?" in the browser** — check
`docker compose ps`; the `api` service should be up on port 8000. If you changed
`VITE_API_URL`, restart the `web` container so Vite picks it up.

**Port already in use** — something else is on 5173, 8000 or 5432. Stop it, or change the
left-hand side of the `ports` mappings in `docker-compose.yml`.

**Starting from scratch** — `docker compose down -v && docker compose up --build`.

---

## 8. Where to read next

[ARCHITECTURE.md](ARCHITECTURE.md) covers the decisions and the reasoning: how
authorization, transactions, uniqueness and concurrency are handled; which alternatives
were rejected and why; what is complete, partial and deliberately deferred; the known
risks; and the next production steps.
