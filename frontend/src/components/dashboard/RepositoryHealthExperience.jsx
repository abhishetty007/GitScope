"use client";

import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, LineChart, Line } from "recharts";
import { calculateGrade, getGradeBadgeClass } from "../../utils/gradeCalculator";

const statusLabel = (status) => status === "PASS" ? "Pass" : status === "PARTIAL" ? "Partial" : status === "N/A" ? "Not applicable" : status === "FAIL" ? "Fail" : status || "Unknown";

function Category({ name, category, index }) {
  const checks = category.checks || [];
  const passed = checks.filter((item) => item.status === "PASS").length;
  const partial = checks.filter((item) => item.status === "PARTIAL").length;
  const failed = checks.filter((item) => item.status === "FAIL").length;
  const applicable = checks.filter((item) => item.status !== "N/A").length;
  const summary = checks.length ? `${passed} passed · ${partial} partial · ${failed} failed · ${checks.length - applicable} not applicable` : "No check details available.";
  return <details className="health-category" open={index === 0}>
    <summary>
      <span className="category-index">0{index + 1}</span><span className="health-category-name"><b>{category.label || name}</b><small>{summary}</small></span>
      <span className="category-score">{category.score == null ? "N/A" : `${category.score} / ${category.max_score}`}<small>{category.percentage == null ? "" : `${category.percentage}%`}</small></span>
      <span className="details-chevron" aria-hidden="true">⌄</span>
    </summary>
    {checks.length ? <ul className="check-list">{checks.map((check, checkIndex) => <li className="check-row" key={`${check.name}-${checkIndex}`}>
      <span className={`status-pill status-${String(check.status || "unknown").toLowerCase().replace(/[^a-z]/g, "")}`}><i aria-hidden="true" />{statusLabel(check.status)}</span>
      <div className="check-content"><b>{check.name}</b><p>{check.evidence || "No evidence detail provided."}</p></div>
      <span className="check-weight">Weight <b>{check.weight ?? "—"}</b></span>
    </li>)}</ul> : <p className="category-empty">No checks are available for this category.</p>}
  </details>;
}

