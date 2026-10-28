import Header from "../src/components/layout/Header";
import Link from "next/link";

export default function NotFound() {
  return (
    <>
      <Header />
      <main className="container not-found-page">
        <div className="not-found-code" aria-hidden="true">404</div>
        <p className="eyebrow">Route not found</p>
        <h1>This page doesn’t exist.</h1>
        <p>The GitHub profile, repository, or page you requested couldn’t be found. Check the address, or start a new analysis.</p>
        <div className="not-found-actions"><Link className="button button-primary" href="/">Back to GitScope <span aria-hidden="true">→</span></Link><Link className="button button-secondary" href="/#repo-search-main">Analyze a profile or repository</Link></div>
      </main>
    </>
  );
}
