"use client";

import { useState, useTransition } from "react";
import { useRouter } from "next/navigation";
import { parseGitHubTarget } from "../../utils/github-target.js";

export default function RepositorySearchForm() {
  const [value, setValue] = useState("");
  const [error, setError] = useState("");
  const [targetKind, setTargetKind] = useState("");
  const [pending, startTransition] = useTransition();
  const router = useRouter();

  function submit(event) {
    event.preventDefault();
    const target = parseGitHubTarget(value);
    if (!target) {
      setError("Use a username such as octocat, owner/repository such as facebook/react, or a GitHub profile or repository URL.");
      return;
    }
    setError("");
    setTargetKind(target.kind);
    const destination = target.kind === "profile"
      ? `/users/${encodeURIComponent(target.username)}`
      : `/repos/${encodeURIComponent(target.owner)}/${encodeURIComponent(target.repository)}`;
    startTransition(() => router.push(destination));
  }

  return (
    <form className="repo-search" onSubmit={submit}>
      <label className="repo-search-label" htmlFor="repo-search-main">Analyze a GitHub profile or repository</label>
      <div className="repo-search-row">
        <span className="repo-search-prefix" aria-hidden="true">↗</span>
        <input id="repo-search-main" value={value} onChange={(event) => { setValue(event.target.value); if (error) setError(""); }} placeholder="username or owner/repository" autoComplete="off" aria-invalid={Boolean(error)} aria-describedby={error ? "repo-search-error" : undefined} />
        <button className="button button-primary" type="submit" disabled={pending}>{pending ? targetKind === "profile" ? "Opening profile…" : "Opening analysis…" : "Analyze GitHub"}<span aria-hidden="true">→</span></button>
      </div>
      {error ? <p className="form-message form-error" id="repo-search-error" role="alert">{error}</p> : null}
    </form>
  );
}
