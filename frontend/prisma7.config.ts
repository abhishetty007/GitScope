import "dotenv/config";
import { defineConfig } from "prisma/config";

export default defineConfig({
  schema: "prisma/schema.prisma",
  migrations: { path: "prisma/migrations" },
  // Client generation and frontend builds do not need live database secrets.
  // Migration commands still require DATABASE_URL to point at the intended DB.
  datasource: {
    url: process.env.DATABASE_URL ?? "postgresql://gitscope:gitscope@127.0.0.1:5432/gitscope",
  },
});
