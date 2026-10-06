const mutationWindows = new Map();

export function hasSameOrigin(request) {
  const origin = request.headers.get("origin");
  if (!origin) return false;
  try {
    const expected = process.env.APP_BASE_URL
      ? new URL(process.env.APP_BASE_URL).origin
      : new URL(request.url).origin;
    return new URL(origin).origin === expected;
  } catch {
    return false;
  }
}

// Per-process backstop. Production deployments should also rate-limit these
// routes at the hosting edge because each Node process has its own window.
export function allowMutation(userId, operation, limit = 12, now = Date.now()) {
  const key = `${userId}:${operation}`;
  const current = mutationWindows.get(key);
  if (!current || now - current.startedAt >= 60_000) {
    mutationWindows.set(key, { startedAt: now, count: 1 });
  } else if (current.count >= limit) {
    return false;
  } else {
    current.count += 1;
  }

  if (mutationWindows.size > 5000) {
    for (const [entryKey, entry] of mutationWindows) {
      if (now - entry.startedAt >= 60_000) mutationWindows.delete(entryKey);
    }
  }
  return true;
}
