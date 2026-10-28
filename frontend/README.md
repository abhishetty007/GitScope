# GitScope frontend

GitScope uses the Next.js App Router for server-rendered public pages and keeps
the Flask API as a separate service.

See the root [deployment checklist](../DEPLOYMENT.md) for provider setup,
runtime variable purposes, and current free-tier constraints.

## Development

1. Start the Flask API from `backend`.
2. Create a local PostgreSQL database, then copy `.env.example` to `.env.local`.
   Set `GITSCOPE_API_BASE_URL`, `DATABASE_URL`, and the Auth0 values.
3. Configure an Auth0 Regular Web Application with callback
   `http://localhost:3000/auth/callback` and logout URL `http://localhost:3000`.
   Configure its GitHub social connection for identity-only access; do not request
   repository scopes. GitScope does not retain GitHub connection tokens.
4. Run `npm install`, `npm run db:migrate:dev -- --name phase5_initial`, then
   `npm run dev`.

Auth0 session and transaction cookies are managed server-side by its Next.js SDK.
Session cookies are HttpOnly and SameSite=Lax; Secure is enabled in production.
The SDK's browser access-token endpoint is disabled. Protected data APIs are
`/api/saved-analyses` and `/api/tracked-repositories`; public analysis pages and
the existing Flask analytics API remain public.

Saved snapshots contain repository display metadata, category scores/check
summaries, and activity aggregates only. Raw file contents, GitHub responses,
commit lists, contributor lists, and OAuth tokens are not persisted.

## Production configuration

`compose.yaml` is the local verification configuration and continues to run its
private PostgreSQL container. For production, combine it with
`compose.production.yaml`: the production overlay removes the local PostgreSQL
service and volume and expects an externally managed PostgreSQL database. It
also sets `GITSCOPE_ENV=production`, disables Flask CORS, and removes Flask's
host-published port. Keep Flask reachable only over the private Compose network
from Next.js; the browser calls Next.js and never calls Flask directly.

Set `GITSCOPE_SITE_URL` before building to the deployed frontend HTTPS origin.
Production `APP_BASE_URL` must also use HTTPS; local HTTP URLs remain supported.
The Auth0 SDK requires `AUTH0_SECRET` to be exactly 32 bytes encoded as 64
hexadecimal characters. At runtime provide a managed PostgreSQL
`DATABASE_URL` with `sslmode=require` (or a stronger provider-supported TLS
mode),
`GITSCOPE_API_BASE_URL`, `APP_BASE_URL`, `AUTH0_DOMAIN`, `AUTH0_CLIENT_ID`,
`AUTH0_CLIENT_SECRET`, and `AUTH0_SECRET`. `AUTH0_ISSUER` is optional; when
omitted, GitScope derives it from `AUTH0_DOMAIN`. The API URL is read
server-side and is not exposed as browser configuration. Do not put credentials
in build arguments or images. Supply secrets through the deployment runtime
configuration, not the local `.env.example` defaults.

The Prisma client uses one lazy connection pool per Next.js process. Configure
`GITSCOPE_DB_POOL_MAX` (default `5`, allowed `1`–`50`) and
`GITSCOPE_DB_CONNECTION_TIMEOUT_MS` (default `5000`, allowed `100`–`30000`)
for the deployment. Size the pool against the maximum number of app instances
and the managed database's connection limit, leaving room for migrations and
operations. The current defaults are conservative starting points, not a
provider capacity guarantee.

### Distributed GitHub API rate limiting

Every GitHub-backed `GET /api/github/*` endpoint is guarded by a PostgreSQL
fixed-window limiter. Counters are incremented atomically in the shared
`gitscope_rate_limit_windows` table, so separate Gunicorn workers and Render
instances enforce the same service-wide windows. These calls originate from
Next.js server code on Vercel, so Render sees Vercel's outbound connection IP,
not the browser user. We deliberately use an aggregate service budget instead
of inventing per-user identity from forwarding headers. The limiter uses the
Neon/PostgreSQL database already required by the application; it adds no Redis
or paid runtime service. It does add a small transactional database write for
each guarded request. The PostgreSQL pool allows at most two connections per
backend worker; size `GUNICORN_WORKERS` and Render instances against Neon limits.

