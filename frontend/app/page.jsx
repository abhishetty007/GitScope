import Header from "../src/components/layout/Header";
import UserSearchForm from "../src/components/search/UserSearchForm";

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
      <main className="container landing-page">
        <section className="landing-hero" aria-labelledby="landing-title">
          <p className="eyebrow">Transparent repository intelligence</p>
          <h1 id="landing-title">Understand the health behind a GitHub project.</h1>
          <p className="landing-copy">
            GitScope evaluates public repository evidence across structure, testing,
            documentation, security, maintenance, and collaboration.
          </p>
          <UserSearchForm />
        </section>
        <section className="landing-details" aria-labelledby="method-title">
          <h2 id="method-title">Evidence first. Scores you can inspect.</h2>
          <p>
            Every signal links back to observable repository evidence. GitScope keeps
            its six engineering categories and presents missing evidence as not
            applicable where appropriate.
          </p>
        </section>
      </main>
    </>
  );
}
