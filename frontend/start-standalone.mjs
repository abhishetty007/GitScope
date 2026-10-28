import nextEnv from "@next/env";

const { loadEnvConfig } = nextEnv;

// Match Next CLI's runtime environment loading before the generated server
// changes cwd into .next/standalone.
process.env.NODE_ENV = "production";
loadEnvConfig(process.cwd(), false);

await import("./.next/standalone/server.js");
