import Header from "../../../src/components/layout/Header";
import Link from "next/link";

export const metadata = {
  title: "Sign in unavailable | GitScope",
  robots: { index: false, follow: false },
};

export default function LoginUnavailablePage() {
  return (
    <>
      <Header />
      <main className="container not-found-page">
        <p className="eyebrow">Account access</p>
        <h1>Sign-in isn’t configured for this environment.</h1>
        <p>GitScope account features need an Auth0 connection. Configure the Auth0 application settings for this environment, then try again.</p>
        <div className="not-found-actions">
          <Link className="button button-primary" href="/">Back to GitScope <span aria-hidden="true">→</span></Link>
          <Link className="button button-secondary" href="/#repo-search-main">Analyze a public repository</Link>
        </div>
      </main>
    </>
  );
}
