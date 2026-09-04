# Architecture notes

Decisions, trade-offs, limitations and next steps for the Feature Request & Voting
Platform. Written alongside the code rather than afterwards, so it records what was
actually decided and why.

---

## 1. The shape of the slice

The brief asks for a production-minded vertical slice rather than full coverage, and
weights judgment far above volume — functional correctness is 15% of the marks, while
implementation quality, testing, architecture and security together make up the rest. The
plan followed from that:

**Build the whole user journey, thin. Go deep on the three things the brief signals
hardest.**

The journey: register and sign in → browse with search, filter and sort → submit → vote
and un-vote → comment → admin changes status and publishes an official response → admin
merges duplicates → admin reads usage statistics.

The depth, chosen because the brief's own business rules point at them:

1. **Vote integrity** — four of the six stated rules are about voting.
2. **Server-enforced authorization**, proved by tests rather than by hidden buttons.
3. **Merging inside one transaction**, including the case the rule does not mention: a
   user who voted on *both* requests.

Everything else was deliberately left out and is listed in §5. A deferred feature with a
stated reason is a decision; a silently missing one is a gap.

---

## 2. Choices, and what was rejected

### 2.1 PostgreSQL, not SQLite

The interesting one, because SQLite would have been simpler.

The rules under test are enforced *by the database*, and SQLite cannot express two of
them:

- **`SELECT ... FOR UPDATE` does not exist in SQLite.** That is the row-level lock the
  merge takes on both requests. SQLAlchemy's `with_for_update()` does not raise on
  SQLite — it silently does nothing, so the merge's deadlock safety would be decoration.
- **SQLite has a single global write lock.** Concurrent writers serialise or fail with
  `database is locked`. Fire 25 simultaneous votes at SQLite and a correct total proves
  nothing about *this* design — SQLite serialised them. The test would pass for the wrong
  reason.

Also: the brief asks for Docker-based local setup of "the required services", and SQLite
is a file rather than a service; and testing on a different engine than you deploy on is
a classic source of bugs that only appear in production.

For the record, `INSERT ... ON CONFLICT DO NOTHING` *is* supported by SQLite — the
idempotency mechanism would have been fine. It is locking and genuine concurrency that
rule it out. If the brief had not asked about concurrency, SQLite would have been a
reasonable choice for an app this size.

Cost accepted: a container that takes a few seconds to become healthy, and slower tests.

### 2.2 FastAPI + SQLAlchemy 2 + Alembic

FastAPI earns its place here specifically: Pydantic gives server-side validation as a
first-class object rather than hand-written checks, its dependency injection makes
authorization a declarative, individually testable unit, and OpenAPI docs fall out of the
same schemas that validate requests — so the documentation cannot drift from the code.

**Sync SQLAlchemy, not async.** The transaction boundaries in this application are the
interesting part, and synchronous sessions make them obvious on the page. FastAPI runs
sync endpoints in a threadpool, which is more than adequate at this scale. Async would
add `await` noise and a second mental model for no measured gain.

**Alembic, and never `create_all()`.** Migrations are the schema's history. The test
suite runs the same migrations a deployment runs, so the schema under test is the real
schema.

### 2.3 Session in an httpOnly cookie, not a bearer token in `localStorage`

A JWT is set as `HttpOnly; SameSite=Lax; Secure` (Secure off for local http). JavaScript
cannot read it, so an XSS bug cannot exfiltrate the session — which is the main practical
argument against the `localStorage` pattern most tutorials show.

Rejected alternatives, and their honest trade-offs:

| Option | Why not |
|---|---|
| Bearer token in `localStorage` | Any XSS hands over the account outright |
| Bearer token in memory only | Session lost on every page refresh |
| Server-side sessions in Postgres | Instantly revocable, but a database read on every request; kept as a next step (§7) |

