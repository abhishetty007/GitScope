import Link from "next/link";
import { redirect } from "next/navigation";
import Header from "../../src/components/layout/Header";
import MutationButton from "../../src/components/saved/MutationButton";
import { getCurrentUser } from "../../src/lib/current-user";
import { getDb } from "../../src/lib/db";

export const dynamic = "force-dynamic";

export const metadata = { title: "Saved analyses" };

export default async function SavedAnalysesPage() {
  const user = await getCurrentUser();
  if (!user) redirect("/auth/login?returnTo=%2Fsaved");
  const db = getDb();
  const saved = await db.savedAnalysis.findMany({
    where: { userId: user.id },
    orderBy: { createdAt: "desc" },
    take: 100,
    select: {
      createdAt: true,
      analysis: {
        select: {
          id: true,
          score: true,
          createdAt: true,
          result: true,
          repository: { select: { ownerLogin: true, name: true } },
        },
      },
    },
  });

  return (
    <>
      <Header />
      <main className="container account-page">
        <h1 className="page-title">Saved analyses</h1>
        <p>Saved public analysis snapshots are private to your GitScope account.</p>
        {saved.length ? (
          <ul className="account-list">
            {saved.map(({ createdAt, analysis }) => (
              <li className="account-card" key={analysis.id}>
                <div>
                  <h2>
                    <Link href={`/saved/${analysis.id}`}>
                      {analysis.result.repository.full_name || `${analysis.repository.ownerLogin}/${analysis.repository.name}`}
                    </Link>
                  </h2>
                  <p>Score: {analysis.score ?? "Not available"} · Saved {new Date(createdAt).toLocaleDateString()}</p>
                </div>
                <MutationButton endpoint={`/api/saved-analyses/${analysis.id}`} label="Remove saved analysis" />
              </li>
            ))}
          </ul>
        ) : <p>You have not saved any analyses yet.</p>}
      </main>
    </>
  );
}
