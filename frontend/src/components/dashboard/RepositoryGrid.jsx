"use client";

import { useState } from "react";

function RepositoryGrid({ repositories, onAnalyzeRepo, analyzingRepo }) {
  const [search, setSearch] = useState("");
  const [sort, setSort] = useState("stars");

  if (!repositories || repositories.length === 0) return null;

  const filteredRepositories = repositories
    .filter((repo) => {
      const searchValue = search.trim().toLowerCase();
      if (!searchValue) return true;
      return (
        repo.name?.toLowerCase().includes(searchValue) ||
        repo.description?.toLowerCase().includes(searchValue)
      );
    })
    .sort((a, b) => {
      if (sort === "stars") return (b.stars || 0) - (a.stars || 0);
      if (sort === "forks") return (b.forks || 0) - (a.forks || 0);
      if (sort === "updated") return new Date(b.updated_at || 0) - new Date(a.updated_at || 0);
      if (sort === "name") return (a.name || "").localeCompare(b.name || "");
      return 0;
    });

  return (
    <section>
      <div className="repository-section-header">
        <h2 className="section-title">
          All Repositories
          <span className="count">{filteredRepositories.length}</span>
        </h2>

        <div className="repository-controls">
          <input
            type="text"
            className="repository-search"
            placeholder="Search repositories..."
            value={search}
            onChange={(event) => setSearch(event.target.value)}
          />

          <select
            className="repository-sort"
            value={sort}
            onChange={(event) => setSort(event.target.value)}
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
          <div className="repository-card" key={repo.full_name}>
            <h3>{repo.name}</h3>
            <p>{repo.description || "No description available."}</p>

            <div className="repo-meta">
              <span>⭐ {repo.stars}</span>
              <span>🍴 {repo.forks}</span>
            </div>

            <p>Language: {repo.language || "Not specified"}</p>

            {repo.topics && repo.topics.length > 0 && (
              <div className="repository-topics">
                <div className="topic-list">
                  {repo.topics.map((topic) => (
                    <span className="topic-tag" key={topic}>
                      {topic}
                    </span>
                  ))}
                </div>
              </div>
            )}

            <p>Open Issues: {repo.open_issues}</p>

            <button
              onClick={() => onAnalyzeRepo(repo)}
              disabled={analyzingRepo !== ""}
            >
              {analyzingRepo === repo.full_name ? "Analyzing..." : "Analyze Repository"}
            </button>

            <a href={repo.html_url} target="_blank" rel="noreferrer">
              View Repository
            </a>
          </div>
        ))}
      </div>

      {filteredRepositories.length === 0 && (
        <p className="empty-state">No repositories match your search.</p>
      )}
    </section>
  );
}

export default RepositoryGrid;