The cost of the choice: JWTs are stateless, so a session **cannot be revoked before it
expires**. Mitigated with a short-ish lifetime; the real fix is a sessions table. And
because the cookie travels automatically, CSRF matters — `SameSite=Lax` covers the
state-changing verbs used here, and §6 records what else production would want.

### 2.4 React Query for server state, no Redux

Nearly all state in this application is a *cache of server data*, not application state.
React Query models that directly: fetching, staleness, retries, loading and error flags,
and cache invalidation. React's own `useState` holds the genuinely local things — form
fields and whether a confirmation is showing.

Adding Redux would mean hand-writing loading booleans, error fields and invalidation
logic that React Query already gets right. The one thing Redux would buy — a single
inspectable store — is not worth that trade at this size.

**Filter state lives in the URL**, not in component state, so a filtered view is
shareable and bookmarkable and the browser's back button behaves. The URL is the single
source of truth and React Query keys off it, caching each filter combination.

### 2.5 Denormalised vote and comment counters

`feature_requests.vote_count` and `.comment_count` are stored, not computed on read.

- **Why:** the board is the hot path. Counting votes per row means a correlated subquery
  per card; sorting by popularity means counting *every* request before ordering. A stored
  integer keeps the list to a single indexed query and makes `ORDER BY vote_count DESC`
  usable.
- **Cost:** two places can disagree if any code path writes a vote without going through
  the service. Contained by keeping all vote writes in `vote_service.py`, updating the
  counter in the same transaction, and asserting counter-equals-rows in the tests.
- **Rejected:** `COUNT(*)` on read (simpler, and correct by construction — the right
  choice at small scale, but it does not sort well); a database trigger (self-healing and
  impossible to bypass, but hides business logic from the application, which is a poor
  trade when the application is where reviewers look for it).

### 2.6 `ILIKE` search, not full-text search

Search is `ILIKE '%term%'` across title and description. Honest at this data size, and
one line to read. It cannot use a normal index and has no relevance ranking, so §7 records
Postgres full-text search with a GIN index as the next step. Building that now would have
been optimising a board with twenty rows.

The user's term is escaped before it goes into the pattern (`\`, `%` and `_`, with an
explicit `ESCAPE`). Otherwise `%` and `_` are wildcards rather than characters: searching
for `100%` would also match "1000 concurrent users", `sign_in` would match "signxin", and
a lone `%` would return the entire board.

---

## 3. Data model

```
users                      feature_requests                    votes
─────                      ────────────────                    ─────
id                         id                                  id
email          UNIQUE      title                               user_id            ┐ UNIQUE
display_name               description                         feature_request_id ┘ together
password_hash              status        (enum, 5 values)       created_at
role           (enum)      author_id     → users
created_at                 official_response                   comments
                           official_response_at                ────────
                           official_response_by_id → users     id
                           merged_into_id → feature_requests   feature_request_id
                           vote_count    (denormalised)        author_id → users
                           comment_count (denormalised)        body
                           created_at, updated_at              created_at
```

Notes on the less obvious parts:

- **`status`** is a Postgres enum of exactly the five supported values, so an invalid
  status cannot be stored even by a direct SQL write. Pydantic rejects it at the edge too,
  giving a `422` rather than a `500`.
- **`merged_into_id`** is a self-reference. Non-null means "this request is a duplicate;
  its activity now lives on that one". A merged request is hidden from the board,
  excluded from statistics, and read-only.
- **`role`** on the user is the entire identity model: standard user and administrator.
  It is never accepted from a client — registration always creates a standard user, and
  there is a test for exactly that.
- **Indexes:** `votes(user_id, feature_request_id)` unique (the business rule),
  `votes(feature_request_id)`, `comments(feature_request_id)`,
  `feature_requests(status)`, and descending indexes on `vote_count` and `created_at` for
  the two default sorts.

---

## 4. Making integrity visible

The brief asks for this explicitly, so here is each mechanism with the code that
implements it.

