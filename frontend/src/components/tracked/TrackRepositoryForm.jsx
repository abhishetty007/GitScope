"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

export default function TrackRepositoryForm() {
  const [value, setValue] = useState("");
  const [pending, setPending] = useState(false);
  const [message, setMessage] = useState("");
  const [isError, setIsError] = useState(false);
  const router = useRouter();

  async function submit(event) {
    event.preventDefault();
    const [owner, repository, ...extra] = value.trim().split("/");
    if (!owner || !repository || extra.length) {
      setIsError(true);
      setMessage("Enter a repository as owner/name.");
      return;
    }
    setPending(true);
    setMessage("");
    setIsError(false);
    try {
      const response = await fetch("/api/tracked-repositories", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ owner, repository }),
      });
      const result = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(result.error || "Could not track repository.");
      setValue("");
      setMessage("Repository tracked.");
      router.refresh();
    } catch (error) {
      setIsError(true);
      setMessage(error.message || "Could not track repository.");
    } finally {
      setPending(false);
    }
  }

  return (
    <form className="tracked-form" onSubmit={submit}>
      <label htmlFor="tracked-repository">Public repository</label>
      <div className="tracked-form-row">
        <input
          id="tracked-repository"
          value={value}
          onChange={(event) => setValue(event.target.value)}
          placeholder="owner/repository"
          maxLength={140}
          required
        />
        <button className="primary-button" type="submit" disabled={pending}>
          {pending ? "Adding…" : "Track repository"}
        </button>
      </div>
      {message ? <p className={isError ? "form-error" : "form-success"} role={isError ? "alert" : "status"}>{message}</p> : null}
    </form>
  );
}
