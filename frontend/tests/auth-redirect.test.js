import test from "node:test";
import assert from "node:assert/strict";
import { loginHref, safeReturnTo } from "../src/utils/auth-redirect.js";

test("login redirect preserves an encoded internal path", () => {
  assert.equal(loginHref("/saved/123e4567-e89b-12d3-a456-426614174000"), "/auth/login?returnTo=%2Fsaved%2F123e4567-e89b-12d3-a456-426614174000");
});

test("safe returnTo preserves internal query and fragment", () => {
  assert.equal(safeReturnTo("/repos/facebook/react?tab=health#summary"), "/repos/facebook/react?tab=health#summary");
});

test("login redirect rejects external, protocol-relative, and malformed targets", () => {
  for (const target of ["https://example.com/", "//example.com/", "javascript:alert(1)", "/\\evil.example", "/\u0000bad"]) {
    assert.equal(loginHref(target), "/auth/login?returnTo=%2F");
  }
});

test("safe returnTo normalizes dot segments without leaving the application origin", () => {
  assert.equal(safeReturnTo("/../saved"), "/saved");
});
