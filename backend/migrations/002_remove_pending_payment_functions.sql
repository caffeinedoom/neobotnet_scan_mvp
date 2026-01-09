-- Migration: Remove unused pending_payment reservation functions
-- Date: 2026-01-08
-- Description: These functions implemented a reservation system that was never used.
--              The plan_type constraint doesn't include 'pending_payment', so these
--              functions would fail if called. Removing dead code.

-- Drop the reservation functions
DROP FUNCTION IF EXISTS public.try_reserve_pro_spot(uuid, integer);
DROP FUNCTION IF EXISTS public.release_expired_reservations(integer);

-- Verify the constraint still exists and is correct
-- (Should already be: plan_type IN ('free', 'paid', 'pro', 'enterprise'))
-- No changes needed to the constraint since pending_payment was never valid
