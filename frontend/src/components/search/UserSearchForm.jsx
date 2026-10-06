"use client";

import { useState, useTransition } from "react";
import { usePathname, useRouter } from "next/navigation";
import SearchSection from "./SearchSection";

export default function UserSearchForm({ initialUsername = "" }) {
  const [username, setUsername] = useState(initialUsername);
  const [error, setError] = useState("");
  const [isPending, startTransition] = useTransition();
  const router = useRouter();
  const pathname = usePathname();

  const analyze = () => {
    const value = username.trim();
    if (!value) {
      setError("Please enter a GitHub username.");
      return;
    }
    setError("");
    const destination = `/users/${encodeURIComponent(value)}`;
    startTransition(() => {
      if (pathname === destination) router.refresh();
      else router.push(destination);
    });
  };

  return (
    <SearchSection
      username={username}
      setUsername={setUsername}
      onAnalyze={analyze}
      loading={isPending}
      error={error}
    />
  );
}
