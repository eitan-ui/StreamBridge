-- StreamBridge Migration v5: lock down the licenses table
--
-- PROBLEM (CRITICAL): the original policies in supabase_setup.sql allowed the
-- anon / publishable key (which ships inside the desktop app and is trivially
-- extractable) to SELECT, UPDATE and INSERT the entire `licenses` table.
-- That exposed every customer email + activation code and allowed anyone to
-- self-issue or revoke licenses, bypassing payment and the Edge Functions.
--
-- FIX: remove all anon-facing policies on `licenses`. With RLS enabled and no
-- policy, the anon/publishable key can no longer read or write the table.
-- Only `service_role` (used exclusively inside the Edge Functions
-- send-code / verify-code / check-license) keeps full access — service_role
-- bypasses RLS entirely.
--
-- Run this in the Supabase SQL Editor.

-- 1. Ensure RLS is on (no-op if already enabled).
alter table licenses enable row level security;

-- 2. Drop the permissive anon policies.
drop policy if exists "Allow read licenses"   on licenses;
drop policy if exists "Allow update licenses" on licenses;
drop policy if exists "Allow insert licenses" on licenses;

-- After this, `select/update/insert/delete` on `licenses` with the anon or
-- publishable key all return 0 rows / permission denied. All license logic must
-- go through the Edge Functions (service_role). See supabase/functions/.

-- 3. app_versions stays publicly readable on purpose: it only holds
--    version / download_url / release_notes (no sensitive data), and the client
--    reads it directly for auto-update. insert/update are already check(false).
--    Nothing to change here, listed for clarity:
--    create policy "Allow read app_versions" on app_versions for select using (true);

-- 4. (Optional hardening) revoke base table privileges from anon as defense in
--    depth, so even a future accidental policy can't grant access by itself.
revoke all on licenses from anon;
