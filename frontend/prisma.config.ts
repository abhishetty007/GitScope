import { loadEnvConfig } from "@next/env";
import { defineConfig } from "prisma/config";
import { getMigrationDatabaseUrl } from "./src/lib/migration-database-url.js";

// Load frontend environment variables before resolving the database URL.
loadEnvConfig(process.cwd());

const migrationUrl = getMigrationDatabaseUrl();

export default defineConfig({
  schema: "prisma/schema.prisma",
  migrations: { path: "prisma/migrations" },
  datasource: {
    url:
      migrationUrl ??
      "postgresql://gitscope:gitscope@127.0.0.1:5432/gitscope",
  },
});