export default function RepositoryHealthExperience({ data }) {
  if (!data?.repository) return null;
  const { repository, health, activity } = data;
  const score = health?.score ?? null;
  const grade = calculateGrade(score);
  const categories = Object.entries(health?.categories || {});
  const metrics = [["Stars", repository.stars], ["Forks", repository.forks], ["Open issues", repository.open_issues], ["Watchers", repository.watchers]];
  const authors = Object.entries(activity?.commits?.commits_by_author || {}).map(([author, commits]) => ({ author, commits }));
  const months = Object.entries(activity?.commits?.commits_by_month || {}).map(([month, commits]) => ({ month, commits }));
  const updated = repository.updated_at ? new Date(repository.updated_at).toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" }) : "Not available";
  return <div className="repo-analysis">
    <section className="repo-identity" aria-labelledby="repo-name">
      <div className="repo-identity-main"><span className="repo-glyph">⌘</span><div><p className="eyebrow">Repository analysis</p><h1 id="repo-name">{repository.full_name}</h1><p className="repo-description">{repository.description || "No repository description provided."}</p></div></div>
      <a className="button button-secondary github-link" href={repository.html_url} target="_blank" rel="noreferrer">View on GitHub <span aria-hidden="true">↗</span></a>
      <div className="repo-context"><span>{repository.language || "Language not specified"}</span><span>Default branch: <b>{repository.default_branch || "Not available"}</b></span><span>Updated {updated}</span></div>
    </section>

    {health ? <section className="health-result" aria-labelledby="health-heading">
      <div className="result-heading"><div><p className="eyebrow">Assessment result</p><h2 id="health-heading">Engineering Health</h2></div><span className="analysis-confidence">Confidence <b>{health.confidence || "Not available"}</b></span></div>
      <div className="result-main">
        <div className="score-wrap"><div className="score-display" role="group" aria-label={score == null ? "Engineering Health score not available" : `Engineering Health score ${score} out of 100`}><div><strong>{score ?? "—"}</strong><span>/ 100</span></div><small>Engineering Health score</small></div></div>
        <div className="result-copy"><span className={`grade-label ${getGradeBadgeClass(grade)}`}>Grade <b>{grade}</b></span><p className="health-summary-text">{health.summary || "Review the category evidence below for this repository."}</p>{health.project_type?.label ? <p className="project-context">Project context: <b>{health.project_type.label}</b>{health.project_type.confidence ? ` · ${health.project_type.confidence} confidence` : ""}</p> : null}</div>
      </div>
      {score != null ? <div className="score-progress"><div className="score-progress-track"><span style={{ width: `${Math.min(100, Math.max(0, score))}%` }} /></div><div><span>0</span><span>100</span></div></div> : null}
    </section> : null}

    <section className="category-section" aria-labelledby="category-heading"><div className="section-heading"><div><p className="eyebrow">Transparent breakdown</p><h2 id="category-heading">Category results</h2></div><p className="section-intro">Expand a category to inspect the checks and repository evidence behind its result.</p></div>
      {categories.length ? <div className="category-list">{categories.map(([name, category], index) => <Category key={name} name={name} category={category} index={index} />)}</div> : <p className="empty-inline">Category results are not available for this analysis.</p>}
    </section>

    {health ? <section className="assessment-section" aria-labelledby="assessment-heading"><div className="section-heading"><div><p className="eyebrow">What the signals suggest</p><h2 id="assessment-heading">Assessment</h2></div></div><div className="assessment-grid">
      {[["strengths", "Strengths", "✓"], ["concerns", "Concerns", "!"], ["recommendations", "Recommendations", "→"]].map(([key, title, mark]) => <article className={`assessment-panel assessment-${key}`} key={key}><div className="assessment-title"><span aria-hidden="true">{mark}</span><h3>{title}</h3></div>{health[key]?.length ? <ul>{health[key].map((item, index) => <li key={`${key}-${index}`}>{item}</li>)}</ul> : <p>No {title.toLowerCase()} were returned for this analysis.</p>}</article>)}
    </div></section> : null}

    <section className="context-section" aria-labelledby="context-heading"><div className="section-heading"><div><p className="eyebrow">Supporting context</p><h2 id="context-heading">Repository activity</h2></div><p className="section-intro">Activity and popularity provide context; they do not define the health score.</p></div>
      <div className="metrics-strip" aria-label="Repository popularity metrics">{metrics.map(([label, value]) => <div className="metric-item" key={label}><span>{label}</span><b>{value ?? "—"}</b></div>)}</div>
      {activity?.commits ? <div className="activity-grid"><article className="activity-panel"><h3>Commit activity</h3><div className="activity-stats"><p><b>{activity.commits.total_commits ?? activity.commits.total ?? 0}</b><span>Total commits</span></p><p><b>{activity.commits.recent ?? 0}</b><span>Recent (90 days)</span></p><p><b>{activity.commits.authors_count ?? activity.commits.authors ?? 0}</b><span>Authors</span></p></div>{authors.length ? <><div className="chart-wrap" role="img" aria-label={`Commits by author: ${authors.map((item) => `${item.author}, ${item.commits}`).join("; ")}`}><ResponsiveContainer width="100%" height={250}><BarChart data={authors} margin={{ top: 12, right: 12, bottom: 30, left: -16 }}><CartesianGrid stroke="var(--chart-grid)" vertical={false} /><XAxis dataKey="author" angle={-20} textAnchor="end" interval={0} tick={{ fill: "var(--text-muted)", fontSize: 11 }} /><YAxis tick={{ fill: "var(--text-muted)", fontSize: 11 }} allowDecimals={false} /><Tooltip contentStyle={{ background: "var(--surface-raised)", border: "1px solid var(--border)" }} /><Bar dataKey="commits" name="Commits" fill="var(--accent)" radius={[3, 3, 0, 0]} /></BarChart></ResponsiveContainer></div><ul className="chart-text-list">{authors.map((item) => <li key={item.author}>{item.author}: {item.commits} commits</li>)}</ul></> : <p className="empty-inline">No author breakdown is available.</p>}{activity.commits.top_commit_author ? <p className="top-contributor">Most active author: <b>{activity.commits.top_commit_author.name}</b> ({activity.commits.top_commit_author.commits} commits)</p> : null}</article>
      <article className="activity-panel"><h3>Monthly commits</h3>{months.length ? <><div className="chart-wrap" role="img" aria-label={`Monthly commits: ${months.map((item) => `${item.month}, ${item.commits}`).join("; ")}`}><ResponsiveContainer width="100%" height={250}><LineChart data={months} margin={{ top: 12, right: 12, bottom: 16, left: -16 }}><CartesianGrid stroke="var(--chart-grid)" vertical={false} /><XAxis dataKey="month" tick={{ fill: "var(--text-muted)", fontSize: 11 }} /><YAxis tick={{ fill: "var(--text-muted)", fontSize: 11 }} allowDecimals={false} /><Tooltip contentStyle={{ background: "var(--surface-raised)", border: "1px solid var(--border)" }} /><Line type="monotone" dataKey="commits" name="Commits" stroke="var(--accent)" strokeWidth={2} dot={false} activeDot={{ r: 4 }} /></LineChart></ResponsiveContainer></div><ul className="chart-text-list">{months.map((item) => <li key={item.month}>{item.month}: {item.commits} commits</li>)}</ul></> : <p className="empty-inline">No monthly commit data is available.</p>}</article></div> : null}
      {activity?.contributors ? <article className="activity-panel contributor-summary"><h3>Contributors</h3><div className="activity-stats"><p><b>{activity.contributors.total_contributors ?? activity.contributors.total ?? 0}</b><span>Contributors</span></p><p><b>{activity.contributors.total_contributions ?? 0}</b><span>Total contributions</span></p></div>{activity.contributors.top_contributor ? <p>Top contributor: <b>{activity.contributors.top_contributor.username}</b> ({activity.contributors.top_contributor.contributions} contributions)</p> : null}</article> : null}
    </section>
  </div>;
}
