import { getDb } from "../../../src/lib/db.js";
import { databaseReadinessResponse } from "../../../src/lib/database-readiness.js";

export const runtime = "nodejs";

export async function GET() {
  return databaseReadinessResponse(() => getDb().$queryRaw`SELECT 1`);
}
