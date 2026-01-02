-- =====================================================
-- Migration: Add User Tiers for Paywall
-- Date: 2026-01-01
-- Description: Adds tier tracking for free/paid users
-- =====================================================

-- Step 1: Add tier column to profiles table
-- Default is 'free' for all existing and new users
ALTER TABLE profiles 
ADD COLUMN IF NOT EXISTS tier TEXT DEFAULT 'free' 
CHECK (tier IN ('free', 'paid'));

-- Step 2: Add payment tracking columns
ALTER TABLE profiles 
ADD COLUMN IF NOT EXISTS paid_at TIMESTAMPTZ;

ALTER TABLE profiles 
ADD COLUMN IF NOT EXISTS stripe_customer_id TEXT;

ALTER TABLE profiles 
ADD COLUMN IF NOT EXISTS stripe_payment_id TEXT;

-- Step 3: Create index for quick tier lookups
CREATE INDEX IF NOT EXISTS idx_profiles_tier ON profiles(tier);

-- Step 4: Create function to get paid user count (for 100 cap)
CREATE OR REPLACE FUNCTION get_paid_user_count()
RETURNS INTEGER
LANGUAGE SQL
SECURITY DEFINER
AS $$
  SELECT COUNT(*)::INTEGER FROM profiles WHERE tier = 'paid';
$$;

-- Step 5: Create function to check if spots available
CREATE OR REPLACE FUNCTION has_paid_spots_available(max_spots INTEGER DEFAULT 100)
RETURNS BOOLEAN
LANGUAGE SQL
SECURITY DEFINER
AS $$
  SELECT (SELECT COUNT(*) FROM profiles WHERE tier = 'paid') < max_spots;
$$;

-- Step 6: Add URL view tracking for free tier limit
-- Tracks how many URLs a free user has viewed
ALTER TABLE profiles
ADD COLUMN IF NOT EXISTS urls_viewed_count INTEGER DEFAULT 0;

-- =====================================================
-- Verification queries (run after migration)
-- =====================================================
-- SELECT column_name, data_type, column_default 
-- FROM information_schema.columns 
-- WHERE table_name = 'profiles' 
-- AND column_name IN ('tier', 'paid_at', 'stripe_customer_id', 'urls_viewed_count');

-- SELECT get_paid_user_count();
-- SELECT has_paid_spots_available(100);