### 4.1 Authorization — `api/app/core/deps.py`

Two dependencies, declared once:

- `get_current_user` → `401` when we cannot identify the caller.
- `require_admin` → `403` when we can, and the answer is still no.

The admin router declares `dependencies=[Depends(require_admin)]` **at the router level**,
so a new admin endpoint is protected by default rather than by the author remembering.
Ownership (`a user cannot edit another user's request`) is checked in
`request_service.update_request`, not in the route.

Two details worth pointing at:

- **404 before 403.** `update_request` loads the request first, so probing an unknown id
  returns "not found" rather than "forbidden". Otherwise the endpoint becomes an oracle
  telling an attacker which ids exist.
- **Hiding a button is not authorization.** The admin controls are hidden from standard
  users for clarity, and the API refuses them regardless. That is what
  `api/tests/test_authorization.py` asserts.

### 4.2 Vote integrity — `api/app/services/vote_service.py`

Four rules meet in one function. The mechanism, in order:

1. **Uniqueness belongs to the database.** `UNIQUE(user_id, feature_request_id)`. An
   application-level "has this user already voted?" cannot be trusted: two concurrent
   requests both read "no" before either writes. Only the database can break that tie.
2. **The endpoints are idempotent.** `POST` issues
   `INSERT ... ON CONFLICT DO NOTHING` and returns `200` with the settled vote state
   whether or not a row was created; `DELETE` behaves the same way on the first and fifth
   call. A retried request, a flaky network, or an impatient double-click cannot create a
   second vote. This is why the optimistic UI is safe.
3. **The counter moves atomically, and only when something changed.** The counter is
   touched only when `rowcount == 1`, using
   `UPDATE feature_requests SET vote_count = vote_count + 1` — arithmetic evaluated *by
   Postgres* under a row lock. Reading the value into Python, adding one, and writing it
   back would lose updates under concurrency.
4. **One transaction.** The vote row and the counter are committed together, so they
   cannot disagree if the request fails halfway.

**This is tested, and the test has teeth.** `test_voting_concurrency.py` fires 20
simultaneous votes from one user (expects exactly one vote) and 25 from different users
(expects exactly 25), each in its own thread with its own database connection. Against a
deliberately naive read-modify-write counter the second test reports **2 out of 25** — 23
lost updates. A concurrency test that cannot fail is worth nothing, so this was checked
rather than assumed.

### 4.3 Merging duplicates — one transaction

`api/app/services/merge_service.py`. All of the following either happens completely or not
at all:

1. **Lock both rows** with `SELECT ... FOR UPDATE`, **ordered by id**. Deterministic lock
   ordering is what stops two admins merging overlapping pairs (A→B and B→A at the same
   moment) from deadlocking.
2. **Validate**: not into itself; neither request already merged. Refusing a merged
   *target* is what makes a cycle impossible — every arrow must end at a live request.
3. **Resolve double-voters, then move the rest.** A user may have voted on *both*
   requests. Moving their vote across would violate the unique constraint, and adding the
   two counters together would count one person twice. So the source-side duplicate votes
   are deleted first, then the remaining votes are re-pointed at the survivor. One human,
   one vote.
4. **Move the comments** — no uniqueness rule applies, so they all move.
5. **Recompute both counters from the underlying rows**, not by adding the old counters,
   which would be wrong after step 3.
6. **Re-point anything already merged into the source.** A survivor can later be merged
   onward (1→2, then 2→3), and the earlier duplicate has to follow, or it would point at
   a request that is itself retired and a visitor would land on a second dead end. The
   invariant is that `merged_into_id` always resolves to a live request **in one hop**,
   and `test_no_merged_request_ever_points_at_another_merged_request` asserts it over the
   whole table.
7. **Mark the source** `merged_into_id = target`. It is now hidden from the board,
   excluded from statistics, and rejects votes, comments and edits with `409`.

