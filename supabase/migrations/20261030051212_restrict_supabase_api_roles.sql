-- Mirrors the existing Supabase migration 20261030051212.
-- Requires the Prisma-managed public tables to exist before this is applied.
-- Re-running REVOKE is safe; app access is through restricted PostgreSQL roles.
REVOKE ALL PRIVILEGES ON TABLE
    public.users,
    public.identities,
    public.repositories,
    public.analyses,
    public.saved_analyses,
    public.tracked_repositories,
    public.gitscope_rate_limit_windows
FROM anon, authenticated;
