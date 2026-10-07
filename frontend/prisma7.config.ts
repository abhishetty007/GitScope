import "dotenv/config";
import { defineConfig } from "prisma/config";
import { getMigrationDatabaseUrl } from "./src/lib/migration-database-url.js";

const migrationUrl = getMigrationDatabaseUrl();

export default defineConfig({
  schema: "prisma/schema.prisma",
  migrations: { path: "prisma/migrations" },
  // Client generation and frontend builds do not need live database secrets.
  // Production migrations prefer the direct/session URL when one is configured.
  datasource: {
    url: migrationUrl ?? "postgresql://gitscope:gitscope@127.0.0.1:5432/gitscope",
  },
});
