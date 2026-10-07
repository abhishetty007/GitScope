import "server-only";
import { PrismaPg } from "@prisma/adapter-pg";
import { PrismaClient } from "../generated/prisma/client.ts";
import { getDatabasePoolOptions } from "./database-pool-config.js";

const globalForPrisma = globalThis;

export function getDb() {
  if (!process.env.DATABASE_URL) {
    throw new Error("Database is not configured");
  }
  if (!globalForPrisma.gitScopePrisma) {
    const adapter = new PrismaPg({
      connectionString: process.env.DATABASE_URL,
      ...getDatabasePoolOptions(),
    });
    globalForPrisma.gitScopePrisma = new PrismaClient({ adapter });
  }
  return globalForPrisma.gitScopePrisma;
}
