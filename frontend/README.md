# GitScope frontend

GitScope uses the Next.js App Router for server-rendered public pages and keeps
the Flask API as a separate service.

## Development

1. Start the Flask API from `backend`.
2. Copy `.env.example` to `.env.local` and set `GITSCOPE_API_BASE_URL` to the API
   origin (the local default is `http://127.0.0.1:5000`).
3. Run `npm install`, then `npm run dev`.

## Production configuration

Set `GITSCOPE_API_BASE_URL` in the Next.js server environment to the reachable
Flask API origin. Set `GITSCOPE_SITE_URL` before building to the deployed
frontend origin, including its scheme and host (using the value supplied by the
hosting environment). The API URL is read server-side and is not exposed as a
browser configuration value. Do not put credentials in either variable.

Build with `npm run build` and run the Node server with `npm start`. Because
public analytics pages are server-rendered, deploy the frontend to a Node-capable
Next.js host; static-only hosting is not sufficient. Configure the Flask API's
production CORS policy for any remaining browser-facing integrations.

The sitemap intentionally lists only the landing page. User and repository
analytics pages are shareable but currently emit `noindex` metadata, avoiding an
unbounded index of arbitrary GitHub entities.
