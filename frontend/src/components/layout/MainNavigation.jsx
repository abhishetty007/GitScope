"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const links = [
  { href: "/", label: "Analyze", primary: true },
  { href: "/saved", label: "Saved" },
  { href: "/tracked", label: "Tracked" },
  { href: "/users/octocat", label: "User analytics", prefix: "/users/" },
];

export default function MainNavigation() {
  const pathname = usePathname();
  return <nav className="header-links" aria-label="Main navigation">
    {links.map(({ href, label, primary, prefix }) => {
      const active = prefix ? pathname.startsWith(prefix) : primary ? pathname === "/" || pathname.startsWith("/repos/") : pathname === href || pathname.startsWith(`${href}/`);
      return <Link className={`${primary ? "nav-primary " : ""}${active ? "is-active" : ""}`} href={href} aria-current={active ? "page" : undefined} key={href}>{label}</Link>;
    })}
  </nav>;
}
