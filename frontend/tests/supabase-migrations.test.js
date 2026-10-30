import test from "node:test";
import assert from "node:assert/strict";
import { readFile, readdir } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import path from "node:path";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const repositoryRoot = path.resolve(root, "..");

test("Supabase security migration mirrors the existing server-only RLS state", async () => {
  const sql = await readFile(
    path.join(repositoryRoot, "supabase", "migrations", "20261030051204_server_only_postgres_access.sql"),
    "utf8",
  );
  const tables = [
    "users",
    "identities",
    "repositories",
    "analyses",
    "saved_analyses",
    "tracked_repositories",
    "gitscope_rate_limit_windows",
  ];

  for (const table of tables) {
    assert.match(sql, new RegExp(`ALTER TABLE public\\.${table} DISABLE ROW LEVEL SECURITY;`));
  }
  assert.doesNotMatch(sql, /^\s*GRANT\s+/im);
});

test("Supabase security migration revokes existing Data API table privileges", async () => {
  const sql = await readFile(
    path.join(repositoryRoot, "supabase", "migrations", "20261030051212_restrict_supabase_api_roles.sql"),
    "utf8",
  );
  const tables = [
    "users",
    "identities",
    "repositories",
    "analyses",
    "saved_analyses",
    "tracked_repositories",
    "gitscope_rate_limit_windows",
  ];

  assert.match(sql, /REVOKE ALL PRIVILEGES ON TABLE[\s\S]*FROM anon, authenticated;/i);
  for (const table of tables) assert.match(sql, new RegExp(`public\\.${table}`));
  assert.doesNotMatch(sql, /^\s*GRANT\s+/im);
});

test("Supabase migration mirrors preserve the existing Prisma rate-limit constraint", async () => {
  const files = (await readdir(path.join(repositoryRoot, "supabase", "migrations"))).sort();
  assert.ok(files.includes("20261030050800_20261006000000_phase5_initial.sql"));
  assert.ok(files.includes("20261030050808_20261014000000_shared_rate_limit.sql"));
  assert.ok(files.includes("20261030051204_server_only_postgres_access.sql"));
  assert.ok(files.includes("20261030051212_restrict_supabase_api_roles.sql"));

  const prismaInitial = await readFile(
    path.join(root, "prisma", "migrations", "20261006000000_phase5_initial", "migration.sql"),
    "utf8",
  );
  const supabaseInitial = await readFile(
    path.join(repositoryRoot, "supabase", "migrations", "20261030050800_20261006000000_phase5_initial.sql"),
    "utf8",
  );
  assert.equal(supabaseInitial, prismaInitial);

  const prismaMigration = await readFile(
    path.join(root, "prisma", "migrations", "20261014000000_shared_rate_limit", "migration.sql"),
    "utf8",
  );
  const supabaseMigration = await readFile(
    path.join(repositoryRoot, "supabase", "migrations", "20261030050808_20261014000000_shared_rate_limit.sql"),
    "utf8",
  );
  assert.equal(supabaseMigration, prismaMigration);
  assert.match(
    prismaMigration,
    /CONSTRAINT "gitscope_rate_limit_windows_count_positive"\s+CHECK \("request_count" > 0\)/,
  );
});
