-- StreamBridge Security Migration v3
-- Adds rate limiting columns for Edge Functions

-- Rate limiting for send-code (code request throttling)
ALTER TABLE licenses ADD COLUMN IF NOT EXISTS code_request_count INTEGER DEFAULT 0;
ALTER TABLE licenses ADD COLUMN IF NOT EXISTS code_request_window TIMESTAMPTZ;

-- Rate limiting for verify-code (brute-force protection)
ALTER TABLE licenses ADD COLUMN IF NOT EXISTS failed_verify_count INTEGER DEFAULT 0;
ALTER TABLE licenses ADD COLUMN IF NOT EXISTS last_failed_verify TIMESTAMPTZ;
