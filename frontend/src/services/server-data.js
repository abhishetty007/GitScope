import { cache } from "react";
import {
  fetchUser,
  fetchUserAnalytics,
  fetchUserRepositories,
  fetchRepositoryAnalytics,
} from "./api";

// Request-scoped React memoization shares data between generateMetadata and page.
export const getUserAnalyticsPageData = cache(async (username) => {
  const [user, analytics, repositories] = await Promise.all([
    fetchUser(username),
    fetchUserAnalytics(username),
    fetchUserRepositories(username),
  ]);
  return { user, analytics, repositories };
});

export const getRepositoryAnalyticsPageData = cache(async (owner, repository) =>
  fetchRepositoryAnalytics(owner, repository)
);
