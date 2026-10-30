-- Mirrors the existing Supabase migration 20261030051204.
-- Requires the Prisma-managed public tables to exist before this is applied.
-- Re-running these statements is safe and does not grant Data API access.
ALTER TABLE public.users DISABLE ROW LEVEL SECURITY;
ALTER TABLE public.identities DISABLE ROW LEVEL SECURITY;
ALTER TABLE public.repositories DISABLE ROW LEVEL SECURITY;
ALTER TABLE public.analyses DISABLE ROW LEVEL SECURITY;
ALTER TABLE public.saved_analyses DISABLE ROW LEVEL SECURITY;
ALTER TABLE public.tracked_repositories DISABLE ROW LEVEL SECURITY;
ALTER TABLE public.gitscope_rate_limit_windows DISABLE ROW LEVEL SECURITY;
