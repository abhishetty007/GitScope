export default function PageLoading() {
  return (
    <main className="container loading-state" aria-busy="true" aria-live="polite">
      <p className="loading-label">Loading analysis</p>
      <div className="skeleton skeleton-line" style={{ width: "36%" }} />
      <div className="skeleton skeleton-line" style={{ width: "62%", height: "28px" }} />
      <div className="skeleton skeleton-block" />
      <p className="sr-only">Loading GitScope data…</p>
    </main>
  );
}
