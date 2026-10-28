export function parseGitHubTarget(value) {
  const input = value.trim();
  if (!input) return null;

  let parts;
  if (/^(?:https?:\/\/)?(?:www\.)?github\.com\//i.test(input)) {
    try {
      const url = new URL(/^https?:\/\//i.test(input) ? input : `https://${input}`);
      if (url.hostname.toLowerCase().replace(/^www\./, "") !== "github.com") return null;
      parts = url.pathname.split("/").filter(Boolean).map((part) => decodeURIComponent(part));
    } catch {
      return null;
    }
  } else {
    parts = input.split("/");
  }

  if (parts.some((part) => !part || /[\\/\s?#]/.test(part))) return null;
  if (parts.length === 1) return { kind: "profile", username: parts[0] };
  if (parts.length === 2) {
    const repository = parts[1].replace(/\.git$/i, "");
    if (!repository) return null;
    return { kind: "repository", owner: parts[0], repository };
  }
  return null;
}
