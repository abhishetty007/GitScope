"use client";

import { useEffect, useRef } from "react";

export default function LandingMotion({ children }) {
  const root = useRef(null);

  useEffect(() => {
    const node = root.current;
    if (!node || !("IntersectionObserver" in window) || window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;

    const targets = node.querySelectorAll("[data-reveal]");
    node.classList.add("motion-ready");
    const observer = new IntersectionObserver((entries) => {
      entries.forEach((entry) => {
        if (!entry.isIntersecting) return;
        entry.target.classList.add("is-revealed");
        observer.unobserve(entry.target);
      });
    }, { threshold: 0.12, rootMargin: "0px 0px -5% 0px" });

    targets.forEach((target) => observer.observe(target));
    return () => observer.disconnect();
  }, []);

  return <div className="landing-motion-shell" ref={root}>{children}</div>;
}
