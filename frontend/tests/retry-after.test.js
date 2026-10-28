import assert from "node:assert/strict";
import test from "node:test";
import { fetchRepositoryAnalytics } from "../src/services/api.js";
import { fetchPublicAnalysis } from "../src/lib/public-github.js";
import { getRateLimitPresentation } from "../src/components/layout/rate-limit-presentation.js";

test("repository analytics preserves Retry-After for manual retry guidance", async () => {
  const previousFetch = globalThis.fetch;
  let calls = 0;
  globalThis.fetch = async () => {
    calls += 1;
    return Response.json(
      { error: "GitHub request budget temporarily exhausted. Try again later." },
      { status: 429, headers: { "Retry-After": "37" } },
    );
  };

  try {
    await assert.rejects(
      fetchRepositoryAnalytics("alice", "repo"),
      (error) => error.status === 429 && error.retryAfter === 37,
    );
    assert.equal(calls, 1, "a capacity denial must not trigger an automatic retry");
    assert.match(
      getRateLimitPresentation(
        429,
        "GitHub request budget temporarily exhausted. Try again later.",
        37,
      ).detail,
      /Retry in 37 seconds/,
    );
  } finally {
    globalThis.fetch = previousFetch;
  }
});

test("server-side public analysis preserves upstream retry timing", async () => {
  const previousFetch = globalThis.fetch;
  globalThis.fetch = async (url) => url.endsWith("/identity")
    ? Response.json({
        provider: "github",
        provider_repo_id: "123",
        visibility: "public",
        owner_login: "alice",
        name: "repo",
      })
    : Response.json(
        { error: "GitHub rate limit exceeded. Try again later." },
        { status: 429, headers: { "Retry-After": "61" } },
      );

  try {
    await assert.rejects(
      fetchPublicAnalysis("alice", "repo"),
      (error) => error.status === 429 && error.retryAfter === 61,
    );
  } finally {
    globalThis.fetch = previousFetch;
  }
});
