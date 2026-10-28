"use client";

import { useState } from "react";

const steps = [
  {
    id: "repository",
    label: "Repository",
    eyebrow: "01 · SOURCE",
    title: "Start with the repository.",
    description: "A public GitHub repository is the source for the assessment. Repository identity and available signals provide the context for what follows.",
    detail: "Repository → observable source context",
  },
  {
    id: "evidence",
    label: "Evidence",
    eyebrow: "02 · OBSERVABLE SIGNALS",
    title: "Inspect the evidence.",
    description: "Category checks surface evidence from the repository so a result can be understood in context.",
    detail: "Illustrative example only: README.md detected",
  },
  {
    id: "analysis",
    label: "Analysis",
    eyebrow: "03 · DETERMINISTIC CHECKS",
    title: "See how signals are grouped.",
    description: "Deterministic checks organize observed signals into the existing engineering categories. The scoring model stays fixed.",
    detail: "Signals → checks → category results",
  },
  {
    id: "health",
    label: "Engineering Health",
    eyebrow: "04 · RESULT",
    title: "Read the health assessment.",
    description: "The result brings the Engineering Health score together with category results, evidence, strengths, concerns, and supplied recommendations.",
    categories: ["Code & Structure", "Testing & Reliability", "Documentation", "Security & Dependencies", "Maintenance", "Collaboration"],
  },
];

export default function InteractiveJourney() {
  const [activeId, setActiveId] = useState(steps[0].id);
  const active = steps.find((step) => step.id === activeId) || steps[0];

  return (
    <div className="journey-explorer">
      <div className="journey-steps" role="group" aria-label="Explore how GitScope analyzes a repository">
        {steps.map((step, index) => <button className={`journey-step ${activeId === step.id ? "is-selected" : ""}`} type="button" key={step.id} aria-pressed={activeId === step.id} aria-controls="journey-detail" onClick={() => setActiveId(step.id)}>
          <span className="journey-step-index">0{index + 1}</span><span className="journey-step-label">{step.label}</span><span className="journey-step-arrow" aria-hidden="true">↗</span>
        </button>)}
      </div>
      <section className="journey-detail" id="journey-detail" aria-live="polite" aria-atomic="true">
        <div><p className="eyebrow">{active.eyebrow}</p><h3>{active.title}</h3><p>{active.description}</p></div>
        {active.categories ? <ul className="journey-category-list" aria-label="Engineering Health categories">{active.categories.map((category) => <li key={category}>{category}</li>)}</ul> : <p className={`journey-detail-sample ${active.id === "evidence" ? "is-illustrative" : ""}`}>{active.id === "evidence" ? <><span>ILLUSTRATIVE ONLY</span>{active.detail}</> : active.detail}</p>}
      </section>
    </div>
  );
}
