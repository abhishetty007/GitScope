import { notFound, redirect } from "next/navigation";
import Link from "next/link";
import Header from "../../../src/components/layout/Header";
import MutationButton from "../../../src/components/saved/MutationButton";
import { getCurrentUser } from "../../../src/lib/current-user";
import { getSavedAnalysis } from "../../../src/lib/user-data";
import { calculateGrade } from "../../../src/utils/gradeCalculator";
import { loginHref } from "../../../src/utils/auth-redirect.js";

export const dynamic = "force-dynamic";

export async function generateMetadata({ params }) {
  const { analysisId } = await params;
  return { title: `Saved analysis ${analysisId.slice(0, 8)}`, robots: { index: false, follow: false } };
}

export default async function SavedAnalysisPage({ params }) {
  const { analysisId } = await params;
  if (!/^[0-9a-f-]{36}$/i.test(analysisId)) notFound();
  const user = await getCurrentUser();
  if (!user) redirect(loginHref(`/saved/${analysisId}`));

  const saved = await getSavedAnalysis(user.id, analysisId);
  if (!saved) notFound();
  const { result, score } = saved.analysis;
  const repository = result.repository;

  return (
    <>
      <Header />
      <main className="container account-page saved-detail">
        <p className="back-link"><Link href="/saved">← Saved analyses</Link></p>
        <p className="eyebrow">Saved snapshot · Not automatically refreshed</p>
        <h1 className="page-title">{repository.full_name}</h1>
        <p>{repository.description || "No description available."}</p>
        <p>Saved snapshot · {new Date(saved.createdAt).toLocaleDateString()}</p>
        <section className="saved-score" aria-label="Engineering health score">
          <span className="micro-label">ENGINEERING HEALTH</span><strong>{score ?? "N/A"}<small> / 100</small></strong><span className="grade-label">Grade <b>{calculateGrade(score)}</b></span>
          <p>{result.health.summary}</p>
        </section>
        <div className="snapshot-actions"><Link className="button button-secondary" href={`/repos/${encodeURIComponent(saved.analysis.repository.ownerLogin)}/${encodeURIComponent(saved.analysis.repository.name)}`}>Open live repository analysis <span aria-hidden="true">→</span></Link></div>
        <h2>Category results</h2>
        <ul className="account-list">
          {Object.entries(result.health.categories || {}).map(([key, category]) => (
            <li className="account-card saved-category" key={key}>
              <div>
                <h3>{category.label}</h3>
                    <p>{category.score ?? "N/A"} / {category.max_score}</p>
                {category.checks.map((check, index) => (
                  <p key={`${check.name}-${index}`}>
                    <strong>{check.name}</strong> · {check.status}: {check.evidence}
                  </p>
                ))}
              </div>
            </li>
          ))}
        </ul>
        <MutationButton endpoint={`/api/saved-analyses/${analysisId}`} label="Delete saved analysis" />
      </main>
    </>
  );
}
