"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

export default function SaveAnalysisButton({ owner, repository }) {
  const [status, setStatus] = useState("");
  const [pending, setPending] = useState(false);
  const router = useRouter();

  async function save() {
    setPending(true);
    setStatus("");
    try {
      const response = await fetch("/api/saved-analyses", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ owner, repository }),
      });
      const result = await response.json().catch(() => ({}));
      if (response.status === 401) {
        const returnTo = `/repos/${encodeURIComponent(owner)}/${encodeURIComponent(repository)}`;
        window.location.assign(`/auth/login?returnTo=${encodeURIComponent(returnTo)}`);
        return;
      }
      if (!response.ok) throw new Error(result.error || "Could not save analysis.");
      setStatus(result.alreadySaved ? "This analysis is already saved." : "Analysis saved.");
      router.refresh();
    } catch (error) {
      setStatus(error.message || "Could not save analysis.");
    } finally {
      setPending(false);
    }
  }

  return (
    <div className="saved-action">
      <button type="button" className="primary-button" disabled={pending} onClick={save}>
        {pending ? "Saving…" : "Save analysis"}
      </button>
      {status ? <p role="status">{status}</p> : null}
    </div>
  );
}
