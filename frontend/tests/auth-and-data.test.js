import test from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import path from "node:path";
import { resolveLocalUser } from "../src/lib/identity.js";
import { compactAnalysis, analysisSnapshotHash } from "../src/lib/analysis-snapshot.js";
import { createProtectedHandlers } from "../src/lib/protected-handlers.js";
import { hasSameOrigin } from "../src/lib/request-security.js";
import { safeErrorMessage } from "../src/lib/safe-error-message.js";
import { assertProductionConfig, productionConfigErrors } from "../src/lib/runtime-config.js";
import { getDatabasePoolOptions } from "../src/lib/database-pool-config.js";
import { getMigrationDatabaseUrl } from "../src/lib/migration-database-url.js";
import { databaseReadinessResponse, isDatabaseReady } from "../src/lib/database-readiness.js";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");

test("error boundary message never exposes arbitrary exception details", () => {
  const secretText = "postgres://user:password@db/internal-token";
  assert.equal(
    safeErrorMessage(new Error(secretText)),
    "This request could not be completed. Please try again.",
  );
  assert.equal(safeErrorMessage(new Error(secretText)).includes(secretText), false);
});

test("Next error boundary renders the safe message helper and retains retry", async () => {
  const boundary = await readFile(path.join(root, "app", "error.jsx"), "utf8");
  assert.match(boundary, /safeErrorMessage\(error\)/);
  assert.doesNotMatch(boundary, /error\?\.message/);
  assert.match(boundary, /onClick=\{reset\}/);
});

test("production configuration reports missing setting names without values", () => {
  const errors = productionConfigErrors({
    GITSCOPE_ENV: "production",
    AUTH0_SECRET: "top-secret-value",
  });
  assert.ok(errors.includes("DATABASE_URL"));
  assert.ok(errors.includes("AUTH0_DOMAIN"));
  assert.equal(errors.join(" ").includes("top-secret-value"), false);
  assert.throws(
    () => assertProductionConfig({ GITSCOPE_ENV: "production" }),
    /DATABASE_URL/,
  );
});

test("production config rejects the local database fallback but local config stays optional", () => {
  const base = {
    GITSCOPE_ENV: "production",
    DATABASE_URL: "postgresql://gitscope:local-dev-only@db:5432/gitscope?sslmode=require",
    GITSCOPE_API_BASE_URL: "http://backend:5000",
    GITSCOPE_SITE_URL: "https://gitscope.example",
    APP_BASE_URL: "https://gitscope.example",
    AUTH0_DOMAIN: "tenant.example",
    AUTH0_CLIENT_ID: "client-id",
    AUTH0_CLIENT_SECRET: "client-secret",
    AUTH0_SECRET: "a".repeat(64),
  };
  assert.ok(productionConfigErrors(base).some((name) => name.startsWith("DATABASE_URL")));
  assert.deepEqual(productionConfigErrors({ NODE_ENV: "production" }), []);
  assert.deepEqual(productionConfigErrors({}), []);
});

test("production database URL requires explicit TLS", () => {
  const config = {
    GITSCOPE_ENV: "production",
    DATABASE_URL: "postgresql://app:secret@db:5432/gitscope",
    GITSCOPE_API_BASE_URL: "http://backend:5000",
    GITSCOPE_SITE_URL: "https://gitscope.example",
    APP_BASE_URL: "https://gitscope.example",
    AUTH0_DOMAIN: "tenant.example",
    AUTH0_CLIENT_ID: "client-id",
    AUTH0_CLIENT_SECRET: "client-secret",
    AUTH0_SECRET: "a".repeat(64),
  };
  assert.ok(productionConfigErrors(config).some((name) => name.includes("TLS")));
  assert.deepEqual(productionConfigErrors({
    ...config,
    DATABASE_URL: `${config.DATABASE_URL}?sslmode=require`,
  }), []);
});

