import "server-only";
import { PrismaPg } from "@prisma/adapter-pg";
import { PrismaClient } from "../generated/prisma/client.ts";

const globalForPrisma = globalThis;

export function getDb() {
  if (!process.env.DATABASE_URL) {
    throw new Error("Database is not configured");
  }
  if (!globalForPrisma.gitScopePrisma) {
    const adapter = new PrismaPg({ connectionString: process.env.DATABASE_URL });
    globalForPrisma.gitScopePrisma = new PrismaClient({ adapter });
  }
  return globalForPrisma.gitScopePrisma;
}
