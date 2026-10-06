import Link from "next/link";

function Header() {
  return (
    <header className="header">
      <div>
        <Link className="brand-title" href="/">GitScope</Link>
        <p className="brand-tagline">Evidence-Driven GitHub Engineering Health Analyzer</p>
      </div>
    </header>
  );
}

export default Header;
