function SearchSection({
  username,
  setUsername,
  onAnalyze,
  loading,
  error,
}) {
  return (
    <section className="search-card">
      <h2>Analyze a GitHub User</h2>

      <div className="search-box">
        <input
          type="text"
          placeholder="Enter GitHub username"
          value={username}
          onChange={(event) => setUsername(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter") {
              onAnalyze();
            }
          }}
        />

        <button onClick={onAnalyze} disabled={loading}>
          {loading ? "Analyzing..." : "Analyze"}
        </button>
      </div>

      {error && <p className="error">{error}</p>}
    </section>
  );
}

export default SearchSection;

