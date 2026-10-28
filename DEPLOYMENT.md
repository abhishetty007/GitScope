# GitScope beta deployment checklist

This guide describes the current Next.js, Flask, PostgreSQL, Auth0, and GitHub
deployment shape. It contains variable names and purposes only. Enter secret
values in provider dashboards, never in Git, Docker build arguments, or build
logs. No provider account or deployment has been configured or verified here.

## Free hosting assessment

The documented combination is Vercel for Next.js, Render for Flask, Neon for
PostgreSQL, and Auth0 for sign-in. Default provider subdomains are available;
Vercel assigns a `vercel.app` address and Render assigns an `onrender.com`
address, both with provider-managed HTTPS.

This combination is suitable for a preview with a few testers, with material
availability limits:

- Render says its Free instances are for previewing and hobby projects, not
  production. Free web services sleep after 15 minutes without inbound traffic
  and take about a minute to wake. Their filesystem is ephemeral, they have no
  persistent disk, and free Render PostgreSQL databases expire after 30 days.
  Each workspace also has 750 Free instance-hours per calendar month across its
  Free services. Outbound bandwidth and build-pipeline usage have workspace
  allowances; check the dashboard because high service-initiated public traffic
  can also suspend a Free web service.
  Use Neon for the database, not Render's free database. Review Render's
  [current free-instance limits](https://render.com/docs/free) before inviting
  testers.
- Vercel Hobby is free, but limited to non-commercial personal use. Current
  included usage includes 1 million function invocations, 4 active CPU-hours,
  and 360 GB-hours of provisioned memory. With Fluid Compute enabled, Hobby
  functions have a 300-second default and maximum duration. Without Fluid
  Compute, the default is 10 seconds and the maximum is 60 seconds. New projects
  enable Fluid Compute by default, but verify the setting in the project
  dashboard; no Vercel project exists to inspect yet. Exceeded free allowances
  may pause features until they reset. Confirm that the plan's terms and usage
  fit the beta before deployment in the [Hobby plan](https://vercel.com/docs/plans/hobby),
  [function limits](https://vercel.com/docs/functions/limitations), and
  [Fluid Compute settings](https://vercel.com/docs/fluid-compute).
- As of 2026-10-25, Neon's Free plan advertises 1 GB storage per project, 100
  CU-hours per project per month, autoscaling up to 2 CU, and a 6-hour
  instant-restore window. Compute may scale to zero. Check the account dashboard
  for current quotas and recovery options; the restore window is not a verified
  backup or disaster-recovery configuration. See [Neon's current Free plan
  details](https://neon.com/blog/neon-free-plan-1-gb-per-project).
- Auth0's pricing page currently lists a Free plan up to 25,000 monthly active
  users. Check the tenant's applicable features and quota in the
  [Auth0 dashboard](https://auth0.com/pricing).

Free tiers can support a preview, but Render's stated production restriction
means the stack cannot be called production-ready while the backend remains on
Render Free. A sleeping backend can also add about a minute to the first
analysis request. Do not add a keep-alive job to work around the sleep policy.

## Provider setup checklist

### 0. Select a reviewed staging source

The local `main` branch is four commits ahead of `origin/main` and contains
uncommitted and untracked work. Do not connect automatic deployment to this
working tree or push the current dirty branch. First review the diff and select
the exact commits and files intended for staging. Prepare a clean, dedicated
staging branch or reviewed build artifact through the normal repository review
process, then run the required checks on that source. Exclude local cache files
and environment files; keep the verified backup separate from deployment
artifacts. No source has been committed, pushed, or deployed as part of this
audit.

### 1. Prepare the PostgreSQL database

- Create a persistent PostgreSQL project in Neon. Select a region close to the
  application services where possible.
- Create a restricted runtime role for the frontend Prisma client and use it
  for `DATABASE_URL`. Create a separate migration-owner role for `DIRECT_URL`;
  provide that URL only to the controlled migration step. Do not run the web
  application as the migration owner.
- Apply the checked-in Prisma migrations once, from the `frontend` directory,
  with `DIRECT_URL` set to the migration-owner connection:
  `npm run db:migrate:deploy`.
- Create a separate `gitscope_rate_limiter` login with access only to the shared
  rate-limit table. Follow the SQL grants and verification queries in
  [frontend/README.md](frontend/README.md#distributed-github-api-rate-limiting).
- Use TLS for both the application and limiter database URLs. Never give the
  limiter role schema creation, table creation, or application-data access.
- Verify effective grants, role membership, TLS connectivity, available
  connections, and recovery settings in the Neon console. These account-side
  checks have not been performed.

### 2. Deploy the Flask API

- Create a Render Web Service from the `backend` directory and select its
  Dockerfile. The container binds to `0.0.0.0:$PORT`; configure `/api/health` as
  the provider health-check path.
- Keep production CORS origins empty. The Next.js server calls Flask; browsers
  should not call the Flask origin directly.
- Configure the GitHub token and restricted PostgreSQL limiter URL only as
  backend runtime secrets. Choose the upstream request budget from the token's
  observed `/rate_limit` quota after accounting for other users of that token.
- Record the assigned HTTPS API origin for Next.js configuration. Do not use a
  public HTTP URL.
- Verify health, readiness, rate-limit responses, logs, and recovery from a
  limiter outage in a separate staging deployment and database.

### 3. Deploy the Next.js frontend

- Import the repository into Vercel and set the project root to `frontend`.
- Use `npm ci` for installation and `npm run build` for the production build.
  The package scripts generate Prisma Client before the build. Select a Vercel
  Node.js runtime that satisfies the package's `>=20.9.0` engine requirement;
  the Docker images use Node 22. The application requires a Node-capable
  Next.js host; it is not a static export.
- Set `GITSCOPE_SITE_URL` to the actual assigned HTTPS frontend origin both at
  build time and runtime. It is used for canonical metadata and the sitemap.
- Set `GITSCOPE_API_BASE_URL` to the actual assigned HTTPS Flask API origin.
- Keep the database URL, Auth0 client secret, Auth0 application secret, and
  GitHub token out of build-time configuration. They are runtime-only values.
- Verify the production build, home page, generated `robots.txt` and
  `sitemap.xml`, saved-analysis APIs, and `/api/ready` after deployment.

### 4. Configure Auth0

Create a Regular Web Application for staging. In its Application URIs, set the
Allowed Callback URL to the exact staging frontend origin followed by
`/auth/callback`, and set both Allowed Logout URLs and Allowed Web Origins to
the exact frontend origin. Set `APP_BASE_URL` to that same stable HTTPS origin;
the SDK uses `/auth/login`, `/auth/callback`, and `/auth/logout`. Register each
preview hostname separately if preview deployments need sign-in; a fixed
`APP_BASE_URL` cannot represent multiple origins. Configure the Auth0 tenant
domain and client credentials as frontend runtime variables. Do not expose them
with a `NEXT_PUBLIC_` prefix. These URLs cannot be finalized until Vercel and
Render assign the staging origins.

The Auth0 GitHub social connection is for identity-only sign-in and is separate
from the backend `GITHUB_TOKEN`; it does not provide a GitHub API token to Flask.

### 5. Configure GitHub REST access

The backend uses public GitHub REST reads. `GITHUB_TOKEN` is optional and, when
present, is sent as a bearer credential by both backend collectors. The code
does not exchange tokens or use a GitHub App installation flow. Without this
variable the API calls are unauthenticated. Keep any credential in the backend
runtime secret store only. Do not use a write-capable or private-repository
credential for a public-repository staging preview. The optional workflow-runs
read uses `GET /repos/{owner}/{repo}/actions/runs`; public resources can be read
without authentication, while a fine-grained token for private data requires
Actions read permission. See [GitHub's workflow-runs permissions](https://docs.github.com/en/rest/actions/workflow-runs#list-workflow-runs-for-a-repository).

Inspect `GET https://api.github.com/rate_limit` with the same authentication
mode and credential that Render will use. Set staging
`GITSCOPE_GITHUB_UPSTREAM_BUDGET_PER_HOUR` below the current remaining core
quota after reserving capacity for other workloads that use that credential.
The backend supplies conservative defaults and bounds by bearer-token class:
recognized user or OAuth tokens default to 2,000/hour and are capped at
2,500/hour; app, Actions, or unrecognized bearer credentials default to
200/hour and are capped at 400/hour; unauthenticated requests default to
20/hour and are capped at 30/hour. The authenticated-user maximum reserves at
least half of the typical 5,000/hour quota, while the lower unrecognized-token
profile accommodates credentials with smaller quotas, including Actions
tokens. These defaults do not account for traffic from other applications
sharing the credential; lower the configured cap when `/rate_limit` shows less
available headroom. Response `X-RateLimit-*`, `Retry-After`, and reset headers
remain authoritative, and primary and secondary GitHub limits are returned
separately from GitScope capacity errors. Do not treat any internal cap as
unlimited API access. See [GitHub's REST rate-limit documentation](https://docs.github.com/en/rest/using-the-rest-api/rate-limits-for-the-rest-api).

### 6. Run release and smoke checks

- Apply migrations before deploying code that depends on them. Do not run
  migrations from application startup or as the restricted limiter role.
- Confirm that `GET /api/health` is independent of GitHub and PostgreSQL, and
  that frontend `GET /api/ready` checks the database with its short timeout.
- Exercise a public profile, a public repository analysis, an invalid or
  inaccessible repository, and a rate-limited request in staging.
- Verify Auth0 login, callback, logout, saved-analysis ownership, and tracked
  repository ownership with a test account.
- Confirm the GitHub quota from live rate-limit headers, global request limits,
  Neon usage, provider logs, database recovery, and provider usage controls.
- Do not treat the successful local build or unit tests as evidence that
  provider networking, TLS, Auth0 callbacks, database grants, or cross-instance
  rate limiting work.

## Runtime environment variables

Set only the names needed by each service. Values belong in provider runtime
configuration and are intentionally omitted here.

| Service | Variable | Purpose |
| --- | --- | --- |
| Frontend, backend, and migration job | `GITSCOPE_ENV` | Enables production configuration and TLS validation in both services and the migration URL selector. |
| Frontend | `NODE_ENV` | Set by Next.js/Vercel or the frontend container; production mode enables secure Auth0 cookies and production CSP. |
| Frontend | `GITSCOPE_SITE_URL` | Actual public frontend origin for canonical metadata and sitemap; set during build and at runtime. |
| Frontend | `APP_BASE_URL` | Public frontend origin used by Auth0 session and callback handling. |
| Frontend | `GITSCOPE_API_BASE_URL` | Flask API origin; public deployments must use HTTPS. |
| Frontend runtime and local migration fallback | `DATABASE_URL` | PostgreSQL URL used by Prisma and frontend data access; use the restricted runtime role and enforce TLS in production. |
| Controlled frontend migration job | `DIRECT_URL` | TLS URL for the separate migration-owner role; set it for staging/production role separation and do not provide it to the web runtime. |
| Frontend | `GITSCOPE_DB_POOL_MAX` | Bounded maximum PostgreSQL connections per Next.js process. |
| Frontend | `GITSCOPE_DB_CONNECTION_TIMEOUT_MS` | Bounded connection timeout for the frontend pool. |
| Frontend | `AUTH0_DOMAIN` | Auth0 tenant domain. |
| Frontend | `AUTH0_CLIENT_ID` | Auth0 application identifier. |
| Frontend | `AUTH0_CLIENT_SECRET` | Auth0 application secret; runtime secret only. |
| Frontend | `AUTH0_SECRET` | 32-byte hex secret used to encrypt the Auth0 session cookie. |
| Frontend | `AUTH0_ISSUER` | Optional expected Auth0 issuer; otherwise derived from the tenant domain. |
| Backend and frontend container | `PORT` | Render supplies the backend port; the frontend Docker image defaults to port 3000. Vercel manages its own runtime port. |
| Frontend container | `HOSTNAME` | Set by the frontend Dockerfile so the standalone Next.js server binds on all interfaces; not a Vercel dashboard setting. |
| Backend | `GITHUB_TOKEN` | Optional server-side GitHub REST credential; runtime secret only. |
| Backend | `GITSCOPE_RATE_LIMIT_DATABASE_URL` | TLS PostgreSQL URL for the restricted shared-limiter role. |
| Backend | `GITSCOPE_GITHUB_UPSTREAM_BUDGET_PER_HOUR` | Required in production; bounded by the configured bearer-token class and selected below the credential's available quota. |
| Backend | `GITSCOPE_GITHUB_METADATA_GLOBAL_LIMIT_PER_MINUTE` | Optional bounded override for metadata route capacity. |
| Backend | `GITSCOPE_GITHUB_MAX_PAGES` | Bounded page count for GitHub collection. |
| Backend | `GITSCOPE_GITHUB_MAX_FILE_FETCHES` | Bounded number of repository files collected per analysis. |
| Backend | `GITSCOPE_ANALYSIS_TIMEOUT_SECONDS` | Bounded analysis collection deadline. |
| Backend | `GITSCOPE_CORS_ORIGINS` | Must be empty in production. |
| Backend | `GUNICORN_WORKERS` | Number of backend worker processes; size against database connections and provider capacity. |
| Backend | `GUNICORN_TIMEOUT` | Optional Gunicorn worker timeout; the Docker default is 60 seconds. |
| Backend | `GUNICORN_GRACEFUL_TIMEOUT` | Optional Gunicorn graceful shutdown timeout; the Docker default is 30 seconds. |
| Backend | `FLASK_DEBUG` | Must not enable debug mode in production. |
| Backend test only | `GITSCOPE_RATE_LIMIT_TEST_DATABASE_URL` | Restricted-role URL for an isolated, migrated PostgreSQL integration-test database; never configure on a deployed service. |
| Local Compose only | `POSTGRES_DB` | Local PostgreSQL database name. |
| Local Compose only | `POSTGRES_USER` | Local PostgreSQL user. |
| Local Compose only | `POSTGRES_PASSWORD` | Local PostgreSQL password; do not reuse a staging or production credential. |
| Local Compose only | `FRONTEND_PORT` | Host port mapped to the local frontend container. |
| Local Compose only | `BACKEND_PORT` | Loopback host port mapped to the local backend container. |

`GITSCOPE_ENV` is required on both staging services and must select production
validation. `GUNICORN_TIMEOUT`, `GUNICORN_GRACEFUL_TIMEOUT`, and `PORT` are
container/platform settings; they do not replace the application-level GitHub
collection deadline. The repository does not define a separate Prisma runtime
role grant script, so provision and verify the `DATABASE_URL` role's required
application-table permissions in Neon. Keep migration-owner credentials in the
one-off migration environment, not the long-running Vercel app.

## Repository entry points and deployment contract

- The frontend project root is `frontend`. Its `package.json` has `npm run
  build` (`prebuild` first runs `prisma generate`), `npm test`, `npm run lint`,
  `npm run db:validate`, and `npm run db:migrate:deploy`. It is a server-rendered
  Next.js app, not a static export. Its package start command is `npm start`
  (`node start-standalone.mjs`). The frontend Dockerfile uses Node 22 and a
  standalone Next.js server.
- The backend project root is `backend`. Its Dockerfile uses Python 3.13 and
  starts `app:app` under Gunicorn, binding to `0.0.0.0:$PORT`; Render must use
  this Dockerfile and `/api/health` as its liveness check.
- `compose.yaml` is for local verification and includes local PostgreSQL.
  `compose.production.yaml` removes that database, uses TLS URLs, and defines a
  `migrator` release profile. The repository has no `vercel.json` or
  `render.yaml`; Vercel and Render project settings therefore remain dashboard
  configuration. Render Free does not support one-off jobs, so run migrations
  from a controlled operator/CI environment or a supported paid job, never at
  web-service startup.

## PostgreSQL roles, pooling, and migration safety

Prisma and Flask use the same PostgreSQL database for separate purposes and
credentials. The Next.js Prisma adapter reads and writes application data using
frontend `DATABASE_URL`, which should be a restricted application runtime role.
The controlled migration step uses a separate migration-owner role through
`DIRECT_URL`; the config can fall back to `DATABASE_URL` for convenience, but
staging and production must set `DIRECT_URL` so the web runtime never receives
schema-owner credentials. The Flask service uses only
`GITSCOPE_RATE_LIMIT_DATABASE_URL` for the shared
`gitscope_rate_limit_windows` counters. The restricted limiter role needs
`CONNECT`, schema `USAGE`, and table `SELECT`, `INSERT`, `UPDATE`, and `DELETE`;
it must not own the table or inherit owner privileges. All production
PostgreSQL URLs must use exactly one TLS `sslmode` (`require`, `verify-ca`, or
`verify-full`). The
backend uses a psycopg pool of at most two connections per worker and disables
server-side prepared statements for transaction-pooler compatibility. The
frontend PostgreSQL pool defaults to five connections per process, bounded by
`GITSCOPE_DB_POOL_MAX`, with a bounded connection timeout. Size both pools
against the provider's real connection allowance and the maximum number of
instances/processes; do not multiply the per-process pool value by one and
assume it is the total.

For a staging migration:

1. Create a staging database that is separate from production and the primary
   development database. Confirm the host, database, schema, TLS mode, and role
   before running any command. Capture a recoverable provider backup/branch or
   otherwise verify a restore path first.
2. From `frontend`, run `npx prisma migrate status` to inspect migration state,
   then run `npm run db:migrate:deploy` against the staging database as the
   migration owner. Set `DIRECT_URL` to the migration-owner URL in the
   controlled migration environment. Although the config can fall back to
   `DATABASE_URL`, do not use the runtime role for staging migrations. Use a
   direct/session migration connection where required by the provider. Never
   use the restricted limiter role and never use
   `prisma db push`. If tables already exist without matching Prisma migration
   history, stop: the initial migration creates tables and there is no repository
   baselining procedure. Snapshot and reconcile the schema/history before
   applying any pending migration.
3. For a fresh staging database, the checked-in migrations create the
   application schema (`20261006000000_phase5_initial`) and then add the shared
   limiter table/index (`20261014000000_shared_rate_limit`). Review the SQL and
   migration status before and after applying them. The repo's Compose
   migration service is a one-off Docker target; Vercel app startup does not
   run migrations.
4. After the limiter table exists, apply and verify the restricted-role grants
   from the [frontend database setup](frontend/README.md#distributed-github-api-rate-limiting).
   Point the backend only at that restricted login. Verify effective grants
   and the SSL connection without printing connection strings.
5. Exercise staging, then perform the four PostgreSQL integration tests below
   against a separate test database. Do not run them against production or the
   primary development database.

The shared-rate-limit migration is additive: it creates one counter table, a
positive-count check, and an index; it does not rewrite application rows. The
initial schema migration creates the application tables and foreign keys with
`ON DELETE CASCADE`, so deleting a user, repository, or analysis can remove
associated saved/tracked/analysis rows. No down migrations are checked in, and
`prisma migrate deploy` does not roll schema changes back. Restoring an older
app artifact does not reverse a database migration. Keep the additive counter
table in place during app rollback; use a verified provider restore/backup only
for an actual database recovery, with the expected data-loss window understood.
The Neon instant-restore window described above is not proof that a backup or
restore procedure has been configured or tested.

## Isolated PostgreSQL integration tests

The four shared-rate-limit database tests in
`backend/tests/test_shared_rate_limit.py` use `unittest` and are skipped unless
`GITSCOPE_RATE_LIMIT_TEST_DATABASE_URL` is present in the test process. First
create a disposable test database separate from every application database,
including staging. Verify its host, database name, and owner role before
applying the checked-in Prisma migrations. Use `DIRECT_URL` only for that
isolated migration step, then set the test variable securely to the
restricted-role TLS URL for the same test database. From the `backend`
directory, run:

```powershell
python -m unittest discover -s tests -p "test_shared_rate_limit.py" -v
```

The tests create unique `test_` counter buckets and delete only rows for those
unique buckets. They need the limiter role's table delete permission for
cleanup. Remove the test variable from the shell/CI environment afterward.
Without an isolated migrated database and its restricted-role credential, the
four tests remain skipped; do not substitute the production or primary
development URL.

## Health, timeouts, logs, cold starts, and rollback

- Flask `GET /api/health` is liveness only and returns without checking GitHub
  or PostgreSQL. Frontend `GET /api/ready` runs `SELECT 1` and returns 503 if
  PostgreSQL is unavailable or the probe exceeds one second. Neither endpoint
  proves that Auth0 or GitHub works. Limiter-guarded API routes fail closed with
  503 if the shared limiter is unavailable.
- Synchronous GitHub calls have a 15-second per-hop timeout; the async client
  uses 5-second connect/write/pool and 20-second read timeouts. Both collectors
  allow at most one redirect and meter redirect hops. Repository analytics has
  a 45-second default collection deadline, bounded to 55 seconds. Gunicorn's
  container default is 60 seconds with a 30-second graceful shutdown timeout;
  Compose gives the container 35 seconds to stop. The frontend server-side
  fetch to Flask has no explicit application timeout. Fluid Compute's 300-second
  Hobby duration can accommodate the 55-second analysis deadline plus startup
  overhead, but without Fluid Compute the 60-second maximum leaves little room
  for overhead and a sleeping Render Free service's roughly one-minute wake-up.
  Verify the Vercel setting and measure the slow path in staging; this latency
  has not been tested against provider cold starts.
- Flask logs request IDs, route templates, methods, statuses, duration, and
  exception type/stack frames without arbitrary exception text. Gunicorn access
  logs include the peer IP, method/protocol, status, response bytes, and
  duration. In this topology the backend peer is normally Vercel egress, not the
  browser IP; do not infer end-user identity from forwarded-IP headers.
- Render Free services sleep after 15 minutes without inbound traffic and take
  about a minute to wake. The shared limiter pool opens lazily on a guarded
  request, so the first guarded request also checks PostgreSQL connectivity.
  Vercel cold-start and full analysis latency have not been measured here.
- Roll back frontend/backend artifacts through their provider deployment
  controls only after confirming the old application version tolerates the
  current schema. Vercel Hobby rollback is limited to the previous production
  deployment; Render Free retains only its two most recent previous deploys.
  Confirm current service settings and runtime environment values as part of a
  rollback. See [Vercel rollback limits](https://vercel.com/docs/cli/rollback)
  and [Render rollback behavior](https://render.com/docs/rollbacks). A code
  rollback does not roll back Neon migrations; keep database recovery separate
  and verify the provider's restore/backup option before staging data is
  treated as durable.

## Remaining pre-staging verification

- On 2026-10-25, the full and production-only npm audits both reported zero
  vulnerabilities for the current lockfile. Re-run them before staging with a
  reachable advisory source. The Python audit initially found
  `PYSEC-2026-4320` in `certifi==2026.7.22`; the backend pin is now
  `certifi==2026.10.19`, and the current audit of `backend/requirements.txt`
  reports no known vulnerabilities. Re-run both audits before staging.
- Publish a privacy policy covering GitHub repository/profile data, saved
  analyses and tracked repositories, Auth0 session cookies, service/provider
  logs (including peer IP), retention, and deletion. No privacy-policy route or
  page is present in the frontend currently. An unpublished owner-review draft
  is in [PRIVACY_POLICY_DRAFT.md](PRIVACY_POLICY_DRAFT.md); its marked legal,
  retention, deletion, and provider details must be completed and verified.
- Publish a support/contact method; no support/contact page or link is present
  in the frontend currently. An unpublished owner-review draft is in
  [SUPPORT_CONTACT_DRAFT.md](SUPPORT_CONTACT_DRAFT.md); the owner must supply a
  real contact method and publish/link it before inviting testers.
- Complete keyboard, screen-reader, focus, contrast, zoom, and reduced-motion
  accessibility review on the actual staging site.
- After stable staging URLs exist, verify Auth0 login/callback/logout and
  ownership flows, Vercel-to-Render HTTPS connectivity, Neon TLS and effective
  grants, the live GitHub quota and chosen bounded budget, analytics under
  rate-limit conditions, cross-instance shared limiting, limiter-outage
  recovery, cold-start/timeout behavior, provider usage controls, and the
  database recovery and app-rollback procedures. Do not mark staging ready
  until these live checks pass.
