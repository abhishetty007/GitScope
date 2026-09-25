import { useState } from "react";
import {
  PieChart,
  Pie,
  Tooltip,
  Legend,
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  LineChart,
  Line,
} from "recharts";
import "./App.css";


function App() {
  const [username, setUsername] = useState("");
  const [user, setUser] = useState(null);
  const [analytics, setAnalytics] = useState(null);
  const [repositories, setRepositories] = useState([]);
  const [repositorySearch, setRepositorySearch] = useState("");
  const [repositorySort, setRepositorySort] = useState("stars");
  const [repositoryAnalytics, setRepositoryAnalytics] =
    useState(null);

  const [loading, setLoading] = useState(false);
  const [analyzingRepository, setAnalyzingRepository] =
    useState("");

  const [error, setError] = useState("");
  const [repositoryError, setRepositoryError] =
    useState("");


  const analyzeUser = async () => {
    if (!username.trim()) {
      setError("Please enter a GitHub username.");
      return;
    }

    setLoading(true);
    setError("");
    setUser(null);
    setAnalytics(null);
    setRepositories([]);
    setRepositorySearch("");
    setRepositorySort("stars");
    setRepositoryAnalytics(null);
    setRepositoryError("");
    setAnalyzingRepository("");

    try {
      const usernameValue = username.trim();

      const userResponse = await fetch(
        `http://127.0.0.1:5000/api/github/user/${usernameValue}`
      );

      const userData = await userResponse.json();

      if (!userResponse.ok) {
        throw new Error(
          userData.error ||
            "Unable to fetch GitHub user."
        );
      }

      const analyticsResponse = await fetch(
        `http://127.0.0.1:5000/api/github/user/${usernameValue}/analytics`
      );

      const analyticsData =
        await analyticsResponse.json();

      if (!analyticsResponse.ok) {
        throw new Error(
          analyticsData.error ||
            "Unable to fetch analytics."
        );
      }

      const repositoriesResponse = await fetch(
        `http://127.0.0.1:5000/api/github/user/${usernameValue}/repositories`
      );

      const repositoriesData =
        await repositoriesResponse.json();

      if (!repositoriesResponse.ok) {
        throw new Error(
          repositoriesData.error ||
            "Unable to fetch repositories."
        );
      }

      setUser(userData);
      setAnalytics(analyticsData);
      setRepositories(repositoriesData);

    } catch (err) {
      setError(err.message);

    } finally {
      setLoading(false);
    }
  };


  const analyzeRepository = async (repo) => {
    setAnalyzingRepository(repo.full_name);
    setRepositoryError("");
    setRepositoryAnalytics(null);

    try {
      const [owner, repositoryName] =
        repo.full_name.split("/");

      const response = await fetch(
        `http://127.0.0.1:5000/api/github/repository/${owner}/${repositoryName}/analytics`
      );

      const data = await response.json();

      if (!response.ok) {
        throw new Error(
          data.error ||
            "Unable to fetch repository analytics."
        );
      }

      setRepositoryAnalytics(data);

    } catch (err) {
      setRepositoryError(err.message);

    } finally {
      setAnalyzingRepository("");
    }
  };


  const languageChartData = analytics
    ? Object.entries(analytics.languages).map(
        ([language, count]) => ({
          name: language,
          value: count,
        })
      )
    : [];


  const commitChartData =
    repositoryAnalytics?.activity?.commits
      ?.commits_by_author
      ? Object.entries(
          repositoryAnalytics.activity.commits
            .commits_by_author
        ).map(([author, commits]) => ({
          author,
          commits,
        }))
      : [];


  const monthlyCommitChartData =
    repositoryAnalytics?.activity?.commits
      ?.commits_by_month
      ? Object.entries(
          repositoryAnalytics.activity.commits
            .commits_by_month
        ).map(([month, commits]) => ({
          month,
          commits,
        }))
      : [];
const repositoryAge = repositoryAnalytics?.repository?.created_at
  ? Math.floor(
      (
        new Date() -
        new Date(repositoryAnalytics.repository.created_at)
      ) /
        (1000 * 60 * 60 * 24 * 365.25)
    )
  : null;

  const activityScore = repositoryAnalytics?.activity?.score;

  const healthFactors = activityScore
    ? [
        {
          name: "Commit activity",
          score: activityScore.commit_score,
          maximum: 40,
        },
        {
          name: "Contributors",
          score: activityScore.contributor_score,
          maximum: 30,
        },
        {
          name: "Repository recency",
          score: activityScore.recency_score,
          maximum: 30,
        },
      ]
    : [];

  const strongestHealthFactor =
    healthFactors.length > 0
      ? [...healthFactors].sort(
          (a, b) =>
            b.score / b.maximum -
            a.score / a.maximum
        )[0]
      : null;

  const weakestHealthFactor =
    healthFactors.length > 0
      ? [...healthFactors].sort(
          (a, b) =>
            a.score / a.maximum -
            b.score / b.maximum
        )[0]
      : null;

  const healthRecommendation =
    weakestHealthFactor?.name === "Commit activity"
      ? "Increase commit activity with more regular updates to improve repository health."
      : weakestHealthFactor?.name === "Contributors"
      ? "Encourage more contributors to participate in the repository."
      : weakestHealthFactor?.name === "Repository recency"
      ? "Make a recent update or commit to keep the repository active."
      : "GitScope could not determine a health recommendation.";


  const filteredRepositories = repositories
    .filter((repo) => {
      const searchValue = repositorySearch.trim().toLowerCase();

      if (!searchValue) {
        return true;
      }

      return (
        repo.name?.toLowerCase().includes(searchValue) ||
        repo.description?.toLowerCase().includes(searchValue)
      );
    })
    .sort((a, b) => {
      if (repositorySort === "stars") {
        return (b.stars || 0) - (a.stars || 0);
      }

      if (repositorySort === "forks") {
        return (b.forks || 0) - (a.forks || 0);
      }

      if (repositorySort === "updated") {
        return (
          new Date(b.updated_at || 0) -
          new Date(a.updated_at || 0)
        );
      }

      if (repositorySort === "name") {
        return (a.name || "").localeCompare(b.name || "");
      }

      return 0;
    });

  return (
    <div className="app">

      <header className="header">
        <div>
          <h1>GitScope</h1>
          <p>GitHub Analytics Dashboard</p>
        </div>
      </header>


      <main className="container">

        {/* Search */}
        <section className="search-card">
          <h2>Analyze a GitHub User</h2>

          <div className="search-box">

            <input
              type="text"
              placeholder="Enter GitHub username"
              value={username}
              onChange={(event) =>
                setUsername(event.target.value)
              }
              onKeyDown={(event) => {
                if (event.key === "Enter") {
                  analyzeUser();
                }
              }}
            />

            <button
              onClick={analyzeUser}
              disabled={loading}
            >
              {loading
                ? "Analyzing..."
                : "Analyze"}
            </button>

          </div>

          {error && (
            <p className="error">
              {error}
            </p>
          )}
        </section>


        {/* Profile */}
        {user && (
          <section className="profile-card">

            <img
              src={user.avatar_url}
              alt={user.login}
              className="avatar"
            />

            <div className="profile-info">

              <h2>
                {user.name || user.login}
              </h2>

              <p className="username">
                @{user.login}
              </p>

              <p>
                {user.bio ||
                  "No bio available."}
              </p>

              <div className="profile-stats">

                <span>
                  <strong>
                    {user.public_repos}
                  </strong>
                  Repositories
                </span>

                <span>
                  <strong>
                    {user.followers}
                  </strong>
                  Followers
                </span>

                <span>
                  <strong>
                    {user.following}
                  </strong>
                  Following
                </span>

              </div>

            </div>
          </section>
        )}


        {/* Profile Analytics */}
        {analytics && (
          <section>

            <h2 className="section-title">
              Profile Analytics
            </h2>

            <div className="stats-grid">

              <div className="stat-card">
                <span>Repositories</span>
                <strong>
                  {analytics.total_repositories}
                </strong>
              </div>

              <div className="stat-card">
                <span>Stars</span>
                <strong>
                  {analytics.total_stars}
                </strong>
              </div>

              <div className="stat-card">
                <span>Forks</span>
                <strong>
                  {analytics.total_forks}
                </strong>
              </div>

              <div className="stat-card">
                <span>Top Language</span>
                <strong>
                  {analytics.top_language ||
                    "None"}
                </strong>
              </div>

            </div>


            <div className="chart-card">

              <h3>Language Distribution</h3>

              {languageChartData.length > 0 && (
                <ResponsiveContainer
                  width="100%"
                  height={350}
                >
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
              )}

            </div>

          </section>
        )}


        {/* Top Repositories */}
        {analytics && (
          <section>

            <h2 className="section-title">
              Top Repositories
            </h2>

            <div className="repository-grid">

              {analytics.top_repositories.map(
                (repo) => (
                  <div
                    className="repository-card"
                    key={repo.name}
                  >

                    <h3>{repo.name}</h3>

                    <p>
                      ⭐ {repo.stars}
                    </p>

                    <p>
                      🍴 {repo.forks}
                    </p>

                    <p>
                      Language:{" "}
                      {repo.language ||
                        "Not specified"}
                    </p>

                    <button
                      onClick={() =>
                        analyzeRepository({
                          full_name: `${username.trim()}/${repo.name}`,
                        })
                      }
                      disabled={
                        analyzingRepository !== ""
                      }
                    >
                      {analyzingRepository ===
                      `${username.trim()}/${repo.name}`
                        ? "Analyzing..."
                        : "Analyze Repository"}
                    </button>

                    <a
                      href={repo.html_url}
                      target="_blank"
                      rel="noreferrer"
                    >
                      View on GitHub
                    </a>

                  </div>
                )
              )}

            </div>

          </section>
        )}


        {/* All Repositories */}
        {repositories.length > 0 && (
          <section>

            <div className="repository-section-header">
              <h2 className="section-title">
                All Repositories

                <span className="count">
                  {filteredRepositories.length}
                </span>
              </h2>

              <div className="repository-controls">
                <input
                  type="text"
                  className="repository-search"
                  placeholder="Search repositories..."
                  value={repositorySearch}
                  onChange={(event) =>
                    setRepositorySearch(event.target.value)
                  }
                />

                <select
                  className="repository-sort"
                  value={repositorySort}
                  onChange={(event) =>
                    setRepositorySort(event.target.value)
                  }
                >
                  <option value="stars">Most Stars</option>
                  <option value="forks">Most Forks</option>
                  <option value="updated">Recently Updated</option>
                  <option value="name">Name (A–Z)</option>
                </select>
              </div>
            </div>

            <div className="repository-grid">

              {filteredRepositories.map((repo) => (
                <div
                  className="repository-card"
                  key={repo.full_name}
                >

                  <h3>{repo.name}</h3>

                  <p>
                    {repo.description ||
                      "No description available."}
                  </p>

                  <div className="repo-meta">

                    <span>
                      ⭐ {repo.stars}
                    </span>

                    <span>
                      🍴 {repo.forks}
                    </span>

                  </div>

                  <p>
                    Language:{" "}
                    {repo.language ||
                      "Not specified"}
                  </p>

                  {repo.topics && repo.topics.length > 0 && (
                    <div className="repository-topics">
                      <div className="topic-list">
                        {repo.topics.map((topic) => (
                          <span
                            className="topic-tag"
                            key={topic}
                          >
                            {topic}
                          </span>
                        ))}
                      </div>
                    </div>
                  )}

                  <p>
                    Open Issues:{" "}
                    {repo.open_issues}
                  </p>

                  <button
                    onClick={() =>
                      analyzeRepository(repo)
                    }
                    disabled={
                      analyzingRepository !== ""
                    }
                  >
                    {analyzingRepository ===
                    repo.full_name
                      ? "Analyzing..."
                      : "Analyze Repository"}
                  </button>

                  <a
                    href={repo.html_url}
                    target="_blank"
                    rel="noreferrer"
                  >
                    View Repository
                  </a>

                </div>
              ))}

            </div>

            {filteredRepositories.length === 0 && (
              <p className="empty-state">
                No repositories match your search.
              </p>
            )}

          </section>
        )}


        {/* Repository Analytics */}
        {repositoryError && (
          <p className="error">
            {repositoryError}
          </p>
        )}


        {repositoryAnalytics && (
          <section>

            <h2 className="section-title">
              Repository Analytics
            </h2>


            <div className="repository-header">

              <h2>
                {
                  repositoryAnalytics
                    .repository.full_name
                }
              </h2>

              <p>
                {
                  repositoryAnalytics
                    .repository.description ||
                  "No description available."
                }
              </p>

              <div className="repository-details">
                <div>
                  <span>Created</span>
                  <strong>
                    {repositoryAnalytics.repository.created_at
                      ? new Date(
                          repositoryAnalytics.repository.created_at
                        ).toLocaleDateString()
                      : "Unknown"}
                  </strong>
                </div>

                <div>
                  <span>Last Updated</span>
                  <strong>
                    {repositoryAnalytics.repository.updated_at
                      ? new Date(
                          repositoryAnalytics.repository.updated_at
                        ).toLocaleDateString()
                      : "Unknown"}
                  </strong>
                </div>

                <div>
                  <span>Default Branch</span>
                  <strong>
                    {repositoryAnalytics.repository.default_branch ||
                      "Unknown"}
                  </strong>
                </div>
              </div>

              {repositoryAnalytics.repository.topics &&
                repositoryAnalytics.repository.topics.length > 0 && (
                  <div className="repository-topics">
                    <h3>Topics</h3>

                    <div className="topic-list">
                      {repositoryAnalytics.repository.topics.map(
                        (topic) => (
                          <span
                            className="topic-tag"
                            key={topic}
                          >
                            {topic}
                          </span>
                        )
                      )}
                    </div>
                  </div>
                )}
            </div>


            <div className="stats-grid">

              <div className="stat-card">
                <span>Stars</span>
                <strong>
                  {
                    repositoryAnalytics
                      .repository.stars
                  }
                </strong>
              </div>

              <div className="stat-card">
                <span>Forks</span>
                <strong>
                  {
                    repositoryAnalytics
                      .repository.forks
                  }
                </strong>
              </div>

              <div className="stat-card">
                <span>Open Issues</span>
                <strong>
                  {
                    repositoryAnalytics
                      .repository.open_issues
                  }
                </strong>
              </div>

              <div className="stat-card">
                <span>Watchers</span>
                <strong>
                  {
                    repositoryAnalytics
                      .repository.watchers
                  }
                </strong>
              </div>

              <div className="stat-card language-status-card">
                <span>Primary Language</span>
                <strong>
                  {repositoryAnalytics.repository.language || "Not detected"}
                </strong>
                <small>
                  {repositoryAnalytics.repository.language
                    ? "Detected from repository metadata"
                    : "GitHub did not report a primary language"}
                </small>
              </div>

              <div className="stat-card">
                <span>Repository Age</span>
                <strong>
                  {repositoryAge !== null
                    ? `${repositoryAge} years`
                    : "Unknown"}
                </strong>
              </div>

            </div>


            {/* Activity Score */}
            <div className="chart-card activity-score-card">
              <h3>Activity Score</h3>

              <p>
                GitScope calculates this score using commit activity,
                contributor count, and repository recency.
              </p>

              <div className="activity-score-grid">

                <div className="stat-card">
                  <span>Overall Score</span>
                  <strong>
                    {repositoryAnalytics.activity.score.activity_score}/100
                  </strong>
                </div>

                <div className="stat-card">
                  <span>Commit Score</span>
                  <strong>
                    {repositoryAnalytics.activity.score.commit_score}
                  </strong>
                </div>

                <div className="stat-card">
                  <span>Contributor Score</span>
                  <strong>
                    {repositoryAnalytics.activity.score.contributor_score}
                  </strong>
                </div>

                <div className="stat-card">
                  <span>Recency Score</span>
                  <strong>
                    {repositoryAnalytics.activity.score.recency_score}
                  </strong>
                </div>

              </div>

              <div className="activity-score-bar-container">
                <div className="activity-score-bar">
                  <div
                    className="activity-score-fill"
                    style={{
                      width: `${repositoryAnalytics.activity.score.activity_score}%`,
                    }}
                  ></div>
                </div>

                <div className="activity-score-labels">
                  <span>0</span>
                  <span>50</span>
                  <span>100</span>
                </div>
              </div>

              <p className="activity-score-interpretation">
                {repositoryAnalytics.activity.score.activity_score >= 80
                  ? "Highly Active"
                  : repositoryAnalytics.activity.score.activity_score >= 60
                  ? "Active"
                  : repositoryAnalytics.activity.score.activity_score >= 40
                  ? "Moderately Active"
                  : "Low Activity"}
              </p>

              <div className="score-breakdown">
                <h4>Score Breakdown</h4>

                <p>
                  Commit activity contributed{" "}
                  <strong>
                    {repositoryAnalytics.activity.score.commit_score}/40
                  </strong>{" "}
                  points.
                </p>

                <p>
                  Contributors contributed{" "}
                  <strong>
                    {repositoryAnalytics.activity.score.contributor_score}/30
                  </strong>{" "}
                  points.
                </p>

                <p>
                  Repository recency contributed{" "}
                  <strong>
                    {repositoryAnalytics.activity.score.recency_score}/30
                  </strong>{" "}
                  points.
                </p>
              </div>
            </div>


            {/* Repository Health */}
            <div className="chart-card">
              <h3>Repository Health</h3>

              <p>
                GitScope summarizes the Activity Score into a simple health
                rating based on commits, contributors, and repository recency.
              </p>

              <div className="stats-grid">

                <div
                  className={`stat-card health-card ${
                    repositoryAnalytics.activity.score.activity_score >= 80
                      ? "health-excellent"
                      : repositoryAnalytics.activity.score.activity_score >= 60
                      ? "health-good"
                      : repositoryAnalytics.activity.score.activity_score >= 40
                      ? "health-moderate"
                      : "health-attention"
                  }`}
                >
                  <span>Health Status</span>

                  <strong>
                    {repositoryAnalytics.activity.score.activity_score >= 80
                      ? "Excellent"
                      : repositoryAnalytics.activity.score.activity_score >= 60
                      ? "Good"
                      : repositoryAnalytics.activity.score.activity_score >= 40
                      ? "Moderate"
                      : "Needs Attention"}
                  </strong>
                </div>

                <div className="stat-card">
                  <span>Activity Score</span>
                  <strong>
                    {repositoryAnalytics.activity.score.activity_score}/100
                  </strong>
                </div>

              </div>

              <p>
                {repositoryAnalytics.activity.score.activity_score >= 80
                  ? "This repository shows strong and consistent activity."
                  : repositoryAnalytics.activity.score.activity_score >= 60
                  ? "This repository is active and appears to be maintained."
                  : repositoryAnalytics.activity.score.activity_score >= 40
                  ? "This repository has moderate activity and may benefit from more regular updates."
                  : "This repository currently shows low activity and may need more regular maintenance."}
              </p>

              {strongestHealthFactor && weakestHealthFactor && (
                <div className="health-summary">
                  <h4>Health Summary</h4>

                  <p>
                    <strong>Strongest factor:</strong>{" "}
                    {strongestHealthFactor.name} (
                    {strongestHealthFactor.score}/
                    {strongestHealthFactor.maximum})
                  </p>

                  <p>
                    <strong>Weakest factor:</strong>{" "}
                    {weakestHealthFactor.name} (
                    {weakestHealthFactor.score}/
                    {weakestHealthFactor.maximum})
                  </p>

                  <p>
                    <strong>Recommendation:</strong>{" "}
                    {healthRecommendation}
                  </p>
                </div>
              )}

              <p>
                <strong>How GitScope rates health:</strong>{" "}
                80–100 = Excellent, 60–79 = Good, 40–59 = Moderate,
                below 40 = Needs Attention.
              </p>
            </div>


            {/* Commit Activity */}
            <div className="chart-card">

              <h3>Commit Activity</h3>

              <p>
                Total Commits:{" "}
                <strong>
                  {
                    repositoryAnalytics
                      .activity.commits
                      .total_commits
                  }
                </strong>
              </p>

              {repositoryAnalytics.activity
                .commits.top_commit_author && (
                <p>
                  Most Active Author:{" "}
                  <strong>
                    {
                      repositoryAnalytics
                        .activity.commits
                        .top_commit_author.name
                    }
                  </strong>
                </p>
              )}


              {commitChartData.length > 0 && (
                <ResponsiveContainer
                  width="100%"
                  height={400}
                >
                  <BarChart
                    data={commitChartData}
                  >

                    <CartesianGrid />

                    <XAxis
                      dataKey="author"
                    />

                    <YAxis />

                    <Tooltip />

                    <Legend />

                    <Bar
                      dataKey="commits"
                      name="Commits"
                    />

                  </BarChart>
                </ResponsiveContainer>
              )}

            </div>


            {/* Monthly Commit Activity */}
            <div className="chart-card">

              <h3>Monthly Commit Activity</h3>

              {monthlyCommitChartData.length > 0 ? (
                <ResponsiveContainer
                  width="100%"
                  height={400}
                >
                  <LineChart
                    data={monthlyCommitChartData}
                  >

                    <CartesianGrid />

                    <XAxis
                      dataKey="month"
                    />

                    <YAxis />

                    <Tooltip />

                    <Legend />

                    <Line
                      type="monotone"
                      dataKey="commits"
                      name="Commits"
                    />

                  </LineChart>
                </ResponsiveContainer>
              ) : (
                <p>
                  No monthly commit data available.
                </p>
              )}

            </div>


            {/* Contributors */}
            <div className="contributor-card">

              <h3>Contributors</h3>

              <div className="contributor-stats">

                <div>
                  <strong>
                    {
                      repositoryAnalytics
                        .activity
                        .contributors
                        .total_contributors
                    }
                  </strong>

                  <span>
                    Contributors
                  </span>
                </div>

                <div>
                  <strong>
                    {
                      repositoryAnalytics
                        .activity
                        .contributors
                        .total_contributions
                    }
                  </strong>

                  <span>
                    Contributions
                  </span>
                </div>

              </div>


              {
                repositoryAnalytics
                  .activity.contributors
                  .top_contributor && (
                <p>
                  Top Contributor:{" "}
                  <strong>
                    {
                      repositoryAnalytics
                        .activity.contributors
                        .top_contributor
                        .username
                    }
                  </strong>
                </p>
              )}

            </div>

          </section>
        )}

      </main>

    </div>
  );
}


export default App;