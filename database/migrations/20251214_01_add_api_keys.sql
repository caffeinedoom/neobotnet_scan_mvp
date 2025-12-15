-- Migration: Add API Keys Table
-- Date: 2025-12-14
-- Purpose: Support custom API keys for authenticated users (LEAN refactor)
-- 
-- This migration adds the api_keys table which allows authenticated users
-- to generate API keys for programmatic access to the public recon data.

-- ============================================================================
-- API KEYS TABLE
-- ============================================================================

CREATE TABLE IF NOT EXISTS "public"."api_keys" (
    "id" UUID DEFAULT gen_random_uuid() NOT NULL,
    "user_id" UUID NOT NULL,
    "key_hash" TEXT NOT NULL,
    "key_prefix" TEXT NOT NULL,
    "name" TEXT DEFAULT 'Default' NOT NULL,
    "created_at" TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    "last_used_at" TIMESTAMPTZ,
    "is_active" BOOLEAN DEFAULT true NOT NULL,
    
    -- Primary key
    CONSTRAINT "api_keys_pkey" PRIMARY KEY ("id"),
    
    -- Ensure key_hash is unique (no duplicate keys)
    CONSTRAINT "api_keys_key_hash_unique" UNIQUE ("key_hash"),
    
    -- Foreign key to Supabase auth.users
    CONSTRAINT "api_keys_user_id_fkey" FOREIGN KEY ("user_id") 
        REFERENCES "auth"."users"("id") ON DELETE CASCADE
);

-- Set table ownership
ALTER TABLE "public"."api_keys" OWNER TO "postgres";

-- ============================================================================
-- INDEXES
-- ============================================================================

-- Fast lookup by key_hash (used for API authentication)
CREATE INDEX IF NOT EXISTS "idx_api_keys_key_hash" 
    ON "public"."api_keys" ("key_hash");

-- Fast lookup by user_id (used for listing user's keys)
CREATE INDEX IF NOT EXISTS "idx_api_keys_user_id" 
    ON "public"."api_keys" ("user_id");

-- Fast lookup for active keys only
CREATE INDEX IF NOT EXISTS "idx_api_keys_active" 
    ON "public"."api_keys" ("key_hash") 
    WHERE "is_active" = true;

-- ============================================================================
-- ROW LEVEL SECURITY
-- ============================================================================

ALTER TABLE "public"."api_keys" ENABLE ROW LEVEL SECURITY;

-- Users can view their own API keys
CREATE POLICY "Users can view own API keys" 
    ON "public"."api_keys" 
    FOR SELECT 
    USING (user_id = auth.uid());

-- Users can create their own API keys
CREATE POLICY "Users can create own API keys" 
    ON "public"."api_keys" 
    FOR INSERT 
    WITH CHECK (user_id = auth.uid());

-- Users can update their own API keys (e.g., deactivate)
CREATE POLICY "Users can update own API keys" 
    ON "public"."api_keys" 
    FOR UPDATE 
    USING (user_id = auth.uid());

-- Users can delete their own API keys
CREATE POLICY "Users can delete own API keys" 
    ON "public"."api_keys" 
    FOR DELETE 
    USING (user_id = auth.uid());

-- Service role has full access (for API key validation in backend)
CREATE POLICY "Service role full access to API keys" 
    ON "public"."api_keys" 
    FOR ALL 
    USING (auth.role() = 'service_role');

-- ============================================================================
-- HELPER FUNCTION: Update last_used_at timestamp
-- ============================================================================

CREATE OR REPLACE FUNCTION "public"."update_api_key_last_used"(p_key_hash TEXT)
RETURNS VOID
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
BEGIN
    UPDATE "public"."api_keys"
    SET "last_used_at" = NOW()
    WHERE "key_hash" = p_key_hash
      AND "is_active" = true;
END;
$$;

-- ============================================================================
-- COMMENTS
-- ============================================================================

COMMENT ON TABLE "public"."api_keys" IS 
    'Stores hashed API keys for authenticated users. Keys are SHA-256 hashed for security. The key_prefix stores first 8 chars for display (e.g., "nb_live_a1b2...").';

COMMENT ON COLUMN "public"."api_keys"."key_hash" IS 
    'SHA-256 hash of the full API key. Never store the raw key.';

COMMENT ON COLUMN "public"."api_keys"."key_prefix" IS 
    'First 8 characters of the key for display purposes (e.g., "nb_live_a1b2c3d4").';

COMMENT ON COLUMN "public"."api_keys"."is_active" IS 
    'Whether the key is active. Inactive keys cannot be used for authentication.';

COMMENT ON FUNCTION "public"."update_api_key_last_used"(TEXT) IS 
    'Updates the last_used_at timestamp for an API key. Called during authentication.';

