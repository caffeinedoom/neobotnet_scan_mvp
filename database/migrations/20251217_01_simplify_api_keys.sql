-- Migration: Simplify API Keys - One Key Per User with Reveal Support
-- Date: 2025-12-17
-- Purpose: Store encrypted key for retrieval, enforce one key per user

-- ============================================================================
-- ADD ENCRYPTED KEY COLUMN
-- ============================================================================

-- Add column to store the encrypted raw key (for reveal functionality)
-- Uses Supabase's built-in encryption with the project's secret
ALTER TABLE "public"."api_keys" 
ADD COLUMN IF NOT EXISTS "encrypted_key" TEXT;

-- ============================================================================
-- ENFORCE ONE KEY PER USER (Optional - can also enforce in application)
-- ============================================================================

-- Create a partial unique index to ensure only ONE active key per user
CREATE UNIQUE INDEX IF NOT EXISTS "idx_api_keys_one_per_user" 
    ON "public"."api_keys" ("user_id") 
    WHERE "is_active" = true;

-- ============================================================================
-- COMMENTS
-- ============================================================================

COMMENT ON COLUMN "public"."api_keys"."encrypted_key" IS 
    'Encrypted raw API key stored for reveal functionality. Encrypted using application-level encryption.';


