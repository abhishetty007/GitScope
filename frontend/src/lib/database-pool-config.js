const DEFAULT_POOL_MAX = 5;
const DEFAULT_CONNECTION_TIMEOUT_MS = 5000;

function readBoundedInteger(env, name, fallback, minimum, maximum) {
  const raw = env[name];
  if (raw === undefined || raw === "") return fallback;
  if (!/^\d+$/.test(raw)) {
    throw new Error(`Invalid database configuration: ${name}`);
  }
  const value = Number(raw);
  if (!Number.isSafeInteger(value) || value < minimum || value > maximum) {
    throw new Error(`Invalid database configuration: ${name}`);
  }
  return value;
}

export function getDatabasePoolOptions(env = process.env) {
  return {
    max: readBoundedInteger(env, "GITSCOPE_DB_POOL_MAX", DEFAULT_POOL_MAX, 1, 50),
    connectionTimeoutMillis: readBoundedInteger(
      env,
      "GITSCOPE_DB_CONNECTION_TIMEOUT_MS",
      DEFAULT_CONNECTION_TIMEOUT_MS,
      100,
      30000,
    ),
    idleTimeoutMillis: 10000,
  };
}
