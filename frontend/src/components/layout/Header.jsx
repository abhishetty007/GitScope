import Link from "next/link";

function Header() {
  return (
    <header className="header">
      <div>
        <Link className="brand-title" href="/">GitScope</Link>
        <p className="brand-tagline">Evidence-Driven GitHub Engineering Health Analyzer</p>
      </div>
      <nav className="header-links" aria-label="Account">
        <Link href="/saved">Saved analyses</Link>
        <Link href="/tracked">Tracked repositories</Link>
        <a href="/auth/login">Sign in</a>
      </nav>
    </header>
  );
}

export default Header;