| Operation | Inbound limit | SDK requests / maximum wire requests per request |
| --- | ---: | ---: |
| Repository engineering analysis | 5/min | 123 / 246 |
| Repository evidence | 10/min | 102 / 204 |
| User analytics | 30/min | 10 / 20 |
| User profile | Shared 60/min metadata bucket | 1 / 2 |
| User repository listing | Shared 60/min metadata bucket | 10 / 20 |
| Repository detail or identity | Shared 60/min metadata bucket | 1 / 2 |
| Repository commits or contributors | Shared 60/min metadata bucket | 11 / 22 each |

Local Compose passes its PostgreSQL URL to Flask. For Render + Neon:

1. Deploy the additive Prisma migration with the application database owner
   before deploying the backend code.
2. In Neon, create a separate login role named `gitscope_rate_limiter` and set
   its generated password in the Neon console. As the database owner, grant it
   only the permissions needed for the counter table (replace the database
   identifier if your Neon database has a different name):

   ```sql
   GRANT CONNECT ON DATABASE gitscope TO gitscope_rate_limiter;
   GRANT USAGE ON SCHEMA public TO gitscope_rate_limiter;
   GRANT SELECT, INSERT, UPDATE, DELETE
     ON TABLE public.gitscope_rate_limit_windows TO gitscope_rate_limiter;
   ```

   Do not grant schema/table creation or application-data access to this role.
   After grants, verify effective privileges as a database owner (the checks
   below include privileges inherited through role membership):

   ```sql
   SELECT
     has_database_privilege('gitscope_rate_limiter', 'gitscope', 'CONNECT') AS can_connect,
     has_schema_privilege('gitscope_rate_limiter', 'public', 'USAGE') AS can_use_schema,
     has_table_privilege('gitscope_rate_limiter', 'public.gitscope_rate_limit_windows', 'SELECT') AS can_select,
     has_table_privilege('gitscope_rate_limiter', 'public.gitscope_rate_limit_windows', 'INSERT') AS can_insert,
     has_table_privilege('gitscope_rate_limiter', 'public.gitscope_rate_limit_windows', 'UPDATE') AS can_update,
     has_table_privilege('gitscope_rate_limiter', 'public.gitscope_rate_limit_windows', 'DELETE') AS can_delete,
     has_table_privilege('gitscope_rate_limiter', 'public.gitscope_rate_limit_windows', 'TRUNCATE') AS can_truncate;
   ```

   The first six results should be true and `can_truncate` false. Also inspect
   Neon role membership/attributes and confirm the role is not a table owner,
   superuser, or member of an application-owner role. Do not grant sequences,
   schema creation, table creation, or TRUNCATE; this migration has no sequence.
   The following owner-side queries expose those attributes and inherited role
   memberships without revealing the role password:

   ```sql
   SELECT rolname, rolsuper, rolcreatedb, rolcreaterole, rolreplication, rolbypassrls
   FROM pg_roles WHERE rolname = 'gitscope_rate_limiter';

   SELECT granted.rolname AS inherited_role
   FROM pg_auth_members m
   JOIN pg_roles granted ON granted.oid = m.roleid
   JOIN pg_roles member ON member.oid = m.member
   WHERE member.rolname = 'gitscope_rate_limiter';

   SELECT c.relname, pg_get_userbyid(c.relowner) AS table_owner
   FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
   WHERE n.nspname = 'public'
     AND c.relname = 'gitscope_rate_limit_windows';
   ```
