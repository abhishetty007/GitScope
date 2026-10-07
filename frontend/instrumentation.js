import { assertProductionConfig } from "./src/lib/runtime-config.js";

export async function register() {
  if (process.env.NEXT_RUNTIME === "nodejs") {
    assertProductionConfig();
  }
}
