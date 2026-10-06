import test from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import path from "node:path";
import { resolveLocalUser } from "../src/lib/identity.js";
import { compactAnalysis, analysisSnapshotHash } from "../src/lib/analysis-snapshot.js";
import { createProtectedHandlers } from "../src/lib/protected-handlers.js";
import { hasSameOrigin } from "../src/lib/request-security.js";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");

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