3. Set these Render backend environment variables (values are supplied in the
   provider dashboard and are never committed):
   - `GITSCOPE_RATE_LIMIT_DATABASE_URL`: Neon pooled PostgreSQL URL for the
     restricted role, with `sslmode=require` or stronger. PgBouncer transaction
     pooling is supported; the client disables server-side prepared statements.
   - `GITSCOPE_GITHUB_METADATA_GLOBAL_LIMIT_PER_MINUTE` is an optional integer
     override for the metadata bucket, bounded at startup.
   - `GITSCOPE_GITHUB_UPSTREAM_BUDGET_PER_HOUR` is required in production and
     bounded by the configured credential class. Recognized user/OAuth bearer
     tokens default to 2,000/hour (maximum 2,500); app, Actions, and unrecognized
     bearer tokens default to 200/hour (maximum 400); unauthenticated access
     defaults to 20/hour (maximum 30). Inspect `/rate_limit` using the same
     credential before staging, account for other consumers, and lower the cap
     when less quota is available. GitHub's response headers remain authoritative.
     See [GitHub REST API rate limits](https://docs.github.com/en/rest/using-the-rest-api/rate-limits-for-the-rest-api).

The upstream budget is charged for each actual outbound GitHub REST request,
not just each inbound GitScope request. A shared PostgreSQL counter also caps
upstream traffic at 300 requests per minute. Repository analysis has no separate
five-starts-per-minute or weighted-workload quota; each upstream request is
already charged against the same minute and hourly counters. Other metadata,
user-analytics, and repository-evidence routes retain their endpoint limits.
All shared upstream counters fail closed. Collection deadlines are at most 55
seconds, and the synchronous GitHub client allows at most one redirect with a
15-second timeout per hop. Analysis HTTP clients use the same one-redirect
maximum. Each analysis bounds file-content concurrency at eight. Concurrent
identical analyses and identical synchronous GitHub GETs are coalesced within
one backend worker process. This is only a duplicate-work optimization; each
leader still uses the shared PostgreSQL limiter, which remains the cross-worker
and cross-instance source of truth. Redirect hops are charged before following.
Failed/cancelled requests are not refunded. No application retry loop is
configured. A database transaction is never held while waiting on GitHub.

Worst-case uncached repository analysis, with current collection bounds, makes
up to 123 SDK requests (246 wire requests if each follows a redirect): one route-level repository visibility check,
one tree request, up to 100 file-content requests, up to 10 commit pages, up to
10 contributor pages, and one workflow-runs request when a GitHub token is
configured. The async collector reuses the route's repository response. Cache
hits lower the actual count; the limiter meters outbound calls, so multiple
Gunicorn workers and Render instances share one counter. Each analysis has at
most eight file fetches in flight. GitHub
documents a 100-request concurrent secondary limit and 900 REST points/minute;
most read requests cost one point, but endpoint exceptions and secondary
controls may vary. Monitor rate-limit response headers after deployment.

The limiter does not read `CF-Connecting-IP`, `X-Forwarded-For`, or any other
caller-supplied IP header. No forwarded-header trust configuration is needed.
This avoids treating Vercel's server egress IP as an individual GitScope user
and prevents header spoofing from changing a limit key. Verify after deployment
by sending repeated requests to each bucket until it returns 429 with
`Retry-After`, then repeat across separate Render instances; the threshold is
shared across the service.

The shared database is fail-closed: if the limiter cannot acquire a connection
or update a counter, guarded GitHub routes return a generic 503 with
`Retry-After: 5`; they do not proceed to GitHub. Application and shared
upstream-budget limits return 429 with a retry interval, which the frontend
preserves for its manual retry message.
GitHub upstream rate limits remain distinct and return a safe GitHub-specific
429 with the upstream retry interval when supplied. Neither the upstream error
text nor limiter connection details are returned or logged.

Vercel's firewall can additionally limit requests that reach the Vercel app,
but it does not protect a separately reachable Render API origin from direct
calls. Vercel's WAF rate limiting has included request volume and then usage
pricing; it is supplementary and not required for the PostgreSQL mechanism.
Render's DDoS mitigation is not an application quota limiter. Neon free-tier
capacity and account quota are account-specific and must be checked in the
owner's console; this design uses the existing database but does not guarantee
that a free plan has enough compute/connections for production traffic.

For a staging verification pass, keep the following separate from production:

1. Deploy only the additive `20261014000000_shared_rate_limit` migration using
   the normal migration-owner URL (`cd frontend; npm run db:migrate:deploy`).
   Do not run it as the restricted limiter role.
2. Connect with the restricted role through the Neon pooled URL and verify the
   TLS connection using the `psql` connection-info command; confirm the displayed connection
   is SSL. The runtime also rejects missing, duplicate, unsupported, or
   non-TLS `sslmode` values before the pool opens.
3. Run `backend/tests/test_shared_rate_limit.py` against a dedicated isolated
   staging/test database by setting `GITSCOPE_RATE_LIMIT_TEST_DATABASE_URL` to
   the restricted-role URL. The integration test uses unique test buckets and
   removes only those rows. It verifies sharing across independent processes
   and pools, not across separately deployed instances.
4. To verify multiple instances, use two staging instance URLs and send requests
   against one shared test bucket/route until the global limit is reached;
   confirm the combined accepted count does not exceed the cap and `Retry-After`
   is present. Use a disposable test deployment/database, never production.
5. In staging only, temporarily make the limiter connection unavailable and
   confirm a guarded route returns generic 503 with `Retry-After: 5` without
   issuing GitHub traffic; restore the URL and verify recovery after restart.

Migration state, effective Neon role grants, a real pooled TLS handshake,
cross-instance behavior, and outage/recovery remain unverified until these
staging checks are performed. Do not interpret local tests as evidence for
those provider-managed settings.

GitHub collection is also bounded by `GITSCOPE_ANALYSIS_TIMEOUT_SECONDS`
(default `45`, maximum `55`), `GITSCOPE_GITHUB_MAX_PAGES` (default `10`), and
`GITSCOPE_GITHUB_MAX_FILE_FETCHES` (default `100`). User repository lists,
commits, and contributors each use at most the configured number of pages.
Each SDK-level request follows at most one redirect (so it makes at most two
wire requests); redirect hops are charged as separate upstream calls.
The in-memory GitHub response/analysis caches and in-flight deduplication remain
per worker, so different instances can repeat calls after a cache miss; the
shared upstream counter charges each actual call. The budget is a conservative application ceiling, not
a guarantee that GitHub will never apply a secondary limit or that no other
application uses the token.

Authenticated JSON mutations reject bodies larger than 4 KiB before JSON
parsing. `GET /api/health` is the liveness check and does not depend on external
services. `GET /api/ready` performs a PostgreSQL query with a one-second bound;
the production Compose frontend healthcheck uses readiness. GitHub is not a
readiness dependency. The backend allows 60 seconds for a worker request and 30
seconds for graceful worker shutdown; Compose grants the container 35 seconds
to stop.

The frontend Dockerfile's default target is the production Next.js runner.
Build `--target migrator` only for the one-off migration service; migrations
remain outside normal frontend startup.

Build with `npm run build`. For a local production smoke test, `npm start`
loads the frontend environment files and runs the generated standalone server;
`npm run preview` uses the same entry point. The container runner starts the
standalone `server.js` directly with runtime environment variables. Because
public analytics pages are server-rendered, deploy the frontend to a Node-capable
Next.js host; static-only hosting is not sufficient. Configure the Flask API's
production CORS policy to remain empty; the browser does not call Flask
directly.

Run `prisma migrate deploy` once as a controlled release step before deploying
the new app version. With Compose, use
`docker compose -f compose.yaml -f compose.production.yaml run --rm migrator`;
the `release`-profile migration service is a one-off task and is never started
by the web service. The migration image contains the Prisma CLI, config, schema,
and checked-in migrations, and receives database credentials only at runtime.
Set optional `DIRECT_URL` only when the provider uses a separate direct/session
endpoint for migrations; otherwise migrations use `DATABASE_URL`. Both
production URLs must enforce TLS. Never run `prisma db push` or migrations from
application startup.

Automated backups and point-in-time recovery belong to the managed PostgreSQL
provider, not application code. Set retention and recovery objectives with the
provider and practice restoring to an isolated database. Application rollback
must account for schema compatibility: use backward-compatible expand/contract
migrations and do not assume a code rollback reverses a database migration.
`npm run test` runs the frontend's Node-based auth/authorization/snapshot/schema
tests.

The sitemap intentionally lists only the landing page. User and repository
analytics pages are shareable but currently emit `noindex` metadata, avoiding an
unbounded index of arbitrary GitHub entities.

Tracked repositories and saved analyses currently cover public repositories
only. Private GitHub access, GitHub App installation, teams/roles, and distributed
mutation rate limiting are deferred. Per-process mutation limits are only a
backstop; configure the production hosting edge for distributed rate limiting.