**Voting and commenting take the same row lock.** Both check "is this request merged?"
and then insert, and without a lock held across that gap a merge committing in between
strands the new row on a retired request — invisible on the board, and impossible for the
user to withdraw. `request_service.get_request_for_update` takes the lock before the
check; because it only ever locks one row, it cannot deadlock against the merge's ordered
two-row lock. `api/tests/test_merge_concurrency.py` races the two operations and asserts
no vote or comment is ever left behind; it fails against the unlocked version.

### 4.4 Error handling — `api/app/errors.py`

Services raise domain errors (`NotFound`, `Forbidden`, `Conflict`, `BadRequest`) rather
than returning error tuples, so business rules read as plain statements. One set of
exception handlers turns those — and Pydantic's validation failures — into a single
envelope, so the frontend has exactly one shape to parse and can show the server's own
message. Field-level `422` details are rendered inline against the fields the server
actually rejected, which means the rules shown to the user are the rules enforced.

---

## 5. Scope: what is complete, partial and deferred

### Complete

| Area | Notes |
|---|---|
| Authentication + two roles | Register, login, logout, `/me`; httpOnly cookie session |
| Browse with search, filter, sort, pagination | URL-driven state; three sort orders |
| Submit and view request detail | Server-side validation with inline field errors |
| Vote / un-vote | Idempotent, concurrency-safe, optimistic in the UI |
| Comments with vote and comment counts | Counts maintained transactionally |
| Status model | All five statuses, admin-only transitions |
| Official response | Admin writes it; displayed distinctly from user comments |
| Merge duplicates | One transaction, preserves activity, de-duplicates voters |
| Usage statistics | Five aggregates plus a most-requested list |
| Migrations | Alembic; the same migrations run in tests |
| Docker local setup | `docker compose up` from a clean clone, health-checked, seeded |
| Tests | 56 backend + 16 frontend, organised around the business rules |
| API docs | OpenAPI at `/docs`, generated from the validating schemas |

### Partial — works, with a stated boundary

- **Editing a request** covers title and description only, and is owner-or-admin. There
  is no edit history and no "edited" marker.
- **"Review submitted requests"** is served by the board, not by a dedicated moderation
  queue: an administrator filters to *Under Review* and acts on each one from its detail
  page. That satisfies the requirement with screens that already exist, and it is an
  interpretation rather than an omission — a purpose-built queue with bulk actions and an
  assignee is what growing triage volume would justify.
- **Pagination** is offset-based. Correct and adequate here; it drifts if rows are
  inserted while a user pages, and deep offsets get slow. Cursor pagination is the fix.
- **Comments are returned in full.** `GET /api/requests/{id}/comments` takes no page or
  limit parameter, so a request with a thousand comments returns a thousand (§6.5). Honest
  at seed scale; the fix is the same cursor pagination the board wants.
- **Search** is `ILIKE` substring matching — no relevance ranking, no index usage (§2.6).
- **Statistics** are computed live on each request. Fine at this size; they would need
  caching or a rollup table well before they became slow.
- **Merging is one-way.** A survivor can be merged onward and earlier duplicates follow
  it (§4.3), but there is no un-merge: splitting a request back out would need the
  original ownership of each vote and comment, which is not recorded.
- **Frontend tests** cover the highest-risk component (the optimistic vote toggle), the
  filter controls, and a shell smoke test that renders the app through its routes to catch
  wiring mistakes. They are not per-page behavioural tests: the backend carries the
  business risk, and the coverage is weighted that way on purpose.

### Deferred deliberately — not attempted

Each of these was a conscious trade against the timebox, not an oversight:

| Not built | Why it was cut |
|---|---|
| Real-time updates (WebSocket/SSE) | Substantial infrastructure; polling and invalidation are sufficient at this scale |
| Email / background notifications | Needs a queue, a worker and a mail provider — a project of its own |
| Redis or any caching layer | Nothing here is slow enough to justify a cache and its invalidation bugs |
| Audit log for admin actions | Genuinely valuable (see §7); a table plus a write on every admin action |
| Rate limiting | Belongs at the edge (reverse proxy / API gateway) more than in the app |
| Refresh-token rotation, password reset, email verification | Real auth surface, well beyond a slice |
| Full-text search with ranking | §2.6 |
| Cursor pagination | Offset is correct at this size |
| Tags / categories, attachments, rich text | Product scope, not architectural depth |
| Deleting a request; editing or deleting a comment | Needs a moderation policy before it needs code: soft delete or hard, who may remove another person's words, and what happens to the denormalised counters. Not an afternoon's work, and the wrong thing to guess at |
| A "my requests" or profile view | The board filters on `q`, `status` and `sort` only — there is no author filter, so a user finds their own submissions by searching for them. A `?author=me` filter is small; a profile page is product scope |
| End-to-end (Playwright) tests | The business rules are better tested at the API level; one E2E happy path is the next increment |
| CI pipeline, metrics, tracing | §7 |
| Following a request / notification preferences | "Follow progress" is served by the status model and the board |

---

## 6. Known risks and limitations

Written plainly, because knowing where the edges are matters more than pretending there
are none.

1. **Sessions cannot be revoked before expiry.** Stateless JWTs. A stolen cookie is valid
   until it expires, and "sign out everywhere" is not possible. Fix: a sessions table
   (§7).
2. **CSRF defence rests on `SameSite=Lax`.** That covers the state-changing verbs used
   here and is a real protection, but production should add a double-submit CSRF token,
   since `Lax` is a same-site policy rather than a per-request proof of intent.
3. **The denormalised counters are only as good as the discipline around them.** Any
   future code path that inserts a vote without going through `vote_service` will drift.
   A reconciliation job — or moving the counters into a trigger — removes the class of bug
   entirely.
4. **A merge cannot be undone** through the API. It moves other people's votes and
   comments, and the source request keeps no record of which of them were originally its
   own, so reversing it would need an audit trail that is not built (§7).
5. **No pagination on comments.** A request with a thousand comments returns all of them
   in one response.
6. **Statistics are recomputed on every call** and are admin-only, so the cost is bounded
   by how many admins refresh the page — but it is `COUNT(*)` over the whole table.
7. **`vote_count` could in principle drift below the true value** if a delete path is ever
   added that bypasses the service. The decrement is guarded (`WHERE vote_count > 0`) so it
   cannot go negative, but negative-proof is not the same as correct.
8. **Passwords require only 8 characters** and there is no breach-list check or login
   throttling. Brute-force protection is delegated to rate limiting that is not built.
9. **The seed's demo password is public.** That is correct for a review environment and
   completely wrong for anything reachable from the internet.
10. **No observability.** No structured logs, metrics or traces; diagnosis today means
    reading container output.

---

## 7. Next production steps

Ordered by what would actually be done first.

1. **Server-side sessions** — a `sessions` table keyed by an opaque token, so sessions
   can be revoked and "sign out everywhere" works. Removes risk 1, and lets §6.2's CSRF
   token hang off the same record.
2. **CI pipeline** — run `pytest`, `vitest`, `tsc --noEmit` and a lint pass on every
   pull request against a Postgres service container. Cheap, and it is what keeps
   everything else in this list honest.
3. **Structured logging with a request id**, then metrics (request rate, latency, error
   rate by endpoint) and tracing around the database. Being able to answer "what happened
   to this request?" precedes every performance decision.
4. **Audit log** — an append-only table recording who changed a status, published a
   response or merged a request, and when. The brief lists it as optional; in a product
   where administrators act on other people's contributions it is close to mandatory.
5. **Rate limiting at the edge** on authentication and write endpoints, plus a login
   attempt counter. Closes risk 8.
