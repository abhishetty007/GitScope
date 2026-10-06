import { notFound } from "next/navigation";
import Header from "../../../src/components/layout/Header";
import ApiErrorState from "../../../src/components/layout/ApiErrorState";
import UserAnalyticsClient from "../../../src/components/dashboard/UserAnalyticsClient";
import { getUserAnalyticsPageData } from "../../../src/services/server-data";
import { safeMetadataText } from "../../../src/services/seo";

export const dynamic = "force-dynamic";

export async function generateMetadata({ params }) {
  const { username: rawUsername } = await params;
  const username = safeMetadataText(rawUsername, 39) || "GitHub user";
  let userName = username;
  try {
    const data = await getUserAnalyticsPageData(rawUsername);
    userName = safeMetadataText(data.user.name || data.user.login || username, 100);
  } catch {
    // Keep a useful, non-indexable title even if the API is unavailable.
  }
  const description = `Public GitHub profile analytics and repository overview for ${userName}.`;
  const path = `/users/${encodeURIComponent(rawUsername)}`;
  return {
    title: `GitHub analytics for ${userName}`,
    description,
    alternates: { canonical: path },
    robots: { index: false, follow: true },
    openGraph: { type: "profile", title: `GitHub analytics for ${userName}`, description },
    twitter: { card: "summary", title: `GitHub analytics for ${userName}`, description },
  };
}

export default async function UserAnalyticsPage({ params }) {
  const { username } = await params;
  let data;
  try {
    data = await getUserAnalyticsPageData(username);
  } catch (error) {
    if (error.status === 404) notFound();
    return (
      <>
        <Header />
        <main className="container">
          <h1 className="page-title">GitHub analytics for @{username}</h1>
          <ApiErrorState message={error.message} />
        </main>
      </>
    );
  }
  return (
    <>
      <Header />
      <main className="container">
        <h1 className="page-title">GitHub analytics for @{data.user.login || username}</h1>
        <UserAnalyticsClient username={data.user.login || username} {...data} />
      </main>
    </>
  );
}