test("production public origins require HTTPS while private Flask may use HTTP", () => {
  const config = {
    GITSCOPE_ENV: "production",
    DATABASE_URL: "postgresql://app:secret@db:5432/gitscope?sslmode=require",
    GITSCOPE_API_BASE_URL: "http://backend:5000",
    GITSCOPE_SITE_URL: "https://gitscope.example",
    APP_BASE_URL: "https://gitscope.example",
    AUTH0_DOMAIN: "tenant.example",
    AUTH0_CLIENT_ID: "client-id",
    AUTH0_CLIENT_SECRET: "client-secret",
    AUTH0_SECRET: "b".repeat(64),
  };
  assert.deepEqual(productionConfigErrors(config), []);
  assert.ok(productionConfigErrors({ ...config, APP_BASE_URL: "http://gitscope.example" }).includes("APP_BASE_URL"));
  assert.ok(productionConfigErrors({ ...config, GITSCOPE_SITE_URL: "http://gitscope.example" }).includes("GITSCOPE_SITE_URL"));
  assert.deepEqual(productionConfigErrors({ ...config, GITSCOPE_ENV: "development", APP_BASE_URL: "http://localhost:3000", GITSCOPE_SITE_URL: "http://localhost:3000" }), []);
});

test("production Auth0 secret must be a 32-byte hex value and local config stays unrestricted", () => {
  const config = {
    GITSCOPE_ENV: "production",
    DATABASE_URL: "postgresql://app:secret@db:5432/gitscope?sslmode=require",
    GITSCOPE_API_BASE_URL: "http://backend:5000",
    GITSCOPE_SITE_URL: "https://gitscope.example",
    APP_BASE_URL: "https://gitscope.example",
    AUTH0_DOMAIN: "tenant.example",
    AUTH0_CLIENT_ID: "client-id",
    AUTH0_CLIENT_SECRET: "client-secret",
    AUTH0_SECRET: "c".repeat(64),
  };
  assert.deepEqual(productionConfigErrors(config), []);
  for (const secret of ["", "replace-with-32-byte-hex-secret", "z".repeat(64), "d".repeat(62)]) {
    assert.ok(productionConfigErrors({ ...config, AUTH0_SECRET: secret }).some((name) => name.startsWith("AUTH0_SECRET")));
  }
  assert.deepEqual(productionConfigErrors({ AUTH0_SECRET: "local-short-secret" }), []);
});

test("database readiness returns safe results and enforces a short timeout", async () => {
  assert.equal(await isDatabaseReady(async () => 1), true);
  assert.equal(await isDatabaseReady(async () => { throw new Error("private database details"); }), false);
  let settleTimedOutProbe;
  const timedOutProbe = isDatabaseReady(
    () => new Promise((resolve) => { settleTimedOutProbe = resolve; }),
    5,
  );
  assert.equal(await timedOutProbe, false);
  settleTimedOutProbe(1);
  await Promise.resolve();
  const healthy = await databaseReadinessResponse(async () => 1);
  assert.equal(healthy.status, 200);
  assert.deepEqual(await healthy.json(), { status: "ready" });
  const unavailable = await databaseReadinessResponse(async () => { throw new Error("private database details"); });
  assert.equal(unavailable.status, 503);
  const unavailableBody = await unavailable.text();
  assert.deepEqual(JSON.parse(unavailableBody), { status: "not_ready" });
  assert.doesNotMatch(unavailableBody, /private database details/);
});

test("timed-out readiness callers share one probe and allow a new probe after it settles", async () => {
  let queryCount = 0;
  let settleProbe;
  const stalledQuery = () => {
    queryCount += 1;
    return new Promise((resolve) => { settleProbe = resolve; });
  };

  const first = isDatabaseReady(stalledQuery, 15);
  await Promise.resolve(); // Let the first query start before the second caller arrives.
  const second = isDatabaseReady(stalledQuery, 15);
  const [firstResult, secondResult] = await Promise.all([first, second]);
  assert.equal(firstResult, false);
  assert.equal(secondResult, false);
  assert.equal(queryCount, 1);

  settleProbe(1);
  await new Promise((resolve) => setImmediate(resolve)); // Allow shared-flight cleanup to run.
  assert.equal(await isDatabaseReady(async () => {
    queryCount += 1;
    return 1;
  }, 15), true);
  assert.equal(queryCount, 2);
});

