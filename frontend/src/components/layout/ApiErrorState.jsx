"use client";

import { useTransition } from "react";
import { useRouter } from "next/navigation";
import { getRateLimitPresentation } from "./rate-limit-presentation.js";

export default function ApiErrorState({ status, message, retryAfter }) {
  const [isPending, startTransition] = useTransition();
  const router = useRouter();

  const rateLimit = getRateLimitPresentation(status, message, retryAfter);
  const limited = status === 429;
  const unavailable = status >= 500 || status == null;
  const title = limited ? rateLimit.title : unavailable ? "GitHub data is temporarily unavailable" : "GitHub data could not be loaded";
  const detail = limited
    ? rateLimit.detail
    : unavailable
      ? "GitScope could not retrieve the data right now. Please try again shortly."
      : "The requested public GitHub data could not be retrieved. Check the address and try again.";

  return (
    <section className="error-page" role="alert">
      <p className="eyebrow">Analysis unavailable</p>
      <h2>{title}</h2>
      <p>{detail}</p>
      <button type="button" disabled={isPending} onClick={() => startTransition(() => router.refresh())}>
        {isPending ? "Retrying…" : "Try again"}
      </button>
      <p><a className="button button-secondary" href="/">Analyze another repository</a></p>
    </section>
  );
}
