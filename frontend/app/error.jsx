"use client";

export default function ErrorPage({ error, reset }) {
  return (
    <main className="container error-page" role="alert">
      <h1>GitHub data could not be loaded</h1>
      <p>{error?.message || "The GitScope API is temporarily unavailable."}</p>
      <button type="button" onClick={reset}>Try again</button>
    </main>
  );
}
