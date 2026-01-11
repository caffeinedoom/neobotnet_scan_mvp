/**
 * Supabase Client Configuration
 * 
 * This module provides the Supabase client for:
 * - Google SSO authentication
 * - Direct database access (if needed)
 * 
 * Note: For data access, we still use the backend API with API keys.
 * Supabase is primarily used for authentication (Google SSO).
 */

import { createClient, SupabaseClient } from '@supabase/supabase-js';

// Environment variables for Supabase
const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL;
const supabaseAnonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;

// Check if we have valid env vars (not during build time)
const isConfigured = !!(supabaseUrl && supabaseAnonKey);

// Validate environment variables (only warn in browser, not during build)
if (!isConfigured && typeof window !== 'undefined') {
  console.warn(
    'Missing Supabase environment variables. ' +
    'Set NEXT_PUBLIC_SUPABASE_URL and NEXT_PUBLIC_SUPABASE_ANON_KEY in your .env.local file.'
  );
}

// Create Supabase client with auth configuration
// Use placeholder values during build to prevent errors
export const supabase: SupabaseClient = createClient(
  supabaseUrl || 'https://placeholder.supabase.co',
  supabaseAnonKey || 'placeholder-anon-key',
  {
    auth: {
      // Persist session in localStorage
      persistSession: true,
      // Auto-refresh tokens
      autoRefreshToken: true,
      // Detect session from URL (for OAuth redirects)
      detectSessionInUrl: true,
      // Storage key for session
      storageKey: 'neobotnet-auth',
    },
  }
);

/**
 * Get the current Supabase session
 */
export const getSession = async () => {
  const { data: { session }, error } = await supabase.auth.getSession();
  if (error) {
    console.error('Error getting session:', error.message);
    return null;
  }
  return session;
};

/**
 * Get the current user
 */
export const getUser = async () => {
  const { data: { user }, error } = await supabase.auth.getUser();
  if (error) {
    console.error('Error getting user:', error.message);
    return null;
  }
  return user;
};

/**
 * Sign in with Google SSO
 * Redirects to Google OAuth flow
 */
export const signInWithGoogle = async () => {
  const { data, error } = await supabase.auth.signInWithOAuth({
    provider: 'google',
    options: {
      // Redirect back to our callback page after auth
      redirectTo: `${window.location.origin}/auth/callback`,
      // Request specific scopes
      scopes: 'email profile',
      // Query params for Google
      queryParams: {
        access_type: 'offline',
        prompt: 'consent',
      },
    },
  });

  if (error) {
    console.error('Google sign-in error:', error.message);
    throw error;
  }

  return data;
};

/**
 * Sign in with X (Twitter) SSO
 * Redirects to Twitter OAuth 2.0 flow
 * 
 * Twitter OAuth 2.0 requires explicit scopes:
 * - users.read: Read user profile information
 * - tweet.read: Required by Twitter even if not using tweets
 * 
 * Note: Make sure your Twitter Developer app has:
 * 1. OAuth 2.0 enabled (not just OAuth 1.0a)
 * 2. Type of App: "Confidential client"
 * 3. Callback URL: https://huxley.neobotnet.com/auth/v1/callback
 * 4. Client ID and Client Secret (NOT API Key/Secret)
 */
export const signInWithTwitter = async () => {
  const { data, error } = await supabase.auth.signInWithOAuth({
    provider: 'twitter',
    options: {
      // Redirect back to our callback page after auth
      redirectTo: `${window.location.origin}/auth/callback`,
      // Twitter OAuth 2.0 requires explicit scopes
      // users.read: Get user profile info
      // tweet.read: Required base scope for Twitter OAuth 2.0
      scopes: 'users.read tweet.read',
    },
  });

  if (error) {
    console.error('Twitter sign-in error:', error.message);
    throw error;
  }

  return data;
};

/**
 * Sign out the current user
 */
export const signOut = async () => {
  const { error } = await supabase.auth.signOut();
  if (error) {
    console.error('Sign out error:', error.message);
    throw error;
  }
};

/**
 * Subscribe to auth state changes
 */
export const onAuthStateChange = (
  callback: (event: string, session: unknown) => void
) => {
  return supabase.auth.onAuthStateChange((event, session) => {
    callback(event, session);
  });
};

export default supabase;

