import "server-only";
import { getCurrentUser } from "./current-user.js";
import { getDb } from "./db.js";
import {
  deleteSavedAnalysis,
  getSavedAnalysis,
  listSavedAnalyses,
  listTrackedRepositories,
  removeTrackedRepository,
  saveAnalysisForUser,
  trackPublicRepository,
} from "./user-data.js";
import { allowMutation, hasSameOrigin } from "./request-security.js";
import { createProtectedHandlers } from "./protected-handlers.js";

export const {
  listSavedHandler,
  saveHandler,
  getSavedHandler,
  deleteSavedHandler,
  listTrackedHandler,
  trackHandler,
  untrackHandler,
} = createProtectedHandlers({
  getCurrentUser,
  getDb,
  hasSameOrigin,
  allowMutation,
  saveAnalysisForUser,
  getSavedAnalysis,
  listSavedAnalyses,
  deleteSavedAnalysis,
  trackPublicRepository,
  listTrackedRepositories,
  removeTrackedRepository,
});