test("frontend Docker default stage is runner and migrator remains an explicit target", async () => {
  const dockerfile = await readFile(path.join(root, "Dockerfile"), "utf8");
  const localCompose = await readFile(path.resolve(root, "..", "compose.yaml"), "utf8");
  const productionCompose = await readFile(path.resolve(root, "..", "compose.production.yaml"), "utf8");
  const stages = [...dockerfile.matchAll(/^FROM\s+.+?\s+AS\s+(\w+)\s*$/gm)].map((match) => match[1]);
  assert.equal(stages.at(-1), "runner");
  assert.ok(stages.includes("migrator"));
  assert.match(dockerfile, /FROM dependencies AS migrator[\s\S]*?CMD \["npm", "run", "db:migrate:deploy"\][\s\S]*?FROM node:22-bookworm-slim AS runner/);
  const frontendService = (compose) => compose.match(/^  frontend:\n([\s\S]*?)(?=^  [a-zA-Z_][a-zA-Z0-9_-]*:|^volumes:)/m)?.[1] ?? "";
  assert.match(frontendService(localCompose), /context: \.\/frontend/);
  assert.doesNotMatch(frontendService(localCompose), /target:/);
  assert.doesNotMatch(frontendService(productionCompose), /target:/);
  assert.match(productionCompose, /migrator:[\s\S]*?target: migrator/);
});

test("production Compose uses DB readiness and grants backend graceful shutdown time", async () => {
  const productionCompose = await readFile(path.resolve(root, "..", "compose.production.yaml"), "utf8");
  assert.match(productionCompose, /\/api\/ready/);
  assert.match(productionCompose, /stop_grace_period:\s*35s/);
});

test("Prisma pg pool settings are explicit, configurable, and bounded", () => {
  assert.deepEqual(getDatabasePoolOptions({}), {
    max: 5,
    connectionTimeoutMillis: 5000,
    idleTimeoutMillis: 10000,
  });
  assert.deepEqual(getDatabasePoolOptions({
    GITSCOPE_DB_POOL_MAX: "8",
    GITSCOPE_DB_CONNECTION_TIMEOUT_MS: "2500",
  }), {
    max: 8,
    connectionTimeoutMillis: 2500,
    idleTimeoutMillis: 10000,
  });
  assert.throws(() => getDatabasePoolOptions({ GITSCOPE_DB_POOL_MAX: "0" }), /GITSCOPE_DB_POOL_MAX/);
  assert.throws(() => getDatabasePoolOptions({ GITSCOPE_DB_CONNECTION_TIMEOUT_MS: "999999" }), /GITSCOPE_DB_CONNECTION_TIMEOUT_MS/);
});

test("migration URL prefers explicit direct URL and otherwise uses DATABASE_URL", () => {
  const runtimeUrl = "postgresql://app:secret@pool:5432/gitscope?sslmode=require";
  const directUrl = "postgresql://migrator:secret@db:5432/gitscope?sslmode=verify-full";
  assert.equal(getMigrationDatabaseUrl({ GITSCOPE_ENV: "production", DATABASE_URL: runtimeUrl, DIRECT_URL: directUrl }), directUrl);
  assert.equal(getMigrationDatabaseUrl({ GITSCOPE_ENV: "production", DATABASE_URL: runtimeUrl }), runtimeUrl);
  assert.throws(() => getMigrationDatabaseUrl({ GITSCOPE_ENV: "production" }), /require DIRECT_URL or DATABASE_URL/);
  assert.throws(() => getMigrationDatabaseUrl({ GITSCOPE_ENV: "production", DATABASE_URL: "postgresql://app:secret@db/gitscope" }), /must enforce TLS/);
  assert.match(getMigrationDatabaseUrl({}), /127\.0\.0\.1:5432/);
});

