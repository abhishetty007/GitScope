import { useState } from "react";
import Header from "./components/layout/Header";
import SearchSection from "./components/search/SearchSection";
import UserProfileCard from "./components/dashboard/UserProfileCard";
import ProfileAnalytics from "./components/dashboard/ProfileAnalytics";
import RepositoryGrid from "./components/dashboard/RepositoryGrid";
import HealthDashboard from "./components/dashboard/HealthDashboard";
import {
  fetchUser,
  fetchUserAnalytics,
  fetchUserRepositories,
  fetchRepositoryAnalytics,
} from "./services/api";
import "./App.css";

function App() {
  const [username, setUsername] = useState("");
  const [user, setUser] = useState(null);
  const [analytics, setAnalytics] = useState(null);
  const [repositories, setRepositories] = useState([]);
  const [repositoryAnalytics, setRepositoryAnalytics] = useState(null);

  const [loading, setLoading] = useState(false);
  const [analyzingRepository, setAnalyzingRepository] = useState("");

  const [error, setError] = useState("");
  const [repositoryError, setRepositoryError] = useState("");

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
    setRepositoryAnalytics(null);
    setRepositoryError("");
    setAnalyzingRepository("");

    try {
      const usernameValue = username.trim();

      const [userData, analyticsData, repositoriesData] = await Promise.all([
        fetchUser(usernameValue),
        fetchUserAnalytics(usernameValue),
        fetchUserRepositories(usernameValue),
      ]);

      setUser(userData);
      setAnalytics(analyticsData);
      setRepositories(repositoriesData);
    } catch (err) {
      setError(err.message || "An error occurred while fetching user data.");
    } finally {
      setLoading(false);
    }
  };

  const analyzeRepository = async (repo) => {
    setAnalyzingRepository(repo.full_name);
    setRepositoryError("");
    setRepositoryAnalytics(null);

    try {
      const [owner, repositoryName] = repo.full_name.split("/");
      const data = await fetchRepositoryAnalytics(owner, repositoryName);
      setRepositoryAnalytics(data);
    } catch (err) {
      setRepositoryError(err.message || "An error occurred while analyzing repository.");
    } finally {
      setAnalyzingRepository("");
    }
  };

  return (
    <div className="app">
      <Header />

      <main className="container">
        <SearchSection
          username={username}
          setUsername={setUsername}
          onAnalyze={analyzeUser}
          loading={loading}
          error={error}
        />

        <UserProfileCard user={user} />

        <ProfileAnalytics
          analytics={analytics}
          username={username.trim()}
          onAnalyzeRepo={analyzeRepository}
          analyzingRepo={analyzingRepository}
        />

        <RepositoryGrid
          repositories={repositories}
          onAnalyzeRepo={analyzeRepository}
          analyzingRepo={analyzingRepository}
        />

        <HealthDashboard
          data={repositoryAnalytics}
          error={repositoryError}
        />
      </main>
    </div>
  );
}

export default App;