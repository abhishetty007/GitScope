import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  LineChart,
  Line,
} from "recharts";
import { calculateGrade, getGradeBadgeClass } from "../../utils/gradeCalculator";

function HealthDashboard({ data, error }) {
  if (error) {
    return <p className="error">{error}</p>;
  }

  if (!data || !data.repository) return null;

  const { repository, health, activity } = data;

  const score = health?.score ?? null;
  const grade = calculateGrade(score);
  const badgeClass = getGradeBadgeClass(grade);

  const categories = health?.categories || {};

  const commitChartData = activity?.commits?.commits_by_author
    ? Object.entries(activity.commits.commits_by_author).map(
        ([author, commits]) => ({
          author,
          commits,
        })
      )
    : [];

  const monthlyCommitChartData = activity?.commits?.commits_by_month
    ? Object.entries(activity.commits.commits_by_month).map(
        ([month, commits]) => ({
          month,
          commits,
        })
      )
    : [];

  return (
    <section>
      <h2 className="section-title">Repository Engineering Health Analytics</h2>

      {/* Overview Header */}
      <div className="repository-header">
        <h2>{repository.full_name}</h2>
        <p>{repository.description || "No description available."}</p>

        <div className="repository-details">
          <div>
            <span>Primary Language</span>
            <strong>{repository.language || "Not specified"}</strong>
          </div>
          <div>
            <span>Default Branch</span>
            <strong>{repository.default_branch || "main"}</strong>
          </div>
          <div>
            <span>Created</span>
            <strong>
              {repository.created_at
                ? new Date(repository.created_at).toLocaleDateString()
                : "Unknown"}
            </strong>
          </div>
          <div>
            <span>Last Updated</span>
            <strong>
              {repository.updated_at
                ? new Date(repository.updated_at).toLocaleDateString()
                : "Unknown"}
            </strong>
          </div>
          <div>
            <span>GitHub Link</span>
            <a href={repository.html_url} target="_blank" rel="noreferrer">
              View Repository
            </a>
          </div>
        </div>

        {repository.topics && repository.topics.length > 0 && (
          <div className="repository-topics">
            <h3>Topics</h3>
            <div className="topic-list">
              {repository.topics.map((topic) => (
                <span className="topic-tag" key={topic}>
                  {topic}
                </span>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Repo Stats Grid */}
      <div className="stats-grid">
        <div className="stat-card">
          <span>Stars</span>
          <strong>{repository.stars ?? 0}</strong>
        </div>
        <div className="stat-card">
          <span>Forks</span>
          <strong>{repository.forks ?? 0}</strong>
        </div>
        <div className="stat-card">
          <span>Open Issues</span>
          <strong>{repository.open_issues ?? 0}</strong>
        </div>
        <div className="stat-card">
          <span>Watchers</span>
          <strong>{repository.watchers ?? 0}</strong>
        </div>
      </div>

      {/* Health Overview Hero */}
      {health && (
        <div className="chart-card activity-score-card">
          <h3>Engineering Health Score</h3>
          <p>{health.summary}</p>

          <div className="activity-score-grid">
            <div className={`stat-card health-card ${badgeClass}`}>
              <span>Grade</span>
              <strong>{grade}</strong>
            </div>

            <div className="stat-card">
              <span>Overall Score</span>
              <strong>
                {score !== null ? `${score} / 100` : "N/A"}
              </strong>
            </div>

            <div className="stat-card">
              <span>Project Type</span>
              <strong>{health.project_type?.label || "General"}</strong>
              <small>Confidence: {health.project_type?.confidence || "N/A"}</small>
            </div>

            <div className="stat-card">
              <span>Analysis Confidence</span>
              <strong>{health.confidence || "MEDIUM"}</strong>
            </div>
          </div>

          {score !== null && (
            <div className="activity-score-bar-container">
              <div className="activity-score-bar">
                <div
                  className="activity-score-fill"
                  style={{ width: `${Math.min(100, Math.max(0, score))}%` }}
                ></div>
              </div>
              <div className="activity-score-labels">
                <span>0</span>
                <span>50</span>
                <span>100</span>
              </div>
            </div>
          )}
        </div>
      )}

      {/* 6 Category Breakdown Grid */}
      {Object.keys(categories).length > 0 && (
        <div className="chart-card">
          <h3>Category Score Breakdown</h3>
          <p>
            GitScope evaluates repository evidence across six weighted engineering
            categories.
          </p>

          <div className="score-breakdown">
            {Object.entries(categories).map(([key, cat]) => (
              <div
                key={key}
                style={{
                  marginBottom: "20px",
                  paddingBottom: "16px",
                  borderBottom: "1px solid #eee",
                }}
              >
                <div
                  style={{
                    display: "flex",
                    justifyContent: "space-between",
                    alignItems: "center",
                    marginBottom: "8px",
                  }}
                >
                  <h4 style={{ margin: 0 }}>
                    {cat.label} (Max {cat.max_score} pts)
                  </h4>
                  <strong>
                    {cat.score !== null ? `${cat.score} / ${cat.max_score} (${cat.percentage}%)` : "N/A"}
                  </strong>
                </div>

                {cat.checks && cat.checks.length > 0 && (
                  <ul style={{ paddingLeft: "20px", fontSize: "0.9rem", color: "#555" }}>
                    {cat.checks.map((check, idx) => (
                      <li key={idx} style={{ marginBottom: "4px" }}>
                        <span
                          className={`badge badge-${
                            check.status === "PASS"
                              ? "pass"
                              : check.status === "PARTIAL"
                              ? "partial"
                              : check.status === "N/A"
                              ? "na"
                              : "fail"
                          }`}
                          style={{
                            marginRight: "8px",
                            padding: "2px 6px",
                            borderRadius: "4px",
                            fontSize: "0.75rem",
                            fontWeight: "bold",
                            background:
                              check.status === "PASS"
                                ? "#e6fffa"
                                : check.status === "PARTIAL"
                                ? "#fffaf0"
                                : check.status === "N/A"
                                ? "#edf2f7"
                                : "#fff5f5",
                            color:
                              check.status === "PASS"
                                ? "#234e52"
                                : check.status === "PARTIAL"
                                ? "#744210"
                                : check.status === "N/A"
                                ? "#4a5568"
                                : "#9b2c2c",
                          }}
                        >
                          {check.status}
                        </span>
                        <strong>{check.name}</strong> (Weight: {check.weight}) — {check.evidence}
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Strengths, Concerns & Recommendations */}
      {health && (
        <div className="chart-card">
          <h3>Assessment Insights & Recommendations</h3>

          {health.strengths && health.strengths.length > 0 && (
            <div style={{ marginBottom: "16px" }}>
              <h4 style={{ color: "#2e7d32" }}>Strengths</h4>
              <ul>
                {health.strengths.map((str, idx) => (
                  <li key={idx}>{str}</li>
                ))}
              </ul>
            </div>
          )}

          {health.concerns && health.concerns.length > 0 && (
            <div style={{ marginBottom: "16px" }}>
              <h4 style={{ color: "#c62828" }}>Areas of Concern</h4>
              <ul>
                {health.concerns.map((con, idx) => (
                  <li key={idx}>{con}</li>
                ))}
              </ul>
            </div>
          )}

          {health.recommendations && health.recommendations.length > 0 && (
            <div>
              <h4 style={{ color: "#1565c0" }}>Actionable Recommendations</h4>
              <ul>
                {health.recommendations.map((rec, idx) => (
                  <li key={idx}>{rec}</li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}

      {/* Commit Activity */}
      {activity?.commits && (
        <div className="chart-card">
          <h3>Commit Activity</h3>
          <div className="stats-grid" style={{ marginBottom: "16px" }}>
            <div className="stat-card">
              <span>Total Commits</span>
              <strong>{activity.commits.total_commits ?? activity.commits.total ?? 0}</strong>
            </div>
            <div className="stat-card">
              <span>Recent (90 Days)</span>
              <strong>{activity.commits.recent ?? 0}</strong>
            </div>
            <div className="stat-card">
              <span>Commit Authors</span>
              <strong>{activity.commits.authors_count ?? activity.commits.authors ?? 0}</strong>
            </div>
          </div>

          {activity.commits.top_commit_author && (
            <p>
              Most Active Author: <strong>{activity.commits.top_commit_author.name}</strong> (
              {activity.commits.top_commit_author.commits} commits)
            </p>
          )}

          {commitChartData.length > 0 && (
            <ResponsiveContainer width="100%" height={350}>
              <BarChart data={commitChartData}>
                <CartesianGrid />
                <XAxis dataKey="author" />
                <YAxis />
                <Tooltip />
                <Legend />
                <Bar dataKey="commits" name="Commits" fill="#3182ce" />
              </BarChart>
            </ResponsiveContainer>
          )}
        </div>
      )}

      {/* Monthly Commit Timeline */}
      {activity?.commits && (
        <div className="chart-card">
          <h3>Monthly Commit Activity</h3>
          {monthlyCommitChartData.length > 0 ? (
            <ResponsiveContainer width="100%" height={350}>
              <LineChart data={monthlyCommitChartData}>
                <CartesianGrid />
                <XAxis dataKey="month" />
                <YAxis />
                <Tooltip />
                <Legend />
                <Line type="monotone" dataKey="commits" name="Commits" stroke="#319795" />
              </LineChart>
            </ResponsiveContainer>
          ) : (
            <p>No monthly commit data available.</p>
          )}
        </div>
      )}

      {/* Contributors */}
      {activity?.contributors && (
        <div className="contributor-card">
          <h3>Contributors</h3>
          <div className="contributor-stats">
            <div>
              <strong>{activity.contributors.total_contributors ?? activity.contributors.total ?? 0}</strong>
              <span>Contributors</span>
            </div>
            <div>
              <strong>{activity.contributors.total_contributions ?? 0}</strong>
              <span>Total Contributions</span>
            </div>
          </div>

          {activity.contributors.top_contributor && (
            <p style={{ marginTop: "12px" }}>
              Top Contributor: <strong>{activity.contributors.top_contributor.username}</strong> (
              {activity.contributors.top_contributor.contributions} contributions)
            </p>
          )}
        </div>
      )}
    </section>
  );
}

export default HealthDashboard;

