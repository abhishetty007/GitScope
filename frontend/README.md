# GitScope frontend

GitScope uses the Next.js App Router for server-rendered public pages and keeps
the Flask API as a separate service.

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

The Flask public analytics endpoints use a process-local fixed-window limit,
configured with `GITSCOPE_PUBLIC_ANALYTICS_LIMIT_PER_MINUTE` (default `60` per
worker). Its memory is bounded and it returns a safe 429 with `Retry-After`.
This is an application backstop only: it is not shared across Gunicorn workers
or replicas and does not replace distributed ingress protection. GitHub
collection is bounded by `GITSCOPE_ANALYSIS_TIMEOUT_SECONDS` (default `45`,
maximum `55`), `GITSCOPE_GITHUB_MAX_PAGES` (default `10`), and
`GITSCOPE_GITHUB_MAX_FILE_FETCHES` (default `100`). Reaching a page/deadline
limit fails safely instead of scoring a silently truncated commit history.

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

Build with `npm run build` and run the Node server with `npm start`. Because
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
