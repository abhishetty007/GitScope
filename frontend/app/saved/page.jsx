import Link from "next/link";
import { redirect } from "next/navigation";
import Header from "../../src/components/layout/Header";
import MutationButton from "../../src/components/saved/MutationButton";
import { getCurrentUser } from "../../src/lib/current-user";
import { loginHref } from "../../src/utils/auth-redirect.js";
import { getDb } from "../../src/lib/db";
import { calculateGrade } from "../../src/utils/gradeCalculator";

export const dynamic = "force-dynamic";

export const metadata = {
  title: "Saved analyses",
  robots: { index: false, follow: false },
};

export default async function SavedAnalysesPage() {
  const user = await getCurrentUser();
  if (!user) redirect(loginHref("/saved"));
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
                    {analysis.result.repository.full_name || `${analysis.repository.ownerLogin}/${analysis.repository.name}`}
                  </h2>
                  <p>Score <b>{analysis.score ?? "N/A"}</b><span className="account-separator">·</span> Grade <b>{calculateGrade(analysis.score)}</b><span className="account-separator">·</span> Saved {new Date(createdAt).toLocaleDateString()}</p>
                </div>
                <div className="account-actions"><Link className="button button-secondary" href={`/saved/${analysis.id}`}>Open snapshot <span aria-hidden="true">→</span></Link><MutationButton endpoint={`/api/saved-analyses/${analysis.id}`} label="Remove saved analysis" /></div>
              </li>
            ))}
          </ul>
        ) : <section className="empty-state-panel"><span className="empty-state-icon" aria-hidden="true">◷</span><h2>No saved analyses yet</h2><p>Saved analyses are private snapshots you can return to later. Run a repository analysis and save it to start your collection.</p><Link className="button button-primary" href="/">Analyze a repository <span aria-hidden="true">→</span></Link></section>}
      </main>
    </>
  );
}
