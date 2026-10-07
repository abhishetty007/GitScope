const DEFAULT_TIMEOUT_MS = 1000;
let inFlightProbe;

function getSharedProbe(query) {
  if (!inFlightProbe) {
    const probe = Promise.resolve().then(query);
    inFlightProbe = probe;
    const clearProbe = () => {
      if (inFlightProbe === probe) inFlightProbe = undefined;
    };
    // Attach both outcomes so a caller timing out does not leave a later
    // rejection unhandled. Callers still receive the original probe promise.
    probe.then(clearProbe, clearProbe);
  }
  return inFlightProbe;
}

export async function isDatabaseReady(query, timeoutMs = DEFAULT_TIMEOUT_MS) {
  let timer;
  try {
    await Promise.race([
      getSharedProbe(query),
      new Promise((_, reject) => {
        timer = setTimeout(() => reject(new Error("readiness timeout")), timeoutMs);
      }),
    ]);
    return true;
  } catch {
    return false;
  } finally {
    clearTimeout(timer);
  }
}

export async function databaseReadinessResponse(query, timeoutMs = DEFAULT_TIMEOUT_MS) {
  const ready = await isDatabaseReady(query, timeoutMs);
  return Response.json(
    ready ? { status: "ready" } : { status: "not_ready" },
    { status: ready ? 200 : 503 },
  );
}
