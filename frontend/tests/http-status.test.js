import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import { existsSync } from "node:fs";
import { createServer } from "node:http";
import { once } from "node:events";
import path from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

const frontendDir = fileURLToPath(new URL("..", import.meta.url));
const productionServer = path.join(frontendDir, ".next", "standalone", "server.js");

async function listen(server) {
  server.listen(0, "127.0.0.1");
  await once(server, "listening");
  return server.address().port;
}

async function close(server) {
  if (!server?.listening) return;
  server.close();
  await once(server, "close");
}

test(
  "production HTTP server returns 404 for missing routes and repositories",
  { skip: !existsSync(productionServer) && "Build the standalone app before this HTTP regression test" },
  async (t) => {
    const backend = createServer((request, response) => {
      if (request.url === "/api/github/repository/valid-owner/valid-repository/analytics") {
        response.writeHead(200, { "content-type": "application/json" });
        response.end(JSON.stringify({
          repository: {
            name: "valid-repository",
            full_name: "valid-owner/valid-repository",
            topics: [],
            html_url: "https://github.com/valid-owner/valid-repository",
          },
          health: { score: 80, confidence: "high", summary: "Mocked verified analysis", categories: {} },
          activity: { commits: {}, contributors: {} },
          evidence: {},
        }));
        return;
      }
      response.writeHead(404, { "content-type": "application/json" });
      response.end(JSON.stringify({ error: "Repository not found" }));
    });
    const backendPort = await listen(backend);
    const reservation = createServer();
    const frontendPort = await listen(reservation);
    // Release the reservation socket before starting Next on the same port.
    await close(reservation);

    const app = spawn(process.execPath, [path.join(frontendDir, "start-standalone.mjs")], {
      cwd: frontendDir,
      stdio: "ignore",
      env: {
        ...process.env,
        NODE_ENV: "production",
        HOSTNAME: "127.0.0.1",
        PORT: String(frontendPort),
        GITSCOPE_API_BASE_URL: `http://127.0.0.1:${backendPort}`,
      },
    });

    t.after(async () => {
      if (app.exitCode === null) {
        app.kill();
        await once(app, "exit");
      }
      await close(backend);
    });

    const baseUrl = `http://127.0.0.1:${frontendPort}`;
    const deadline = Date.now() + 20_000;
    let ready = false;
    while (!ready && Date.now() < deadline) {
      if (app.exitCode !== null) throw new Error("Standalone server exited before becoming ready");
      try {
        ready = (await fetch(`${baseUrl}/this-route-does-not-exist`)).status === 404;
      } catch {
        await new Promise((resolve) => setTimeout(resolve, 100));
      }
    }
    assert.equal(ready, true, "standalone server did not become ready");

    const missingRoute = await fetch(`${baseUrl}/this-route-does-not-exist`);
    assert.equal(missingRoute.status, 404);

    const readiness = await fetch(`${baseUrl}/api/ready`);
    assert.equal(readiness.status, 200);
    for (const endpoint of ["/api/saved-analyses", "/api/tracked-repositories"]) {
      const protectedApi = await fetch(`${baseUrl}${endpoint}`);
      assert.equal(protectedApi.status, 401, `${endpoint} must reject an unauthenticated request`);
    }

    const invalidRepository = await fetch(`${baseUrl}/repos/missing-owner/missing-repository`);
    assert.equal(invalidRepository.status, 404);
    assert.match(await invalidRepository.text(), /doesn.t exist/i);

    const validRepository = await fetch(`${baseUrl}/repos/valid-owner/valid-repository`);
    assert.equal(validRepository.status, 200);
    assert.match(await validRepository.text(), /Mocked verified analysis/);
  },
);
