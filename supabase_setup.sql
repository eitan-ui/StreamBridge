-- StreamBridge License & Update System
-- Run this in Supabase SQL Editor

-- 1. Licenses table (1 machine at a time per user)
create table if not exists licenses (
  id uuid default gen_random_uuid() primary key,
  username text not null unique,
  activation_code text not null,
  machine_id text,          -- hardware fingerprint of active machine
  machine_name text,        -- friendly name (computer name)
  active boolean default true,  -- set false to block user
  last_seen timestamptz,
  created_at timestamptz default now()
);

-- 2. App versions table (for auto-update)
create table if not exists app_versions (
  id uuid default gen_random_uuid() primary key,
  version text not null unique,
  download_url text not null,
  release_notes text,
  is_latest boolean default false,
  created_at timestamptz default now()
);

-- 3. RLS policies
alter table licenses enable row level security;
alter table app_versions enable row level security;

-- Licenses: allow read/update by anon (client app needs to check & update machine_id)
create policy "Allow read licenses" on licenses for select using (true);
create policy "Allow update licenses" on licenses for update using (true);
create policy "Allow insert licenses" on licenses for insert with check (true);

-- App versions: allow read by anyone
create policy "Allow read app_versions" on app_versions for select using (true);
-- Only service_role can insert/update versions (via dashboard or admin API)
create policy "Allow insert app_versions" on app_versions for insert with check (false);
create policy "Allow update app_versions" on app_versions for update using (false);

-- 4. Insert initial version
insert into app_versions (version, download_url, release_notes, is_latest)
values ('1.0.0', '', 'Initial release', true)
on conflict (version) do nothing;
