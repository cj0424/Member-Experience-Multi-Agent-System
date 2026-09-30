-- Phase 3: close the database to the public API.
-- Turns on Row Level Security on every table in "public" WITHOUT policies:
-- the anon / publishable key can no longer read or write anything.
-- The app keeps working ONLY if it uses the secret / service_role key, which
-- bypasses RLS and lives only on the server (.env / Streamlit secrets).
-- ⚠️ Check your key type first (see the instructions). Safe to run more than once.

do $$
declare r record;
begin
  for r in select tablename from pg_tables where schemaname = 'public' loop
    execute format('alter table public.%I enable row level security', r.tablename);
  end loop;
end $$;
