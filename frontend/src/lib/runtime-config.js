const requiredProductionSettings = [
  "DATABASE_URL",
  "GITSCOPE_API_BASE_URL",
  "GITSCOPE_SITE_URL",
  "APP_BASE_URL",
  "AUTH0_DOMAIN",
  "AUTH0_CLIENT_ID",
  "AUTH0_CLIENT_SECRET",
  "AUTH0_SECRET",
];

export function productionConfigErrors(env = process.env) {
  if (env.GITSCOPE_ENV !== "production") return [];

  const errors = requiredProductionSettings.filter((name) => !env[name]?.trim());

  const placeholders = {
    AUTH0_DOMAIN: "your-tenant.",
    AUTH0_CLIENT_ID: "your-auth0-client-id",
    AUTH0_CLIENT_SECRET: "your-auth0-client-secret",
    AUTH0_SECRET: "replace-with-32-byte-hex-secret",
  };
  for (const [name, placeholder] of Object.entries(placeholders)) {
    if (env[name]?.includes(placeholder)) errors.push(name);
  }

  if (env.DATABASE_URL?.trim()) {
    try {
      const databaseUrl = new URL(env.DATABASE_URL);
      if (!["postgres:", "postgresql:"].includes(databaseUrl.protocol)) {
        errors.push("DATABASE_URL");
      }
      if (!databaseUrl.username || !databaseUrl.password) {
        errors.push("DATABASE_URL");
      }
      if (!["require", "verify-ca", "verify-full"].includes(databaseUrl.searchParams.get("sslmode"))) {
        errors.push("DATABASE_URL (TLS required)");
      }
      if (decodeURIComponent(databaseUrl.password) === "local-dev-only" ||
          decodeURIComponent(databaseUrl.password) === "change-me") {
        errors.push("DATABASE_URL (local fallback credential)");
      }
    } catch {
      errors.push("DATABASE_URL");
    }
  }

  for (const name of ["APP_BASE_URL", "GITSCOPE_SITE_URL", "GITSCOPE_API_BASE_URL"]) {
    if (!env[name]?.trim()) continue;
    try {
      const value = new URL(env[name]);
      if (!["http:", "https:"].includes(value.protocol) || value.username || value.password) {
        errors.push(name);
      }
    } catch {
      errors.push(name);
    }
  }

  return [...new Set(errors)];
}

export function assertProductionConfig(env = process.env) {
  const errors = productionConfigErrors(env);
  if (errors.length) {
    throw new Error(`Invalid production configuration: ${errors.join(", ")}`);
  }
}
