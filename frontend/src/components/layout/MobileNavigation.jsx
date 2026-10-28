"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { usePathname } from "next/navigation";

export default function MobileNavigation({ signedIn }) {
  const [open, setOpen] = useState(false);
  const pathname = usePathname();
  useEffect(() => {
    if (!open) return;
    const onKeyDown = (event) => { if (event.key === "Escape") setOpen(false); };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [open]);
  return (
    <div className="mobile-navigation">
      <button className="mobile-menu-button" type="button" aria-expanded={open} aria-controls="mobile-menu" onClick={() => setOpen((value) => !value)}>
        <span>{open ? "Close" : "Menu"}</span><span aria-hidden="true">{open ? "×" : "☰"}</span>
      </button>
      <nav className={`mobile-menu ${open ? "is-open" : ""}`} id="mobile-menu" aria-label="Main navigation" aria-hidden={!open} inert={!open}>
        <Link aria-current={pathname === "/" || pathname.startsWith("/repos/") ? "page" : undefined} href="/" onClick={() => setOpen(false)}>Analyze repository</Link>
        <Link aria-current={pathname.startsWith("/saved") ? "page" : undefined} href="/saved" onClick={() => setOpen(false)}>Saved analyses</Link>
        <Link aria-current={pathname.startsWith("/tracked") ? "page" : undefined} href="/tracked" onClick={() => setOpen(false)}>Tracked repositories</Link>
        <Link aria-current={pathname.startsWith("/users/") ? "page" : undefined} href="/users/octocat" onClick={() => setOpen(false)}>User analytics</Link>
        <a href={signedIn ? "/auth/logout" : "/auth/login"}>{signedIn ? "Sign out" : "Sign in"}</a>
      </nav>
    </div>
  );
}
