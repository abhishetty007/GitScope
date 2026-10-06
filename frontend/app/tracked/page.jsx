import Link from "next/link";
import { redirect } from "next/navigation";
import Header from "../../src/components/layout/Header";
import MutationButton from "../../src/components/saved/MutationButton";
import TrackRepositoryForm from "../../src/components/tracked/TrackRepositoryForm";
import { getCurrentUser } from "../../src/lib/current-user";
import { getDb } from "../../src/lib/db";

export const dynamic = "force-dynamic";

export const metadata = { title: "Tracked repositories" };

export default async function TrackedRepositoriesPage() {
  const user = await getCurrentUser();
  if (!user) redirect("/auth/login?returnTo=%2Ftracked");
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
                  <p>Public · Tracked {new Date(createdAt).toLocaleDateString()}</p>
                </div>
                <MutationButton
                  endpoint={`/api/tracked-repositories/${repository.id}`}
                  label="Untrack"
                />
              </li>
            ))}
          </ul>
        ) : <p>You are not tracking any repositories yet.</p>}
      </main>
    </>
  );
}
