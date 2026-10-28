import Link from "next/link";
import { getAuth0 } from "../../lib/auth0.js";
import MobileNavigation from "./MobileNavigation";
import MainNavigation from "./MainNavigation";

async function Header() {
  let signedIn = false;
  let displayName = "";
  try {
    const session = await getAuth0()?.getSession();
    signedIn = Boolean(session?.user?.sub);
    displayName = session?.user?.name || session?.user?.email || "Account";
  } catch {
    // Keep navigation available when the identity provider is temporarily unavailable.
  }
  return (
    <header className="header" id="top">
      <div className="header-inner">
        <Link className="brand" href="/" aria-label="GitScope home"><span className="brand-mark" aria-hidden="true">G</span><span>GitScope</span></Link>
        <MainNavigation />
        <div className="header-account">
          {signedIn ? <><span className="account-link">{displayName}</span><a className="account-link" href="/auth/logout">Sign out</a></> : <a className="account-link" href="/auth/login">Sign in</a>}
        </div>
        <MobileNavigation signedIn={signedIn} />
      </div>
    </header>
  );
}

export default Header;
