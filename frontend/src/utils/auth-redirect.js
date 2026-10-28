const SAFE_BASE = "https://gitscope.invalid";

export function safeReturnTo(value, fallback = "/") {
  if (typeof value !== "string" || !value.startsWith("/") || value.startsWith("//") || value.includes("\\")) return fallback;
  if ([...value].some((character) => character.charCodeAt(0) <= 31 || character.charCodeAt(0) === 127)) return fallback;
  try {
    const target = new URL(value, SAFE_BASE);
    if (target.origin !== SAFE_BASE) return fallback;
    return target.pathname + target.search + target.hash;
  } catch { return fallback; }
}

export function loginHref(returnTo = "/") {
  return "/auth/login?returnTo=" + encodeURIComponent(safeReturnTo(returnTo));
}
