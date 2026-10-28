import test from "node:test";
import assert from "node:assert/strict";
import nextConfig from "../next.config.mjs";

test("global response headers include baseline browser protections", async () => {
  const rules = await nextConfig.headers();
  const values = new Map(rules[0].headers.map(({ key, value }) => [key, value]));

  assert.equal(rules[0].source, "/:path*");
  assert.equal(values.get("X-Content-Type-Options"), "nosniff");
  assert.equal(values.get("X-Frame-Options"), "DENY");
  const csp = values.get("Content-Security-Policy");
  assert.match(csp, /default-src 'self'/);
  assert.match(csp, /script-src 'self' 'unsafe-inline'/);
  assert.doesNotMatch(csp, /unsafe-eval/);
  assert.match(csp, /base-uri 'self'/);
  assert.match(csp, /form-action 'self'/);
  assert.match(csp, /frame-ancestors 'none'/);
  assert.match(csp, /object-src 'none'/);
  assert.match(csp, /img-src 'self' data: https:\/\/avatars\.githubusercontent\.com/);
  assert.equal(values.get("Referrer-Policy"), "strict-origin-when-cross-origin");
  assert.match(values.get("Permissions-Policy"), /camera=\(\)/);
});
