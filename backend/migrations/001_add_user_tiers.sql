-- =====================================================
-- Migration: Add User Tiers for Paywall
-- Date: 2026-01-01
-- Description: Adds tier/payment tracking to existing tables
-- =====================================================
-- NOTE: Uses existing user_quotas and user_usage tables
-- (there is no separate 'profiles' table in this schema)
-- =====================================================

-- Step 1: Update plan_type constraint to include 'paid'
-- First drop existing constraint, then add new one
ALTER TABLE user_quotas DROP CONSTRAINT IF EXISTS valid_plan_type;
ALTER TABLE user_quotas ADD CONSTRAINT valid_plan_type 
  CHECK (plan_type IN ('free', 'paid', 'pro', 'enterprise'));

-- Step 2: Add Stripe payment tracking columns to user_quotas
ALTER TABLE user_quotas 
ADD COLUMN IF NOT EXISTS stripe_customer_id TEXT;

ALTER TABLE user_quotas 
ADD COLUMN IF NOT EXISTS stripe_payment_id TEXT;

ALTER TABLE user_quotas 
ADD COLUMN IF NOT EXISTS paid_at TIMESTAMPTZ;

-- Step 3: Create index for quick plan_type lookups
CREATE INDEX IF NOT EXISTS idx_user_quotas_plan_type ON user_quotas(plan_type);

-- Step 4: Add URL view tracking to user_usage
-- Tracks how many URLs a free user has viewed (for 250 limit)
ALTER TABLE user_usage
ADD COLUMN IF NOT EXISTS urls_viewed_count INTEGER DEFAULT 0;

-- Step 5: Create function to get paid user count (for 100 user cap)
CREATE OR REPLACE FUNCTION get_paid_user_count()
RETURNS INTEGER
LANGUAGE SQL
SECURITY DEFINER
AS $$
  SELECT COUNT(*)::INTEGER FROM user_quotas WHERE plan_type = 'paid';
$$;

-- Step 6: Create function to check if spots available
CREATE OR REPLACE FUNCTION has_paid_spots_available(max_spots INTEGER DEFAULT 100)
RETURNS BOOLEAN
LANGUAGE SQL
SECURITY DEFINER
AS $$
  SELECT (SELECT COUNT(*) FROM user_quotas WHERE plan_type = 'paid') < max_spots;
$$;

-- =====================================================
-- Verification queries (run after migration)
-- =====================================================
-- SELECT column_name, data_type, column_default 
-- FROM information_schema.columns 
-- WHERE table_name = 'user_quotas' 
-- AND column_name IN ('plan_type', 'paid_at', 'stripe_customer_id', 'stripe_payment_id');

-- SELECT column_name, data_type, column_default 
-- FROM information_schema.columns 
-- WHERE table_name = 'user_usage' 
-- AND column_name = 'urls_viewed_count';

-- SELECT get_paid_user_count();
-- SELECT has_paid_spots_available(100);
