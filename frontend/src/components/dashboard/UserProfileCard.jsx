function UserProfileCard({ user }) {
  if (!user) return null;

  return (
    <section className="profile-card">
      <img src={user.avatar_url} alt={user.login} className="avatar" />

      <div className="profile-info">
        <h2>{user.name || user.login}</h2>

        <p className="username">@{user.login}</p>

        <p>{user.bio || "No bio available."}</p>

        <div className="profile-stats">
          <span>
            <strong>{user.public_repos}</strong>
            Repositories
          </span>

          <span>
            <strong>{user.followers}</strong>
            Followers
          </span>

          <span>
            <strong>{user.following}</strong>
            Following
          </span>
        </div>
      </div>
    </section>
  );
}

export default UserProfileCard;

