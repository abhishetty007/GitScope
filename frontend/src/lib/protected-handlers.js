const json = (payload, status = 200) => Response.json(payload, { status });
const safeErrorStatus = (error) =>
  error?.status === 404 ? 404 : error?.status === 429 ? 429 : 502;
const validSlug = (value, max) =>
  typeof value === "string" && value.length <= max && /^[A-Za-z0-9_.-]+$/.test(value);
const readInput = async (request) => {
  try {
    return { value: await request.json() };
  } catch {
    return { error: true };
  }
};

export function createProtectedHandlers(dependencies = {}) {
  const getUser = dependencies.getCurrentUser;
  const getDatabase = dependencies.getDb;
  const originCheck = dependencies.hasSameOrigin;
  const limit = dependencies.allowMutation;
  const save = dependencies.saveAnalysisForUser;
  const getSaved = dependencies.getSavedAnalysis;
  const listSaved = dependencies.listSavedAnalyses;
  const removeSaved = dependencies.deleteSavedAnalysis;
  const track = dependencies.trackPublicRepository;
  const listTracked = dependencies.listTrackedRepositories;
  const removeTracked = dependencies.removeTrackedRepository;

  async function authenticated() {
    return getUser();
  }

  async function listSavedHandler() {
    try {
      const user = await authenticated();
      if (!user) return json({ error: "Authentication required" }, 401);
      return json(await listSaved(user.id, getDatabase()));
    } catch {
      return json({ error: "Saved analyses are temporarily unavailable" }, 500);
    }
  }

  async function saveHandler(request) {
    if (!originCheck(request)) return json({ error: "Invalid request origin" }, 403);
    try {
      const user = await authenticated();
      if (!user) return json({ error: "Authentication required" }, 401);
      const parsed = await readInput(request);
      if (parsed.error) return json({ error: "Request body must be valid JSON" }, 400);
      const input = parsed.value;
      if (!validSlug(input?.owner, 39) || !validSlug(input?.repository, 100)) {
        return json({ error: "Provide a valid public repository owner and name" }, 400);
      }
      if (!limit(user.id, "save-analysis", 12)) {
        return json({ error: "Too many save requests. Try again shortly." }, 429);
      }
      const result = await save(user.id, input.owner, input.repository);
      return json(result, result.alreadySaved ? 200 : 201);
    } catch (error) {
      return json({ error: "Unable to save this public analysis" }, safeErrorStatus(error));
    }
  }

  async function getSavedHandler(_request, context) {
    try {
      const user = await authenticated();
      if (!user) return json({ error: "Authentication required" }, 401);
      const { analysisId } = await context.params;
      const saved = await getSaved(user.id, analysisId, getDatabase());
      if (!saved) return json({ error: "Saved analysis not found" }, 404);
      return json(saved);
    } catch {
      return json({ error: "Saved analysis is temporarily unavailable" }, 500);
    }
  }

  async function deleteSavedHandler(request, context) {
    if (!originCheck(request)) return json({ error: "Invalid request origin" }, 403);
    try {
      const user = await authenticated();
      if (!user) return json({ error: "Authentication required" }, 401);
      const { analysisId } = await context.params;
      if (!limit(user.id, "delete-saved-analysis", 20)) {
        return json({ error: "Too many requests. Try again shortly." }, 429);
      }
      const deleted = await removeSaved(user.id, analysisId, getDatabase());
      if (!deleted) return json({ error: "Saved analysis not found" }, 404);
      return new Response(null, { status: 204 });
    } catch {
      return json({ error: "Unable to delete saved analysis" }, 500);
    }
  }

  async function listTrackedHandler() {
    try {
      const user = await authenticated();
      if (!user) return json({ error: "Authentication required" }, 401);
      const rows = await listTracked(user.id, getDatabase());
      return json(rows.map((row) => ({
        createdAt: row.createdAt,
        repository: {
          ...row.repository,
          providerRepoId: row.repository.providerRepoId.toString(),
        },
      })));
    } catch {
      return json({ error: "Tracked repositories are temporarily unavailable" }, 500);
    }
  }

  async function trackHandler(request) {
    if (!originCheck(request)) return json({ error: "Invalid request origin" }, 403);
    try {
      const user = await authenticated();
      if (!user) return json({ error: "Authentication required" }, 401);
      const parsed = await readInput(request);
      if (parsed.error) return json({ error: "Request body must be valid JSON" }, 400);
      const input = parsed.value;
      if (!validSlug(input?.owner, 39) || !validSlug(input?.repository, 100)) {
        return json({ error: "Provide a valid public repository owner and name" }, 400);
      }
      if (!limit(user.id, "track-repository", 20)) {
        return json({ error: "Too many requests. Try again shortly." }, 429);
      }
      const result = await track(user.id, input.owner, input.repository);
      return json(result, 201);
    } catch (error) {
      return json({ error: "Unable to track this public repository" }, safeErrorStatus(error));
    }
  }

  async function untrackHandler(request, context) {
    if (!originCheck(request)) return json({ error: "Invalid request origin" }, 403);
    try {
      const user = await authenticated();
      if (!user) return json({ error: "Authentication required" }, 401);
      const { repositoryId } = await context.params;
      if (!/^[0-9a-f-]{36}$/i.test(repositoryId)) {
        return json({ error: "Tracked repository not found" }, 404);
      }
      if (!limit(user.id, "untrack-repository", 30)) {
        return json({ error: "Too many requests. Try again shortly." }, 429);
      }
      const deleted = await removeTracked(user.id, repositoryId, getDatabase());
      if (!deleted) return json({ error: "Tracked repository not found" }, 404);
      return new Response(null, { status: 204 });
    } catch {
      return json({ error: "Unable to remove tracked repository" }, 500);
    }
  }

  return {
    listSavedHandler,
    saveHandler,
    getSavedHandler,
    deleteSavedHandler,
    listTrackedHandler,
    trackHandler,
    untrackHandler,
  };
}
