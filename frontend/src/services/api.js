const BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:5000";

async function handleResponse(response, defaultErrorMsg) {
  const data = await response.json().catch(() => ({}));

  if (!response.ok) {
    throw new Error(data.error || defaultErrorMsg);
  }

  return data;
}

export async function fetchUser(username) {
  const response = await fetch(
    `${BASE_URL}/api/github/user/${encodeURIComponent(username)}`
  );
  return handleResponse(response, "Unable to fetch GitHub user.");
}

export async function fetchUserAnalytics(username) {
  const response = await fetch(
    `${BASE_URL}/api/github/user/${encodeURIComponent(username)}/analytics`
  );
  return handleResponse(response, "Unable to fetch user analytics.");
}

export async function fetchUserRepositories(username) {
  const response = await fetch(
    `${BASE_URL}/api/github/user/${encodeURIComponent(username)}/repositories`
  );
  return handleResponse(response, "Unable to fetch user repositories.");
}

export async function fetchRepositoryAnalytics(owner, repository) {
  const response = await fetch(
    `${BASE_URL}/api/github/repository/${encodeURIComponent(
      owner
    )}/${encodeURIComponent(repository)}/analytics`
  );
  return handleResponse(response, "Unable to fetch repository analytics.");
}

