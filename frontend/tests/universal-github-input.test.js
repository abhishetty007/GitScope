import test from "node:test";
import assert from "node:assert/strict";
import { parseGitHubTarget } from "../src/utils/github-target.js";

test("universal GitHub input recognizes profile and repository slugs", () => {
  assert.deepEqual(parseGitHubTarget("octocat"), { kind: "profile", username: "octocat" });
  assert.deepEqual(parseGitHubTarget("facebook/react"), { kind: "repository", owner: "facebook", repository: "react" });
});

test("universal GitHub input recognizes profile and repository URLs", () => {
  assert.deepEqual(parseGitHubTarget("https://github.com/octocat"), { kind: "profile", username: "octocat" });
  assert.deepEqual(parseGitHubTarget("https://github.com/facebook/react"), { kind: "repository", owner: "facebook", repository: "react" });
  assert.deepEqual(parseGitHubTarget("HTTPS://github.com/octocat/"), { kind: "profile", username: "octocat" });
  assert.deepEqual(parseGitHubTarget("github.com/facebook/react.git"), { kind: "repository", owner: "facebook", repository: "react" });
});

test("universal GitHub input rejects malformed and unrelated URLs", () => {
  for (const value of ["", "   ", "facebook/react/tree/main", "https://gitlab.com/owner/repo", "https://github.com/owner/%2Frepo", "owner//repo"]) {
    assert.equal(parseGitHubTarget(value), null, value);
  }
});
