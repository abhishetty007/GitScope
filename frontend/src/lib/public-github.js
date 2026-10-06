import "server-only";

const baseUrl = () =>
  (process.env.GITSCOPE_API_BASE_URL || "http://127.0.0.1:5000").replace(/\/$/, "");

async function getJson(path) {
  const response = await fetch(`${baseUrl()}${path}`, { cache: "no-store" });
  if (!response.ok) {
    const error = new Error(response.status === 404 ? "Public repository not found" : "GitScope analytics service is unavailable");
    error.status = response.status;
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
