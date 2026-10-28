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

export function auth0SettingsErrors(env = process.env) {
  const required = ["AUTH0_DOMAIN", "AUTH0_CLIENT_ID", "AUTH0_CLIENT_SECRET", "AUTH0_SECRET", "APP_BASE_URL"];
  const errors = required.filter((name) => !env[name]?.trim());
  if (env.AUTH0_SECRET?.trim() && !/^[a-fA-F0-9]{64}$/.test(env.AUTH0_SECRET)) errors.push("AUTH0_SECRET (must be 32-byte hex)");
  if (env.AUTH0_DOMAIN?.trim() && env.AUTH0_ISSUER?.trim()) {
    try {
      const issuer = new URL(env.AUTH0_ISSUER);
      if (issuer.protocol !== "https:" || issuer.href !== `https://${env.AUTH0_DOMAIN.replace(/^https?:\/\//, "").replace(/\/$/, "")}/`) errors.push("AUTH0_ISSUER");
    } catch { errors.push("AUTH0_ISSUER"); }
  }
  if (env.APP_BASE_URL?.trim()) {
    try {
      const base = new URL(env.APP_BASE_URL);
      if (!["http:", "https:"].includes(base.protocol) || base.username || base.password) errors.push("APP_BASE_URL");
    } catch { errors.push("APP_BASE_URL"); }
  }
  return [...new Set(errors)];
}

export function productionConfigErrors(env = process.env) {
  if (env.GITSCOPE_ENV !== "production") return [];

  const errors = requiredProductionSettings.filter((name) => !env[name]?.trim());
  errors.push(...auth0SettingsErrors(env).filter((name) => !errors.includes(name)));

  const placeholders = {
    AUTH0_DOMAIN: "your-tenant.",
    AUTH0_CLIENT_ID: "your-auth0-client-id",
    AUTH0_CLIENT_SECRET: "your-auth0-client-secret",
    AUTH0_SECRET: "replace-with-32-byte-hex-secret",
  };
  for (const [name, placeholder] of Object.entries(placeholders)) {
    if (env[name]?.includes(placeholder)) errors.push(name);
  }

  if (env.AUTH0_SECRET?.trim() && !/^[a-fA-F0-9]{64}$/.test(env.AUTH0_SECRET)) {
    errors.push("AUTH0_SECRET (must be 32-byte hex)");
  }

  if (env.DATABASE_URL?.trim()) {
    try {
      const databaseUrl = new URL(env.DATABASE_URL);
      const sslmodeValues = Array.from(databaseUrl.searchParams.entries())
        .filter(([name]) => name.toLowerCase() === "sslmode")
        .map(([, value]) => value.toLowerCase());
      if (!["postgres:", "postgresql:"].includes(databaseUrl.protocol)) {
        errors.push("DATABASE_URL");
      }
      if (!databaseUrl.username || !databaseUrl.password) {
        errors.push("DATABASE_URL");
      }
      if (sslmodeValues.length !== 1 || !["require", "verify-ca", "verify-full"].includes(sslmodeValues[0])) {
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
      const requiresHttps = name === "APP_BASE_URL" || name === "GITSCOPE_SITE_URL";
      const privateComposeApi = name === "GITSCOPE_API_BASE_URL" &&
        value.protocol === "http:" && value.hostname === "backend" && value.port === "5000";
      if (!["http:", "https:"].includes(value.protocol) || value.username || value.password ||
          (requiresHttps && value.protocol !== "https:") ||
          (name === "GITSCOPE_API_BASE_URL" && value.protocol !== "https:" && !privateComposeApi)) {
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
