"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

export default function MutationButton({ endpoint, label, confirmText }) {
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");
  const router = useRouter();

  async function remove() {
    if (confirmText && !window.confirm(confirmText)) return;
    setPending(true);
    setError("");
    try {
      const response = await fetch(endpoint, { method: "DELETE" });
      if (!response.ok) {
        const result = await response.json().catch(() => ({}));
        throw new Error(result.error || "Could not remove item.");
      }
      router.refresh();
    } catch (reason) {
      setError(reason.message || "Could not remove item.");
    } finally {
      setPending(false);
    }
  }

  return (
    <div>
      <button type="button" className="secondary-button" disabled={pending} onClick={remove}>
        {pending ? "Removing…" : label}
      </button>
      {error ? <p className="error" role="alert">{error}</p> : null}
    </div>
  );
}
