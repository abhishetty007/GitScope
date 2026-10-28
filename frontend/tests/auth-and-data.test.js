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
import { assertProductionConfig, auth0SettingsErrors, productionConfigErrors } from "../src/lib/runtime-config.js";
import { getDatabasePoolOptions } from "../src/lib/database-pool-config.js";
import { getMigrationDatabaseUrl } from "../src/lib/migration-database-url.js";
import { databaseReadinessResponse, isDatabaseReady } from "../src/lib/database-readiness.js";
import { fetchPublicAnalysis } from "../src/lib/public-github.js";
import { getRateLimitPresentation } from "../src/components/layout/rate-limit-presentation.js";
import { deleteSavedAnalysis, saveAnalysisForUser } from "../src/lib/user-data.js";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");

test("error boundary message never exposes arbitrary exception details", () => {
  const secretText = "postgres://user:password@db/internal-token";
  assert.equal(
    safeErrorMessage(new Error(secretText)),
    "This request could not be completed. Please try again.",
  );
  assert.equal(safeErrorMessage(new Error(secretText)).includes(secretText), false);
});

test("429 presentation distinguishes GitHub limits from GitScope admission limits", () => {
  assert.equal(
    getRateLimitPresentation(429, "GitHub rate limit exceeded. Try again later.").title,
    "GitHub rate limit reached",
  );
  for (const message of [
    "Too many GitHub requests. Try again later.",
    "GitHub service capacity is temporarily exhausted. Try again later.",
    "GitHub request budget temporarily exhausted. Try again later.",
  ]) {
    assert.notEqual(getRateLimitPresentation(429, message).title, "GitHub rate limit reached");
  }
  assert.equal(getRateLimitPresentation(429, undefined).title, "Request limit reached");
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

test("Auth0 local configuration requires server credentials and a matching issuer", () => {
  const valid = { AUTH0_DOMAIN: "tenant.example", AUTH0_ISSUER: "https://tenant.example/", AUTH0_CLIENT_ID: "client-id", AUTH0_CLIENT_SECRET: "client-secret", AUTH0_SECRET: "a".repeat(64), APP_BASE_URL: "http://localhost:3000" };
  assert.deepEqual(auth0SettingsErrors(valid), []);
  assert.ok(auth0SettingsErrors({ ...valid, AUTH0_ISSUER: "https://attacker.example/" }).includes("AUTH0_ISSUER"));
  assert.ok(auth0SettingsErrors({ ...valid, AUTH0_SECRET: "short" }).some((name) => name.startsWith("AUTH0_SECRET")));
  assert.ok(auth0SettingsErrors({ ...valid, APP_BASE_URL: "javascript:alert(1)" }).includes("APP_BASE_URL"));
  assert.ok(auth0SettingsErrors({ AUTH0_DOMAIN: "tenant.example" }).includes("AUTH0_CLIENT_SECRET"));
});

test("production config rejects the local database fallback but local config stays optional", () => {
  const base = {
    GITSCOPE_ENV: "production",
    DATABASE_URL: "postgresql://gitscope:local-dev-only@db:5432/gitscope?sslmode=require",
    GITSCOPE_API_BASE_URL: "http://backend:5000",
    GITSCOPE_SITE_URL: "https://gitscope.example",
    APP_BASE_URL: "https://gitscope.example",
    AUTH0_DOMAIN: "tenant.example",
    AUTH0_ISSUER: "https://tenant.example/",
    AUTH0_CLIENT_ID: "client-id",
    AUTH0_CLIENT_SECRET: "client-secret",
    AUTH0_SECRET: "a".repeat(64),
  };
  assert.ok(productionConfigErrors(base).some((name) => name.startsWith("DATABASE_URL")));
  assert.deepEqual(productionConfigErrors({ NODE_ENV: "production" }), []);
  assert.deepEqual(productionConfigErrors({}), []);
});

test("production Auth0 issuer is optional and derived from the configured domain", () => {
  const config = {
    GITSCOPE_ENV: "production",
    DATABASE_URL: "postgresql://app:secret@db:5432/gitscope?sslmode=require",
    GITSCOPE_API_BASE_URL: "http://backend:5000",
    GITSCOPE_SITE_URL: "https://gitscope.example",
    APP_BASE_URL: "https://gitscope.example",
    AUTH0_DOMAIN: "tenant.example",
    AUTH0_CLIENT_ID: "client-id",
    AUTH0_CLIENT_SECRET: "client-secret",
    AUTH0_SECRET: "a".repeat(64),
  };
  assert.deepEqual(productionConfigErrors(config), []);
  assert.ok(productionConfigErrors({ ...config, AUTH0_ISSUER: "https://attacker.example/" }).includes("AUTH0_ISSUER"));
});

test("production database URL requires explicit TLS", () => {
  const config = {
    GITSCOPE_ENV: "production",
    DATABASE_URL: "postgresql://app:secret@db:5432/gitscope",
    GITSCOPE_API_BASE_URL: "http://backend:5000",
    GITSCOPE_SITE_URL: "https://gitscope.example",
    APP_BASE_URL: "https://gitscope.example",
    AUTH0_DOMAIN: "tenant.example",
    AUTH0_ISSUER: "https://tenant.example/",
    AUTH0_CLIENT_ID: "client-id",
    AUTH0_CLIENT_SECRET: "client-secret",
    AUTH0_SECRET: "a".repeat(64),
  };
  assert.ok(productionConfigErrors(config).some((name) => name.includes("TLS")));
  assert.deepEqual(productionConfigErrors({
    ...config,
    DATABASE_URL: `${config.DATABASE_URL}?sslmode=require`,
  }), []);
  for (const duplicate of [
    "postgresql://app:secret@db:5432/gitscope?sslmode=require&sslmode=disable",
    "postgresql://app:secret@db:5432/gitscope?sslmode=disable&sslmode=require",
    "postgresql://app:secret@db:5432/gitscope?sslmode=require&%73slmode=require",
  ]) {
    assert.ok(productionConfigErrors({ ...config, DATABASE_URL: duplicate }).some((name) => name.includes("TLS")));
  }
});

test("production public origins require HTTPS while private Flask may use HTTP", () => {
  const config = {
    GITSCOPE_ENV: "production",
    DATABASE_URL: "postgresql://app:secret@db:5432/gitscope?sslmode=require",
    GITSCOPE_API_BASE_URL: "http://backend:5000",
    GITSCOPE_SITE_URL: "https://gitscope.example",
    APP_BASE_URL: "https://gitscope.example",
    AUTH0_DOMAIN: "tenant.example",
    AUTH0_ISSUER: "https://tenant.example/",
    AUTH0_CLIENT_ID: "client-id",
    AUTH0_CLIENT_SECRET: "client-secret",
    AUTH0_SECRET: "b".repeat(64),
  };
  assert.deepEqual(productionConfigErrors(config), []);
  assert.ok(productionConfigErrors({ ...config, APP_BASE_URL: "http://gitscope.example" }).includes("APP_BASE_URL"));
  assert.ok(productionConfigErrors({ ...config, GITSCOPE_SITE_URL: "http://gitscope.example" }).includes("GITSCOPE_SITE_URL"));
  assert.ok(productionConfigErrors({ ...config, GITSCOPE_API_BASE_URL: "http://api.gitscope.example" }).includes("GITSCOPE_API_BASE_URL"));
  assert.deepEqual(productionConfigErrors({ ...config, GITSCOPE_API_BASE_URL: "https://api.gitscope.example" }), []);
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
    AUTH0_ISSUER: "https://tenant.example/",
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

test("production npm entrypoint loads runtime env before starting the standalone server", async () => {
  const packageJson = JSON.parse(await readFile(path.join(root, "package.json"), "utf8"));
  const launcher = await readFile(path.join(root, "start-standalone.mjs"), "utf8");
  const dockerfile = await readFile(path.join(root, "Dockerfile"), "utf8");
  assert.equal(packageJson.scripts.start, "node start-standalone.mjs");
  assert.equal(packageJson.scripts.preview, "node start-standalone.mjs");
  assert.ok(launcher.indexOf("loadEnvConfig(process.cwd(), false)") < launcher.indexOf('await import("./.next/standalone/server.js")'));
  assert.match(dockerfile, /CMD \["node", "server\.js"\]/);
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
  assert.throws(() => getMigrationDatabaseUrl({ GITSCOPE_ENV: "production", DATABASE_URL: "postgresql://app:secret@db/gitscope?sslmode=require&sslmode=disable" }), /must enforce TLS/);
  assert.throws(() => getMigrationDatabaseUrl({ GITSCOPE_ENV: "production", DATABASE_URL: "postgresql://app:secret@db/gitscope?sslmode=disable&sslmode=require" }), /must enforce TLS/);
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

test("repeated login for one issuer and subject reuses the same local identity", async () => {
  const seen = new Map();
  let writes = 0;
  const db = { identity: { upsert: async ({ where }) => {
    writes += 1;
    const key = JSON.stringify(where.issuer_subject);
    if (!seen.has(key)) seen.set(key, { user: { id: "same-local-id", createdAt: new Date(0) } });
    return seen.get(key);
  } } };
  const session = { user: { sub: "google-oauth2|123", email: "person@example.com" } };
  const first = await resolveLocalUser(session, "https://tenant.example/", db);
  const second = await resolveLocalUser(session, "https://tenant.example/", db);
  assert.equal(first.id, "same-local-id");
  assert.equal(second.id, first.id);
  assert.equal(writes, 2);
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

test("public analysis fetch logs only safe downstream status and known error text", async () => {
  const originalFetch = globalThis.fetch;
  const originalError = console.error;
  const logged = [];
  globalThis.fetch = async (url) => url.endsWith("/identity")
    ? Response.json({ provider: "github", provider_repo_id: "123", visibility: "public", owner_login: "alice", name: "repo" })
    : Response.json({ error: "Internal server error" }, { status: 500 });
  console.error = (...args) => logged.push(args);
  try {
    await assert.rejects(fetchPublicAnalysis("alice", "repo"), (error) => error.status === 500);
    assert.deepEqual(logged, [["public_github_downstream_failure", {
      path: "/api/github/repository/alice/repo/analytics",
      status: 500,
      message: "Internal server error",
    }]]);

    logged.length = 0;
    globalThis.fetch = async (url) => url.endsWith("/identity")
      ? Response.json({ provider: "github", provider_repo_id: "123", visibility: "public", owner_login: "alice", name: "repo" })
      : Response.json({ error: "GitHub service capacity is temporarily exhausted. Try again later." }, { status: 429 });
    await assert.rejects(
      fetchPublicAnalysis("alice", "repo"),
      (error) => error.status === 429 && error.message === "GitHub service capacity is temporarily exhausted. Try again later."
    );
    assert.deepEqual(logged, [["public_github_downstream_failure", {
      path: "/api/github/repository/alice/repo/analytics",
      status: 429,
      message: "GitHub service capacity is temporarily exhausted. Try again later.",
    }]]);
  } finally {
    globalThis.fetch = originalFetch;
    console.error = originalError;
  }
});

test("save persists a server-fetched snapshot and uses executeRaw for the PostgreSQL void lock", async () => {
  const associations = new Set();
  const lockCalls = [];
  const analysis = {
    repository: { name: "repo", full_name: "alice/repo", updated_at: "2026-10-01T00:00:00Z" },
    health: { score: 87, categories: {} },
    activity: {},
  };
  const tx = {
    repository: { upsert: async () => ({ id: "repo-id" }) },
    analysis: {
      upsert: async ({ create }) => {
        assert.equal(create.score, 87);
        return { id: "analysis-id" };
      },
      findUnique: async () => ({ id: "analysis-id" }),
    },
    $executeRaw: async (strings, ...values) => {
      lockCalls.push({ sql: strings.join("?"), values });
    },
    savedAnalysis: {
      createMany: async ({ data, skipDuplicates }) => {
        assert.equal(skipDuplicates, true);
        const key = `${data[0].userId}:${data[0].analysisId}`;
        if (associations.has(key)) return { count: 0 };
        associations.add(key);
        return { count: 1 };
      },
    },
  };
  const db = {
    $transaction: async (callback, options) => {
      assert.equal(options.isolationLevel, "Serializable");
      return callback(tx);
    },
  };
  const dependencies = {
    db,
    fetchPublicAnalysis: async (owner, repository) => {
      assert.deepEqual([owner, repository], ["alice", "repo"]);
      return {
        identity: { provider_repo_id: "123", owner_login: "alice", name: "repo" },
        analysis,
      };
    },
  };

  const first = await saveAnalysisForUser("user-id", "alice", "repo", dependencies);
  const duplicate = await saveAnalysisForUser("user-id", "alice", "repo", dependencies);

  assert.deepEqual(first, { analysisId: "analysis-id", alreadySaved: false });
  assert.deepEqual(duplicate, { analysisId: "analysis-id", alreadySaved: true });
  assert.equal(lockCalls.length, 2);
  assert.ok(lockCalls.every(({ sql }) => sql.includes("pg_advisory_xact_lock")));
  assert.ok(lockCalls.every(({ values }) => values[0] === "analysis-id"));
});

test("saved-analysis deletion uses executeRaw for the PostgreSQL void lock", async () => {
  const lockCalls = [];
  let deleted = false;
  let counted = false;
  const tx = {
    $executeRaw: async (strings, ...values) => {
      lockCalls.push({ sql: strings.join("?"), values });
    },
    savedAnalysis: {
      findUnique: async ({ where }) => {
        assert.deepEqual(where.userId_analysisId, { userId: "user-a", analysisId: "analysis-a" });
        return { analysisId: "analysis-a" };
      },
      delete: async () => { deleted = true; },
      count: async () => { counted = true; return 1; },
    },
    analysis: { deleteMany: async () => assert.fail("shared analysis must remain") },
  };
  const db = { $transaction: async (callback, options) => {
    assert.equal(options.isolationLevel, "Serializable");
    return callback(tx);
  } };

  assert.equal(await deleteSavedAnalysis("user-a", "analysis-a", db), true);
  assert.equal(deleted, true);
  assert.equal(counted, true);
  assert.deepEqual(lockCalls, [{
    sql: "SELECT pg_advisory_xact_lock(hashtextextended(?, 0))",
    values: ["analysis-a"],
  }]);
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
    evidence: { file_contents: { README: "sensitive" }, commit_history_truncated: true },
    _commits: [{ sha: "raw" }], _contributors: [{ login: "private" }], _workflow_runs: [{ name: "workflow" }],
  });
  assert.equal(snapshot.health.score, 80);
  assert.equal(snapshot.evidence.commit_history_truncated, true);
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