test("production Compose boundary disables Flask CORS and host port publishing", async () => {
  const productionCompose = await readFile(
    path.resolve(root, "..", "compose.production.yaml"),
    "utf8",
  );
  assert.match(productionCompose, /GITSCOPE_CORS_ORIGINS:\s*["']{2}/);
  assert.match(productionCompose, /ports:\s*!reset\s*\[\]/);
  assert.match(productionCompose, /DATABASE_URL:\s*\$\{DATABASE_URL:\?Set DATABASE_URL\}/);
  assert.match(productionCompose, /GITSCOPE_ENV:\s*production/);
  assert.match(productionCompose, /postgres:\s*!reset\s+null/);
  assert.match(productionCompose, /postgres_data:\s*!reset\s+null/);
  assert.match(productionCompose, /DIRECT_URL:\s*\$\{DIRECT_URL:-\}/);
  assert.match(productionCompose, /target:\s*migrator/);
  assert.match(productionCompose, /profiles:\s*\["release"\]/);
  assert.doesNotMatch(productionCompose, /POSTGRES_PASSWORD/);
});

test("production migration image has Prisma files and receives no build-time DB secrets", async () => {
  const dockerfile = await readFile(path.resolve(root, "Dockerfile"), "utf8");
  const localCompose = await readFile(path.resolve(root, "..", "compose.yaml"), "utf8");
  const productionCompose = await readFile(path.resolve(root, "..", "compose.production.yaml"), "utf8");
  assert.match(dockerfile, /FROM dependencies AS migrator/);
  assert.match(dockerfile, /COPY prisma \.\/prisma/);
  assert.match(dockerfile, /COPY prisma7\.config\.ts/);
  assert.match(dockerfile, /COPY src\/lib\/migration-database-url\.js/);
  assert.match(dockerfile, /CMD \["npm", "run", "db:migrate:deploy"\]/);
  assert.doesNotMatch(dockerfile, /ARG\s+(?:DATABASE_URL|DIRECT_URL)/);
  assert.doesNotMatch(dockerfile, /ENV\s+(?:DATABASE_URL|DIRECT_URL)/);
  assert.doesNotMatch(localCompose, /args:[\s\S]{0,120}(?:DATABASE_URL|DIRECT_URL)/);
  assert.doesNotMatch(productionCompose, /args:[\s\S]{0,120}(?:DATABASE_URL|DIRECT_URL)/);
});

function makeRequest(url, method = "GET", body, origin = "https://gitscope.example") {
  return new Request(url, {
    method,
    headers: {
      ...(body === undefined ? {} : { "content-type": "application/json" }),
      ...(origin ? { origin } : {}),
    },
    ...(body === undefined ? {} : { body: JSON.stringify(body) }),
  });
}

function makeHandlers(overrides = {}) {
  return createProtectedHandlers({
    getCurrentUser: async () => ({ id: "user-a" }),
    getDb: () => ({}),
    hasSameOrigin: () => true,
    allowMutation: () => true,
    ...overrides,
  });
}

test("Auth0 subject maps to a local user by configured issuer and subject, never email", async () => {
  const originalIssuer = process.env.AUTH0_ISSUER;
  process.env.AUTH0_ISSUER = "https://tenant.example/";
  let query;
  try {
    const user = await resolveLocalUser(
      { user: { sub: "github|123", email: "changed@example.com" } },
      process.env.AUTH0_ISSUER,
      { identity: { upsert: async (args) => { query = args; return { user: { id: "local-uuid" } }; } } },
    );
    assert.deepEqual(user, { id: "local-uuid" });
    assert.deepEqual(query.where.issuer_subject, { issuer: "https://tenant.example/", subject: "github|123" });
    assert.equal("email" in query.where.issuer_subject, false);
  } finally {
    if (originalIssuer === undefined) delete process.env.AUTH0_ISSUER;
    else process.env.AUTH0_ISSUER = originalIssuer;
  }
});

test("unauthenticated saved-analysis requests are rejected", async () => {
  const handlers = makeHandlers({ getCurrentUser: async () => null });
  const response = await handlers.listSavedHandler();
  assert.equal(response.status, 401);
});

test("save ignores browser identity/result and uses the session user plus repository slug", async () => {
  let args;
  const handlers = makeHandlers({
    saveAnalysisForUser: async (...input) => { args = input; return { analysisId: "analysis-1", alreadySaved: false }; },
  });
  const response = await handlers.saveHandler(makeRequest("https://gitscope.example/api/saved-analyses", "POST", {
    owner: "alice", repository: "repo", userId: "user-b", result: { health: { score: 1 } },
  }));
  assert.equal(response.status, 201);
  assert.deepEqual(args, ["user-a", "alice", "repo"]);
});

test("malformed JSON mutation bodies return a client error", async () => {
  const handlers = makeHandlers();
  const request = new Request("https://gitscope.example/api/saved-analyses", {
    method: "POST",
    headers: { origin: "https://gitscope.example", "content-type": "application/json" },
    body: "{",
  });
  assert.equal((await handlers.saveHandler(request)).status, 400);
});

test("oversized save and track bodies are rejected before mutation work", async () => {
  let writes = 0;
  const handlers = makeHandlers({
    saveAnalysisForUser: async () => { writes += 1; },
    trackPublicRepository: async () => { writes += 1; },
  });
  const oversized = "x".repeat(8192);
  const requests = ["saved-analyses", "tracked-repositories"].map((path) => new Request(
    `https://gitscope.example/api/${path}`,
    { method: "POST", headers: { origin: "https://gitscope.example", "content-type": "application/json" }, body: oversized },
  ));
  const responses = [await handlers.saveHandler(requests[0]), await handlers.trackHandler(requests[1])];
  for (const response of responses) {
    assert.equal(response.status, 413);
    assert.deepEqual(await response.json(), { error: "Request body is too large" });
  }
  assert.equal(writes, 0);
});

test("saved-analysis read and delete operations are scoped to the session user", async () => {
  const scopeChecks = [];
  const handlers = makeHandlers({
    getSavedAnalysis: async (userId, analysisId) => {
      scopeChecks.push(["read", userId, analysisId]);
      return userId === "user-b" ? { analysis: { id: analysisId } } : null;
    },
    deleteSavedAnalysis: async (userId, analysisId) => {
      scopeChecks.push(["delete", userId, analysisId]);
      return userId === "user-b";
    },
  });
  const context = { params: Promise.resolve({ analysisId: "analysis-b" }) };
  assert.equal((await handlers.getSavedHandler(makeRequest("https://gitscope.example"), context)).status, 404);
  assert.equal((await handlers.deleteSavedHandler(makeRequest("https://gitscope.example", "DELETE"), context)).status, 404);
  assert.deepEqual(scopeChecks, [["read", "user-a", "analysis-b"], ["delete", "user-a", "analysis-b"]]);
});

test("tracking uses session ownership and rejects a repository the server marks unavailable", async () => {
  let trackArgs;
  const handlers = makeHandlers({
    trackPublicRepository: async (...args) => { trackArgs = args; return { repositoryId: "repo-id" }; },
    removeTrackedRepository: async (userId, repositoryId) => userId === "user-b" && repositoryId === "repo-id",
  });
  const added = await handlers.trackHandler(makeRequest("https://gitscope.example", "POST", {
    owner: "alice", repository: "repo", userId: "user-b", visibility: "private",
  }));
  assert.equal(added.status, 201);
  assert.deepEqual(trackArgs, ["user-a", "alice", "repo"]);
  const removed = await handlers.untrackHandler(
    makeRequest("https://gitscope.example", "DELETE"),
    { params: Promise.resolve({ repositoryId: "00000000-0000-0000-0000-000000000001" }) },
  );
  assert.equal(removed.status, 404);

  const privateHandlers = makeHandlers({
    trackPublicRepository: async () => { const error = new Error("not public"); error.status = 404; throw error; },
  });
  assert.equal((await privateHandlers.trackHandler(makeRequest("https://gitscope.example", "POST", { owner: "alice", repository: "secret" }))).status, 404);
});

test("authenticated lists are queried with the current local user id", async () => {
  let savedUser;
  let trackedUser;
  const handlers = makeHandlers({
    listSavedAnalyses: async (userId) => { savedUser = userId; return []; },
    listTrackedRepositories: async (userId) => { trackedUser = userId; return []; },
  });
  assert.equal((await handlers.listSavedHandler()).status, 200);
  assert.equal((await handlers.listTrackedHandler()).status, 200);
  assert.equal(savedUser, "user-a");
  assert.equal(trackedUser, "user-a");
});

test("mutations enforce same-origin and the request guard accepts only the configured origin", async () => {
  const handlers = makeHandlers({ hasSameOrigin: () => false });
  const response = await handlers.saveHandler(makeRequest("https://gitscope.example", "POST", { owner: "alice", repository: "repo" }));
  assert.equal(response.status, 403);
  assert.equal(hasSameOrigin(new Request("https://gitscope.example/api/x", { headers: { origin: "https://evil.example" } })), false);
});

test("saved snapshot is compact and excludes raw evidence, commits, contributors, and workflow payloads", () => {
  const snapshot = compactAnalysis({
    repository: { name: "repo", full_name: "alice/repo", id: 12 },
    health: { score: 80, summary: "Evidence summary", categories: { maintenance: { label: "Maintenance", score: 12, max_score: 15, checks: [{ name: "cadence", status: "PASS", weight: 3, evidence: "Monthly commits" }] } } },
    activity: {
      commits: { total_commits: 42, commits_by_author: { rawAuthor: 10 }, commits_by_month: { "2026-01": 5 } },
      contributors: { total_contributors: 3, top: [{ login: "secret-user" }], total_contributions: 42 },
    },
    evidence: { file_contents: { README: "sensitive" } },
    _commits: [{ sha: "raw" }], _contributors: [{ login: "private" }], _workflow_runs: [{ name: "workflow" }],
  });
  assert.equal(snapshot.health.score, 80);
  assert.deepEqual(snapshot.activity.commits.commits_by_month, { "2026-01": 5 });
  assert.equal(JSON.stringify(snapshot).includes("sensitive"), false);
  assert.equal(JSON.stringify(snapshot).includes("rawAuthor"), false);
  assert.equal(JSON.stringify(snapshot).includes("secret-user"), false);
  assert.equal(JSON.stringify(snapshot).includes("workflow"), false);
  assert.equal(analysisSnapshotHash(snapshot), analysisSnapshotHash(snapshot));
});

test("Prisma schema and committed migration contain stable repository identity and ownership constraints", async () => {
  const schema = await readFile(path.join(root, "prisma/schema.prisma"), "utf8");
  const migration = await readFile(path.join(root, "prisma/migrations/20261006000000_phase5_initial/migration.sql"), "utf8");
  assert.match(schema, /@@unique\(\[provider, providerRepoId\]\)/);
  assert.match(schema, /@@unique\(\[issuer, subject\]\)/);
  assert.match(schema, /@@id\(\[userId, analysisId\]\)/);
  assert.match(schema, /@@id\(\[userId, repositoryId\]\)/);
  assert.match(schema, /@@index\(\[repositoryId, createdAt\(sort: Desc\)\]\)/);
  assert.match(migration, /FOREIGN KEY \("user_id"\) REFERENCES "users"\("id"\) ON DELETE CASCADE/);
  assert.match(migration, /UNIQUE INDEX "repositories_provider_provider_repo_id_key"/);
  assert.doesNotMatch(migration, /UNIQUE INDEX "repositories_provider_owner_login_name_key"/);
});
