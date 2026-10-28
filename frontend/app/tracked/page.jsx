import Link from "next/link";
import { redirect } from "next/navigation";
import Header from "../../src/components/layout/Header";
import MutationButton from "../../src/components/saved/MutationButton";
import TrackRepositoryForm from "../../src/components/tracked/TrackRepositoryForm";
import { getCurrentUser } from "../../src/lib/current-user";
import { loginHref } from "../../src/utils/auth-redirect.js";
import { getDb } from "../../src/lib/db";

export const dynamic = "force-dynamic";

export const metadata = {
  title: "Tracked repositories",
  robots: { index: false, follow: false },
};

export default async function TrackedRepositoriesPage() {
  const user = await getCurrentUser();
  if (!user) redirect(loginHref("/tracked"));
  const tracked = await getDb().trackedRepository.findMany({
    where: { userId: user.id },
    orderBy: { createdAt: "desc" },
    select: {
      createdAt: true,
      repository: {
        select: {
          id: true,
          ownerLogin: true,
          name: true,
          visibility: true,
        },
      },
    },
  });

  return (
    <>
      <Header />
      <main className="container account-page">
        <h1 className="page-title">Tracked repositories</h1>
        <p>Track public repositories for quick access. Tracking does not grant private repository access.</p>
        <TrackRepositoryForm />
        {tracked.length ? (
          <ul className="account-list">
            {tracked.map(({ createdAt, repository }) => (
              <li className="account-card" key={repository.id}>
                <div>
                  <h2>
                    <Link href={`/repos/${encodeURIComponent(repository.ownerLogin)}/${encodeURIComponent(repository.name)}`}>
                      {repository.ownerLogin}/{repository.name}
                    </Link>
                  </h2>
                  <p>Public repository · Tracked {new Date(createdAt).toLocaleDateString()}</p>
                </div>
                <div className="account-actions"><Link className="button button-primary" href={`/repos/${encodeURIComponent(repository.ownerLogin)}/${encodeURIComponent(repository.name)}`}>Analyze repository <span aria-hidden="true">→</span></Link><MutationButton
                  endpoint={`/api/tracked-repositories/${repository.id}`}
                  label="Untrack"
                /></div>
              </li>
            ))}
          </ul>
        ) : <section className="empty-state-panel"><span className="empty-state-icon" aria-hidden="true">⌖</span><h2>No tracked repositories yet</h2><p>Tracking keeps public repositories close at hand. It does not grant access to private repositories.</p><p>Enter a public <code>owner/name</code> above, or start with an analysis.</p><Link className="button button-secondary" href="/">Analyze a repository <span aria-hidden="true">→</span></Link></section>}
      </main>
    </>
  );
}
