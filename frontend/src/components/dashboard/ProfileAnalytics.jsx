import {
  PieChart,
  Pie,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from "recharts";

function ProfileAnalytics({ analytics, username, onAnalyzeRepo, analyzingRepo }) {
  if (!analytics) return null;

  const languageChartData = analytics.languages
    ? Object.entries(analytics.languages).map(([language, count]) => ({
        name: language,
        value: count,
      }))
    : [];

  const topRepos = analytics.top_repositories || [];

  return (
    <section>
      <h2 className="section-title">Profile Analytics</h2>

      <div className="stats-grid">
        <div className="stat-card">
          <span>Repositories</span>
          <strong>{analytics.total_repositories ?? analytics.total ?? 0}</strong>
        </div>

        <div className="stat-card">
          <span>Stars</span>
          <strong>{analytics.total_stars ?? analytics.stars ?? 0}</strong>
        </div>

        <div className="stat-card">
          <span>Forks</span>
          <strong>{analytics.total_forks ?? analytics.forks ?? 0}</strong>
        </div>

        <div className="stat-card">
          <span>Top Language</span>
          <strong>{analytics.top_language || "None"}</strong>
        </div>
      </div>

      {languageChartData.length > 0 && (
        <div className="chart-card">
          <h3>Language Distribution</h3>
          <ResponsiveContainer width="100%" height={350}>
            <PieChart>
              <Pie
                data={languageChartData}
                dataKey="value"
                nameKey="name"
                cx="50%"
                cy="50%"
                outerRadius={120}
                label
              />
              <Tooltip />
              <Legend />
            </PieChart>
          </ResponsiveContainer>
        </div>
      )}

      {topRepos.length > 0 && (
        <div style={{ marginTop: "24px" }}>
          <h3 className="section-title">Top Repositories</h3>
          <div className="repository-grid">
            {topRepos.map((repo) => (
              <div className="repository-card" key={repo.name}>
                <h3>{repo.name}</h3>
                <p>⭐ {repo.stars}</p>
                <p>🍴 {repo.forks}</p>
                <p>Language: {repo.language || "Not specified"}</p>

                <button
                  onClick={() =>
                    onAnalyzeRepo({
                      full_name: repo.full_name || `${username}/${repo.name}`,
                    })
                  }
                  disabled={analyzingRepo !== ""}
                >
                  {analyzingRepo === (repo.full_name || `${username}/${repo.name}`)
                    ? "Analyzing..."
                    : "Analyze Repository"}
                </button>

                {repo.html_url && (
                  <a href={repo.html_url} target="_blank" rel="noreferrer">
                    View on GitHub
                  </a>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
    </section>
  );
}

export default ProfileAnalytics;

