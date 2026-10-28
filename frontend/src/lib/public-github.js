import "server-only";

const baseUrl = () =>
  (process.env.GITSCOPE_API_BASE_URL || "http://127.0.0.1:5000").replace(/\/$/, "");

const safeDownstreamMessages = new Set([
  "Public repository not found",
  "Repository not found",
  "GitHub rate limit exceeded. Try again later.",
  "Too many GitHub requests. Try again later.",
  "GitHub service capacity is temporarily exhausted. Try again later.",
  "GitHub request budget temporarily exhausted. Try again later.",
  "Service temporarily unavailable. Try again shortly.",
  "Internal server error",
]);

async function getJson(path) {
  const response = await fetch(`${baseUrl()}${path}`, { cache: "no-store" });
  if (!response.ok) {
    const payload = await response.clone().json().catch(() => ({}));
    const message = safeDownstreamMessages.has(payload.error)
      ? payload.error
      : "Downstream service returned an unrecognized error";
    console.error("public_github_downstream_failure", {
      path,
      status: response.status,
      message,
    });
    const error = new Error(
      response.status === 404
        ? "Public repository not found"
        : safeDownstreamMessages.has(payload.error)
          ? payload.error
          : "GitScope analytics service is unavailable"
    );
    error.status = response.status;
    const retryAfter = Number(response.headers.get("retry-after"));
    if (Number.isSafeInteger(retryAfter) && retryAfter > 0) {
      error.retryAfter = retryAfter;
    }
    throw error;
  }
  return response.json();
}

export async function fetchPublicAnalysis(owner, repository) {
  const ownerPart = encodeURIComponent(owner);
  const repoPart = encodeURIComponent(repository);
  const [identity, analysis] = await Promise.all([
    getJson(`/api/github/repository/${ownerPart}/${repoPart}/identity`),
    getJson(`/api/github/repository/${ownerPart}/${repoPart}/analytics`),
  ]);

  if (
    identity.provider !== "github" ||
    !/^\d+$/.test(identity.provider_repo_id || "") ||
    identity.visibility !== "public" ||
    !analysis.repository?.full_name ||
    analysis.repository.full_name.toLowerCase() !== `${identity.owner_login}/${identity.name}`.toLowerCase()
  ) {
    const error = new Error("GitScope returned an invalid public repository analysis");
    error.status = 502;
    throw error;
  }
  return { identity, analysis };
}

export async function fetchPublicRepository(owner, repository) {
  const ownerPart = encodeURIComponent(owner);
  const repoPart = encodeURIComponent(repository);
  const identity = await getJson(
    `/api/github/repository/${ownerPart}/${repoPart}/identity`,
  );
  if (
    identity.provider !== "github" ||
    !/^\d+$/.test(identity.provider_repo_id || "") ||
    identity.visibility !== "public"
  ) {
    const error = new Error("Public repository not found");
    error.status = 404;
    throw error;
  }
  return identity;
}
