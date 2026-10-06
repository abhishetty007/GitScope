"use client";

import { useTransition } from "react";
import { useRouter } from "next/navigation";

export default function ApiErrorState({ message }) {
  const [isPending, startTransition] = useTransition();
  const router = useRouter();

  return (
    <section className="error-page" role="alert">
      <h2>GitHub data could not be loaded</h2>
      <p>{message || "The GitScope API is temporarily unavailable."}</p>
      <button type="button" disabled={isPending} onClick={() => startTransition(() => router.refresh())}>
        {isPending ? "Retrying…" : "Try again"}
      </button>
    </section>
  );
}
