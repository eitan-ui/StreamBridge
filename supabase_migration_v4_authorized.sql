-- StreamBridge Migration v4: pre-authorization for paid users
-- Only emails with authorized=true can activate the app

ALTER TABLE licenses ADD COLUMN IF NOT EXISTS authorized BOOLEAN DEFAULT FALSE;

-- Grandfather existing users (already verified) as authorized
UPDATE licenses SET authorized = TRUE WHERE code_verified = TRUE;
