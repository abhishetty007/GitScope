import "server-only";
import { getAuth0 } from "./auth0.js";
import { getDb } from "./db.js";
import { resolveLocalUser } from "./identity.js";

export async function getCurrentUser(options = {}) {
  const authClient = options.authClient === undefined ? getAuth0() : options.authClient;
  if (!authClient) return null;
  const session = await authClient.getSession();
  if (typeof session?.user?.sub !== "string" || !session.user.sub) return null;

  const issuer = new URL(
    process.env.AUTH0_ISSUER || `https://${process.env.AUTH0_DOMAIN}/`,
  ).toString();
  const db = options.db || getDb();
  return resolveLocalUser(session, issuer, db);
}

export async function requireCurrentUser(options) {
  return getCurrentUser(options);
}
