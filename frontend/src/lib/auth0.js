import "server-only";
import { Auth0Client } from "@auth0/nextjs-auth0/server";

let auth0;

export function getAuth0() {
  if (auth0) return auth0;
  if (!process.env.AUTH0_DOMAIN || !process.env.AUTH0_CLIENT_ID || !process.env.AUTH0_CLIENT_SECRET || !process.env.AUTH0_SECRET) {
    return null;
  }

  auth0 = new Auth0Client({
    enableAccessTokenEndpoint: false,
    session: {
      cookie: {
        secure: process.env.NODE_ENV === "production",
        sameSite: "lax",
        path: "/",
      },
    },
  });
  return auth0;
}
