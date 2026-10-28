import "server-only";
import { Auth0Client } from "@auth0/nextjs-auth0/server";
import { assertProductionConfig, auth0SettingsErrors } from "./runtime-config.js";

let auth0;

export function getAuth0() {
  if (auth0) return auth0;
  if (process.env.GITSCOPE_ENV === "production") assertProductionConfig();
  if (auth0SettingsErrors().length) return null;

  auth0 = new Auth0Client({
    domain: process.env.AUTH0_DOMAIN,
    clientId: process.env.AUTH0_CLIENT_ID,
    clientSecret: process.env.AUTH0_CLIENT_SECRET,
    secret: process.env.AUTH0_SECRET,
    appBaseUrl: process.env.APP_BASE_URL,
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
