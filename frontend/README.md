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

Use `compose.production.yaml` with the local `compose.yaml` when deploying this
Compose configuration. It sets `GITSCOPE_ENV=production`, requires production
configuration, disables Flask CORS, and removes Flask's host-published port.
Keep Flask reachable only over the private Compose network from Next.js; the
browser calls Next.js and never calls Flask directly.

Set `GITSCOPE_SITE_URL` before building to the deployed frontend origin,
including its scheme and host. At runtime provide `DATABASE_URL`,
`GITSCOPE_API_BASE_URL`, `APP_BASE_URL`, `AUTH0_DOMAIN`, `AUTH0_CLIENT_ID`,
`AUTH0_CLIENT_SECRET`, and `AUTH0_SECRET`. `AUTH0_ISSUER` is optional; when
omitted, GitScope derives it from `AUTH0_DOMAIN`. The API URL is read
server-side and is not exposed as browser configuration. Do not put credentials
in build arguments or images. Supply secrets through the deployment runtime
configuration, not the local `.env.example` defaults.

Build with `npm run build` and run the Node server with `npm start`. Because
public analytics pages are server-rendered, deploy the frontend to a Node-capable
Next.js host; static-only hosting is not sufficient. Configure the Flask API's
production CORS policy for any remaining browser-facing integrations.

Run `npm run db:migrate:deploy` once as a release step before deploying the new
app version. Do not run Prisma schema push or migrations from application startup.
Use a PostgreSQL runtime URL with TLS and backups enabled; keep migration
credentials separate where the provider supports it. `npm run test` runs the
frontend's Node-based auth/authorization/snapshot/schema tests.

The sitemap intentionally lists only the landing page. User and repository
analytics pages are shareable but currently emit `noindex` metadata, avoiding an
unbounded index of arbitrary GitHub entities.

Tracked repositories and saved analyses currently cover public repositories
only. Private GitHub access, GitHub App installation, teams/roles, and distributed
mutation rate limiting are deferred. Per-process mutation limits are only a
backstop; configure the production hosting edge for distributed rate limiting.
