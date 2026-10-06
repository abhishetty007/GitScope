"use client";

import { useState, useTransition } from "react";
import { useRouter } from "next/navigation";
import UserProfileCard from "./UserProfileCard";
import ProfileAnalytics from "./ProfileAnalytics";
import RepositoryGrid from "./RepositoryGrid";
import UserSearchForm from "../search/UserSearchForm";

export default function UserAnalyticsClient({ username, user, analytics, repositories }) {
  const [analyzingRepo, setAnalyzingRepo] = useState("");
  const [isPending, startTransition] = useTransition();
  const router = useRouter();

  const openRepository = (repo) => {
    const [owner, name] = (repo.full_name || `${username}/${repo.name}`).split("/");
    setAnalyzingRepo(`${owner}/${name}`);
    startTransition(() => router.push(`/repos/${encodeURIComponent(owner)}/${encodeURIComponent(name)}`));
  };

  return (
    <>
      <UserSearchForm initialUsername={username} />
      <UserProfileCard user={user} />
      <ProfileAnalytics
        analytics={analytics}
        username={username}
        onAnalyzeRepo={openRepository}
        analyzingRepo={isPending ? analyzingRepo : ""}
      />
      <RepositoryGrid
        repositories={repositories}
        onAnalyzeRepo={openRepository}
        analyzingRepo={isPending ? analyzingRepo : ""}
      />
    </>
  );
}
