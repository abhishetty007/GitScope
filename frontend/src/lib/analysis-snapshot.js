import { createHash } from "node:crypto";

const text = (value, max = 500) =>
  typeof value === "string"
    ? Array.from(value).filter((character) => {
        const code = character.codePointAt(0);
        return code >= 32 && code !== 127;
      }).join("").slice(0, max)
    : null;
const number = (value) => Number.isFinite(value) ? value : null;

export function compactAnalysis(analysis) {
  const repository = analysis?.repository || {};
  const health = analysis?.health || {};
  const activity = analysis?.activity || {};
  const categories = Object.fromEntries(
    Object.entries(health.categories || {}).map(([key, category]) => [key, {
      label: text(category.label, 100),
      score: number(category.score),
      max_score: number(category.max_score),
      percentage: number(category.percentage),
      confidence: text(category.confidence, 20),
      checks: (category.checks || []).slice(0, 20).map((check) => ({
        name: text(check.name, 120),
        status: text(check.status, 20),
        weight: number(check.weight),
        evidence: text(check.evidence, 400),
      })),
    }]),
  );

  return {
    repository: {
      name: text(repository.name, 255),
      full_name: text(repository.full_name, 511),
      description: text(repository.description, 500),
      language: text(repository.language, 100),
      stars: number(repository.stars),
      forks: number(repository.forks),
      open_issues: number(repository.open_issues),
      watchers: number(repository.watchers),
      created_at: text(repository.created_at, 40),
      updated_at: text(repository.updated_at, 40),
      default_branch: text(repository.default_branch, 255),
      html_url: text(repository.html_url, 1000),
    },
    health: {
      score: number(health.score),
      max_score: number(health.max_score),
      summary: text(health.summary, 1000),
      confidence: text(health.confidence, 20),
      project_type: health.project_type ? {
        type: text(health.project_type.type, 80),
        label: text(health.project_type.label, 120),
        confidence: text(health.project_type.confidence, 20),
      } : null,
      monorepo: health.monorepo ? {
        is_monorepo: Boolean(health.monorepo.is_monorepo),
        explicit: Boolean(health.monorepo.explicit),
      } : null,
      ci: health.ci ? {
        configured: Boolean(health.ci.configured),
        available: Boolean(health.ci.available),
        completed_runs: number(health.ci.completed_runs),
        success_rate: number(health.ci.success_rate),
      } : null,
      categories,
      strengths: (health.strengths || []).slice(0, 8).map((item) => text(item, 400)),
      concerns: (health.concerns || []).slice(0, 8).map((item) => text(item, 400)),
      recommendations: (health.recommendations || []).slice(0, 8).map((item) => text(item, 400)),
    },
    activity: {
      commits: {
        total_commits: number(activity.commits?.total_commits),
        recent: number(activity.commits?.recent),
        commits_last_30_days: number(activity.commits?.commits_last_30_days),
        commits_last_365_days: number(activity.commits?.commits_last_365_days),
        active_months: number(activity.commits?.active_months),
        longest_gap_days: number(activity.commits?.longest_gap_days),
        days_since_last_commit: number(activity.commits?.days_since_last_commit),
        commits_by_month: Object.fromEntries(
          Object.entries(activity.commits?.commits_by_month || {}).slice(-36)
            .filter(([month, count]) => /^\d{4}-\d{2}$/.test(month) && Number.isFinite(count)),
        ),
      },
      contributors: {
        total_contributors: number(activity.contributors?.total_contributors),
        total_contributions: number(activity.contributors?.total_contributions),
        top3_share: number(activity.contributors?.top3_share),
        bus_factor_50: number(activity.contributors?.bus_factor_50),
        bus_factor_80: number(activity.contributors?.bus_factor_80),
      },
    },
  };
}

export function analysisSnapshotHash(snapshot) {
  return createHash("sha256").update(JSON.stringify(snapshot)).digest("hex");
}
