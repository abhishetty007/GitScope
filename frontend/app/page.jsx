import Header from "../src/components/layout/Header";
import Link from "next/link";
import RepositorySearchForm from "../src/components/search/RepositorySearchForm";
import LandingMotion from "../src/components/layout/LandingMotion";
import InteractiveJourney from "../src/components/landing/InteractiveJourney";

export const metadata = {
  title: "GitHub Engineering Health Analytics",
  description: "Analyze public GitHub profiles and repositories with transparent, evidence-driven engineering health signals.",
  alternates: { canonical: "/" },
  openGraph: {
    title: "GitScope — GitHub Engineering Health Analytics",
    description: "Evidence-driven health insights for public GitHub repositories.",
    type: "website",
  },
};

export default function HomePage() {
  return (
    <>
      <Header />
      <LandingMotion>
      <main className="landing-page">
        <section className="landing-hero container" aria-labelledby="landing-title" data-reveal>
          <div className="hero-copy">
            <p className="eyebrow"><span className="eyebrow-mark" aria-hidden="true">●</span> Evidence-driven GitHub profile and repository analysis</p>
            <h1 id="landing-title">Make your GitHub repository’s engineering health <span>visible.</span></h1>
            <p className="landing-copy">GitScope evaluates observable repository signals and turns them into an explainable Engineering Health score, with the evidence behind every result.</p>
            <RepositorySearchForm />
            <p className="hero-note">Public repositories · Deterministic signals · Evidence you can inspect</p>
            <p className="secondary-entry">Looking for a contributor overview? <Link href="/users/octocat">Explore user analytics <span aria-hidden="true">→</span></Link></p>
          </div>
          <div className="hero-aside" aria-hidden="true">
            <div className="hero-orbit orbit-one" /><div className="hero-orbit orbit-two" />
            <div className="hero-node node-a">01 <span>repository</span></div><div className="hero-node node-b">02 <span>evidence</span></div><div className="hero-node node-c">03 <span>analysis</span></div>
            <div className="hero-core"><span className="core-mark">G</span><span>ENGINEERING<br/>HEALTH</span><i /></div>
          </div>
        </section>

        <section className="preview-section section-shell" aria-labelledby="preview-title" data-reveal>
          <div className="section-heading"><div><p className="eyebrow">A clearer read on code health</p><h2 id="preview-title">Signals with a source.</h2></div><span className="preview-label">Illustrative product preview</span></div>
          <div className="analysis-preview">
            <div className="preview-topline"><span className="repo-crumb"><span className="repo-glyph">⌘</span> example / repository</span><span className="preview-status"><i /> ILLUSTRATIVE SAMPLE · NOT A REAL RESULT</span></div>
            <div className="preview-body">
              <div className="preview-score"><span className="micro-label">ENGINEERING HEALTH · SAMPLE</span><div className="score-line"><strong>92<small> / 100</small></strong><span className="grade-chip">GRADE A+</span></div><p>Example score to show how an analysis result is presented.</p><div className="score-track"><span /></div><div className="track-labels"><span>0</span><span>100</span></div></div>
              <div className="preview-categories"><div className="micro-label">CATEGORY BREAKDOWN <span>6 SIGNAL GROUPS</span></div>
                {["Code & Structure", "Testing & Reliability", "Documentation", "Security & Dependencies", "Maintenance", "Collaboration"].map((name, index) => <div className="preview-category" key={name}><span className="category-index">0{index + 1}</span><span>{name}</span><span className="preview-na">Example</span></div>)}
              </div>
            </div>
            <div className="preview-evidence"><span className="evidence-icon" aria-hidden="true">↳</span><span><b>Example evidence:</b> README detected · test directory present</span><span className="evidence-tag">SAMPLE ONLY</span></div>
          </div>
        </section>

        <section className="method-section section-shell" id="methodology" aria-labelledby="method-title" data-reveal>
          <div className="section-heading"><div><p className="eyebrow">From repository to useful context</p><h2 id="method-title">A result you can trace.</h2></div><p className="section-intro">A transparent path from observable signals to a score and practical next steps.</p></div>
          <ol className="method-steps"><li><span>01</span><h3>Repository</h3><p>Start with a public GitHub repository.</p></li><li><span>02</span><h3>Evidence</h3><p>Review observable files, signals, and activity.</p></li><li><span>03</span><h3>Deterministic analysis</h3><p>Signals are evaluated using consistent rules.</p></li><li><span>04</span><h3>Health score</h3><p>See category results and the evidence behind them.</p></li><li><span>05</span><h3>Recommendations</h3><p>Find supplied actions tied to the assessment.</p></li></ol>
          <InteractiveJourney />
        </section>

        <section className="categories-section section-shell" aria-labelledby="categories-title" data-reveal>
          <div className="section-heading"><div><p className="eyebrow">Six dimensions of project health</p><h2 id="categories-title">See the engineering signals.</h2></div><p className="section-intro">Category results keep the score legible and show where evidence is strong, missing, or not applicable.</p></div>
          <div className="category-grid">{[["01", "Code & Structure", "Repository organization and foundational signals."], ["02", "Testing & Reliability", "Signals related to test coverage and reliability."], ["03", "Documentation", "The presence and shape of project guidance."], ["04", "Security & Dependencies", "Observable security and dependency signals."], ["05", "Maintenance", "Repository maintenance and activity context."], ["06", "Collaboration", "Signals related to contributions and collaboration."]].map(([n, title, body]) => <article className="category-tile" key={n}><span className="tile-index">{n}</span><span className="tile-arrow" aria-hidden="true">↗</span><h3>{title}</h3><p>{body}</p></article>)}</div>
        </section>

        <section className="evidence-section section-shell" aria-labelledby="evidence-title" data-reveal><div className="evidence-copy"><p className="eyebrow">No black box</p><h2 id="evidence-title">A score should come with receipts.</h2><p>GitScope presents observable evidence alongside category results, so you can understand what contributed to an assessment and where a signal was not available.</p></div><div className="evidence-points"><p><span>01</span><b>Observable signals</b><small>Grounded in repository data.</small></p><p><span>02</span><b>Explainable results</b><small>Category scores with check-level evidence.</small></p><p><span>03</span><b>Useful next steps</b><small>Recommendations supplied by the analysis.</small></p></div></section>

        <section className="user-analytics-callout section-shell" data-reveal><div><p className="eyebrow">Also available</p><h2>Explore a GitHub profile.</h2><p>Review public profile analytics and repositories, then open an engineering analysis for a repository.</p></div><Link className="button button-secondary" href="/users/octocat">Open user analytics <span aria-hidden="true">→</span></Link></section>
        <section className="final-cta section-shell" data-reveal><p className="eyebrow">Start with a GitHub profile or repository</p><h2>Make the signals easier to see.</h2><Link className="button button-primary final-cta-link" href="#repo-search-main">Analyze a profile or repository <span aria-hidden="true">↑</span></Link></section>
      </main>
      <footer className="site-footer"><div className="footer-inner"><Link className="brand footer-brand" href="/"><span className="brand-mark" aria-hidden="true">G</span><span>GitScope</span></Link><p>Evidence-driven GitHub engineering health.</p><nav aria-label="Footer navigation"><Link href="/">Analyze</Link><Link href="/#methodology">Methodology</Link><Link href="/saved">Saved analyses</Link><Link href="/tracked">Tracked repositories</Link></nav><span className="footer-meta">Built for clearer engineering context.</span></div></footer>
      </LandingMotion>
    </>
  );
}
