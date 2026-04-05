-- StreamBridge License System v2 — Email-based registration
-- Run this in Supabase SQL Editor AFTER the original supabase_setup.sql

-- 1. Add new columns for email-based activation
ALTER TABLE licenses ADD COLUMN IF NOT EXISTS email TEXT;
ALTER TABLE licenses ADD COLUMN IF NOT EXISTS code_expires_at TIMESTAMPTZ;
ALTER TABLE licenses ADD COLUMN IF NOT EXISTS code_verified BOOLEAN DEFAULT FALSE;

-- 2. Migrate existing users: copy username to email
UPDATE licenses SET email = username WHERE email IS NULL;

-- 3. Add unique constraint on email
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'licenses_email_key'
  ) THEN
    ALTER TABLE licenses ADD CONSTRAINT licenses_email_key UNIQUE (email);
  END IF;
END $$;

-- 4. Create index for faster email lookups
CREATE INDEX IF NOT EXISTS idx_licenses_email ON licenses (email);
