import { notFound } from "next/navigation";
import Header from "../../../../src/components/layout/Header";
import ApiErrorState from "../../../../src/components/layout/ApiErrorState";
import RepositoryAnalyticsClient from "../../../../src/components/dashboard/RepositoryAnalyticsClient";
import SaveAnalysisButton from "../../../../src/components/saved/SaveAnalysisButton";
import { getRepositoryAnalyticsPageData } from "../../../../src/services/server-data";
import { safeMetadataText } from "../../../../src/services/seo";

export const dynamic = "force-dynamic";

export async function generateMetadata({ params }) {
  const { owner: rawOwner, repository: rawRepository } = await params;
  const owner = safeMetadataText(rawOwner, 39) || "GitHub owner";
  const repository = safeMetadataText(rawRepository, 100) || "repository";
  let description = `Evidence-based engineering health analysis for the public GitHub repository ${owner}/${repository}.`;
  try {
    const data = await getRepositoryAnalyticsPageData(rawOwner, rawRepository);
    description = safeMetadataText(data.health?.summary, 200) || description;
  } catch {
    // Keep fallback metadata available during API errors and not-found responses.
  }
  const title = `${owner}/${repository} engineering health`;
  const path = `/repos/${encodeURIComponent(rawOwner)}/${encodeURIComponent(rawRepository)}`;
  return {
    title,
    description,
    alternates: { canonical: path },
    robots: { index: false, follow: true },
    openGraph: { type: "article", title, description },
    twitter: { card: "summary", title, description },
  };
}

export default async function RepositoryAnalyticsPage({ params }) {
  const { owner, repository } = await params;
  let data;
  try {
    data = await getRepositoryAnalyticsPageData(owner, repository);
  } catch (error) {
    if (error.status === 404) notFound();
    return (
      <>
        <Header />
        <main className="container">
          <h1 className="page-title">Engineering health: {owner}/{repository}</h1>
          <ApiErrorState message={error.message} />
        </main>
      </>
    );
  }
  const fullName = data.repository.full_name || `${owner}/${repository}`;
  return (
    <>
      <Header />
      <main className="container">
        <h1 className="page-title">Engineering health: {fullName}</h1>
        <SaveAnalysisButton owner={owner} repository={repository} />
        <RepositoryAnalyticsClient data={data} />
      </main>
    </>
  );
}