6. **Postgres full-text search** — a generated `tsvector` column with a GIN index,
   `websearch_to_tsquery`, and `ts_rank` for ordering. Replaces §2.6 when the board grows.
7. **Cursor pagination** for the board and comments.
8. **Counter reconciliation** — a periodic job asserting `vote_count` equals the row
   count, alerting on drift. Cheap insurance for the §2.5 trade-off.
9. **Deployment** — build the web app to static files behind a CDN, run the API as a
   container behind a load balancer with `alembic upgrade head` as a release step (not on
   container start, so concurrent replicas cannot race), and Postgres as a managed
   instance with backups and a read replica when reporting justifies one.
10. **One end-to-end happy path** in Playwright — sign in, submit, vote, comment, admin
    changes status — as a smoke test against a real deployment.

---

## 8. Notes for the discussion topics

Short answers to the areas the brief flags, so they are on the record.

**Frontend architecture.** Layered as `pages → components → hooks → typed client`. Pages
fetch and compose; components are presentational and take props, which is what makes
`VoteButton` unit-testable. All server state goes through React Query with query keys in
one place; all API access goes through one client that parses one error envelope.

**Transaction boundaries.** One HTTP request maps to one session and one transaction.
Services commit explicitly on success; anything unhandled rolls the whole request back.
The interesting boundaries are voting (insert + counter) and merging (six statements, one
commit).

**Race conditions.** Handled in four places: the unique index on votes, the atomic
counter increment, `FOR UPDATE` with deterministic lock ordering in the merge, and the
same row lock taken by voting and commenting so a write cannot land on a request that is
being merged away. Each is covered by a test that fails when the mechanism is removed —
both concurrency suites were checked against the broken versions rather than assumed.

**Caching.** None today, deliberately. The first thing worth caching is the statistics
endpoint, then the first page of the board for anonymous visitors — both are read-heavy
and tolerate staleness. Neither is a bottleneck yet, and a cache added before it is
needed is mostly a new source of stale-data bugs.

**Scaling bottlenecks, in the order they would appear.** (1) `ILIKE '%term%'` cannot use
an index — full scans as the table grows. (2) Deep offset pagination. (3) Hot-row write
contention on a viral request's counter — every vote locks the same row; the fix is
sharded counters or a periodic rollup. (4) Live `COUNT(*)` statistics. Notably, the vote
*read* path scales fine precisely because of the denormalised counter.

**Security posture.** Passwords bcrypt-hashed with per-password salts; session in an
httpOnly cookie; role never client-supplied; authorization server-side on every route;
Pydantic validation at the edge; SQLAlchemy parameterises all queries, so there is no
string-built SQL; login messages identical for unknown-email and wrong-password so the
endpoint cannot enumerate accounts; author identity exposed publicly but email addresses
never; CORS restricted to an explicit origin list because credentials are enabled. Gaps
are risks 1, 2 and 8.

**Accessibility.** The vote control is a real `<button>` with `aria-pressed` and an
accessible name that includes the request title and current count; status is conveyed by
text as well as colour; every input has a `<label>`; focus is visible everywhere; there is
a skip link; loading regions are marked `aria-busy` and errors `role="alert"`; the
skeleton shimmer respects `prefers-reduced-motion`. Not done: a full screen-reader pass
and keyboard-trap testing on the merge confirmation.

**Performance.** Indexed sorts, one query per list page plus one for the caller's votes
(no N+1), `placeholderData` so changing a filter does not blank the screen, debounced
search, and a ~73 kB gzipped bundle with no UI framework.

---

## 9. On the timebox

The brief sets 6–8 hours and says respecting it is part of the exercise. This submission
was built to that: the user journey is complete but thin, three areas are deep, and §5
records everything traded away. The work was scoped so that every mechanism here can be
explained and defended — which is why there is no caching layer, no WebSocket and no
background worker, and why the concurrency test was checked against a broken
implementation rather than assumed to work.
