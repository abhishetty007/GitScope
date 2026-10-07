const localDevelopmentUrl = "postgresql://gitscope:gitscope@127.0.0.1:5432/gitscope";

export function getMigrationDatabaseUrl(env = process.env) {
  const url = env.DIRECT_URL || env.DATABASE_URL;
  if (env.GITSCOPE_ENV === "production") {
    if (!url) {
      throw new Error("Production migrations require DIRECT_URL or DATABASE_URL");
    }
    let parsedUrl;
    try {
      parsedUrl = new URL(url);
    } catch {
      throw new Error("Production migration database URL is invalid");
    }
    if (!["postgres:", "postgresql:"].includes(parsedUrl.protocol)) {
      throw new Error("Production migration database URL is invalid");
    }
    if (!["require", "verify-ca", "verify-full"].includes(parsedUrl.searchParams.get("sslmode"))) {
      throw new Error("Production migration database URL must enforce TLS");
    }
    return url;
  }
  return url || localDevelopmentUrl;
}
