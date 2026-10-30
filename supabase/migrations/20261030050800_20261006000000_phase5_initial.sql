CREATE TABLE "users" (
    "id" UUID NOT NULL,
    "created_at" TIMESTAMPTZ(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMPTZ(3) NOT NULL,
    CONSTRAINT "users_pkey" PRIMARY KEY ("id")
);

CREATE TABLE "identities" (
    "id" UUID NOT NULL,
    "user_id" UUID NOT NULL,
    "issuer" VARCHAR(512) NOT NULL,
    "subject" VARCHAR(255) NOT NULL,
    "created_at" TIMESTAMPTZ(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT "identities_pkey" PRIMARY KEY ("id")
);

CREATE TABLE "repositories" (
    "id" UUID NOT NULL,
    "provider" VARCHAR(32) NOT NULL DEFAULT 'github',
    "provider_repo_id" BIGINT NOT NULL,
    "owner_login" VARCHAR(255) NOT NULL,
    "name" VARCHAR(255) NOT NULL,
    "visibility" VARCHAR(16) NOT NULL DEFAULT 'public',
    "created_at" TIMESTAMPTZ(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMPTZ(3) NOT NULL,
    CONSTRAINT "repositories_pkey" PRIMARY KEY ("id")
);

CREATE TABLE "analyses" (
    "id" UUID NOT NULL,
    "repository_id" UUID NOT NULL,
    "analyzer_version" VARCHAR(64) NOT NULL,
    "snapshot_hash" CHAR(64) NOT NULL,
    "score" DOUBLE PRECISION,
    "result" JSONB NOT NULL,
    "created_at" TIMESTAMPTZ(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "source_updated_at" TIMESTAMPTZ(3),
    CONSTRAINT "analyses_pkey" PRIMARY KEY ("id")
);

CREATE TABLE "saved_analyses" (
    "user_id" UUID NOT NULL,
    "analysis_id" UUID NOT NULL,
    "created_at" TIMESTAMPTZ(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT "saved_analyses_pkey" PRIMARY KEY ("user_id", "analysis_id")
);

CREATE TABLE "tracked_repositories" (
    "user_id" UUID NOT NULL,
    "repository_id" UUID NOT NULL,
    "created_at" TIMESTAMPTZ(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT "tracked_repositories_pkey" PRIMARY KEY ("user_id", "repository_id")
);

CREATE UNIQUE INDEX "identities_issuer_subject_key" ON "identities"("issuer", "subject");
CREATE INDEX "identities_user_id_idx" ON "identities"("user_id");
CREATE UNIQUE INDEX "repositories_provider_provider_repo_id_key" ON "repositories"("provider", "provider_repo_id");
CREATE INDEX "repositories_provider_owner_login_name_idx" ON "repositories"("provider", "owner_login", "name");
CREATE UNIQUE INDEX "analyses_repository_id_analyzer_version_snapshot_hash_key" ON "analyses"("repository_id", "analyzer_version", "snapshot_hash");
CREATE INDEX "analyses_repository_id_created_at_idx" ON "analyses"("repository_id", "created_at" DESC);
CREATE INDEX "saved_analyses_analysis_id_idx" ON "saved_analyses"("analysis_id");
CREATE INDEX "tracked_repositories_repository_id_idx" ON "tracked_repositories"("repository_id");

ALTER TABLE "identities" ADD CONSTRAINT "identities_user_id_fkey" FOREIGN KEY ("user_id") REFERENCES "users"("id") ON DELETE CASCADE ON UPDATE CASCADE;
ALTER TABLE "analyses" ADD CONSTRAINT "analyses_repository_id_fkey" FOREIGN KEY ("repository_id") REFERENCES "repositories"("id") ON DELETE CASCADE ON UPDATE CASCADE;
ALTER TABLE "saved_analyses" ADD CONSTRAINT "saved_analyses_user_id_fkey" FOREIGN KEY ("user_id") REFERENCES "users"("id") ON DELETE CASCADE ON UPDATE CASCADE;
ALTER TABLE "saved_analyses" ADD CONSTRAINT "saved_analyses_analysis_id_fkey" FOREIGN KEY ("analysis_id") REFERENCES "analyses"("id") ON DELETE CASCADE ON UPDATE CASCADE;
ALTER TABLE "tracked_repositories" ADD CONSTRAINT "tracked_repositories_user_id_fkey" FOREIGN KEY ("user_id") REFERENCES "users"("id") ON DELETE CASCADE ON UPDATE CASCADE;
ALTER TABLE "tracked_repositories" ADD CONSTRAINT "tracked_repositories_repository_id_fkey" FOREIGN KEY ("repository_id") REFERENCES "repositories"("id") ON DELETE CASCADE ON UPDATE CASCADE;
