'use client';

/**
 * Authentication Context for NeoBot-Net LEAN
 * 
 * Supports:
 * - Google SSO via Supabase Auth
 * - API key generation for programmatic access
 * 
 * Note: Email/password auth has been removed for the LEAN refactor.
 */

import React, { createContext, useContext, useEffect, useReducer, ReactNode, useCallback, useRef } from 'react';
import { toast } from 'sonner';
import { supabase, signInWithGoogle, signInWithTwitter, signOut as supabaseSignOut, getSession } from '@/lib/supabase';
import { API_BASE_URL } from '@/lib/api/config';
import type { Session, User } from '@supabase/supabase-js';

// ============================================================================
// TYPES
// ============================================================================

interface AuthState {
  user: User | null;
  session: Session | null;
  isLoading: boolean;
  isAuthenticated: boolean;
}

interface APIKey {
  id: string;
  key?: string; // Only present on creation
  key_prefix: string;
  name: string;
  created_at: string;
  last_used_at: string | null;
  is_active: boolean;
}

interface AuthContextType extends AuthState {
  signInWithGoogle: () => Promise<void>;
  signInWithTwitter: () => Promise<void>;
  signOut: () => Promise<void>;
  getAPIKeys: () => Promise<APIKey[]>;
  createAPIKey: (name?: string) => Promise<APIKey>;
  revokeAPIKey: (keyId: string) => Promise<boolean>;
}

// ============================================================================
// REDUCER
// ============================================================================

type AuthAction =
  | { type: 'SET_LOADING'; payload: boolean }
  | { type: 'SET_SESSION'; payload: { user: User | null; session: Session | null } }
  | { type: 'SIGN_OUT' };

const initialState: AuthState = {
  user: null,
  session: null,
  isLoading: true,
  isAuthenticated: false,
};

const authReducer = (state: AuthState, action: AuthAction): AuthState => {
  switch (action.type) {
    case 'SET_LOADING':
      return { ...state, isLoading: action.payload };
    case 'SET_SESSION':
      return {
        ...state,
        user: action.payload.user,
        session: action.payload.session,
        isAuthenticated: !!action.payload.session,
        isLoading: false,
      };
    case 'SIGN_OUT':
      return {
        ...initialState,
        isLoading: false,
      };
    default:
      return state;
  }
};

// ============================================================================
// CONTEXT
// ============================================================================

const AuthContext = createContext<AuthContextType | undefined>(undefined);

// ============================================================================
// PROVIDER
// ============================================================================

export const AuthProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
  const [state, dispatch] = useReducer(authReducer, initialState);
  const hasShownSignInToast = useRef(false);

  // Create backend session (sets httpOnly cookie)
  const createBackendSession = useCallback(async (accessToken: string) => {
    try {
      await fetch(`${API_BASE_URL}/api/v1/auth/session`, {
        method: 'POST',
        credentials: 'include', // Important: include cookies
        headers: {
          'Authorization': `Bearer ${accessToken}`,
          'Content-Type': 'application/json',
        },
      });
      console.log('Backend session created (httpOnly cookie set)');
    } catch (error) {
      console.error('Failed to create backend session:', error);
      // Don't fail login if backend session creation fails - Bearer token still works
    }
  }, []);

  // Initialize auth state on mount
  useEffect(() => {
    // Subscribe to auth state changes FIRST
    // This will fire INITIAL_SESSION event with the current session state
    const { data: { subscription } } = supabase.auth.onAuthStateChange(
      async (event, session) => {
        console.log('Auth state changed:', event, session ? 'has session' : 'no session');
        
        // Handle all session-related events
        if ((event === 'SIGNED_IN' || event === 'INITIAL_SESSION' || event === 'TOKEN_REFRESHED') && session) {
          // Create backend session (sets httpOnly cookie for secure API calls)
          await createBackendSession(session.access_token);
          
          dispatch({
            type: 'SET_SESSION',
            payload: {
              user: session.user,
              session: session,
            },
          });
          // Only show toast for actual sign-in, not for session restore or page reload
          // Use ref to prevent duplicate toasts across re-renders and sessionStorage for new tabs
          if (event === 'SIGNED_IN' && !hasShownSignInToast.current) {
            const toastKey = 'neobotnet_signin_toast_shown';
            const lastShown = sessionStorage.getItem(toastKey);
            const now = Date.now();
            
            // Only show toast if we haven't shown it in the last 5 seconds
            // This handles OAuth redirects that fire SIGNED_IN on return
            if (!lastShown || (now - parseInt(lastShown, 10)) > 5000) {
              toast.success('Signed in successfully!');
              sessionStorage.setItem(toastKey, now.toString());
            }
            hasShownSignInToast.current = true;
          }
        } else if (event === 'SIGNED_OUT') {
          dispatch({ type: 'SIGN_OUT' });
        } else if (event === 'INITIAL_SESSION' && !session) {
          // No existing session found - mark loading as done
          dispatch({ type: 'SET_LOADING', payload: false });
        }
      }
    );

    // Fallback: manually check session after a short delay
    // This handles edge cases where onAuthStateChange might not fire
    const timeoutId = setTimeout(async () => {
      try {
        const session = await getSession();
        if (session) {
          dispatch({ 
            type: 'SET_SESSION',
            payload: {
              user: session.user,
              session: session,
            },
          });
        } else {
          // Only set loading to false if we're still loading
          // (onAuthStateChange might have already handled this)
          dispatch({ type: 'SET_LOADING', payload: false });
        }
      } catch (error) {
        console.error('Failed to check session:', error);
        dispatch({ type: 'SET_LOADING', payload: false });
      }
    }, 1000);

    return () => {
      subscription.unsubscribe();
      clearTimeout(timeoutId);
    };
  }, [createBackendSession]);

  // Sign in with Google
  const handleSignInWithGoogle = useCallback(async () => {
    try {
      dispatch({ type: 'SET_LOADING', payload: true });
      await signInWithGoogle();
      // Note: The actual sign-in happens via redirect
      // The onAuthStateChange listener will handle the session update
    } catch (error) {
      console.error('Google sign-in failed:', error);
      toast.error('Failed to sign in with Google');
      dispatch({ type: 'SET_LOADING', payload: false });
    }
  }, []);

  // Sign in with X (Twitter)
  const handleSignInWithTwitter = useCallback(async () => {
    try {
      dispatch({ type: 'SET_LOADING', payload: true });
      console.log('[Twitter OAuth] Initiating sign-in...');
      console.log('[Twitter OAuth] Redirect URL will be:', `${window.location.origin}/auth/callback`);
      
      const result = await signInWithTwitter();
      
      console.log('[Twitter OAuth] signInWithOAuth result:', result);
      // Note: The actual sign-in happens via redirect
      // The onAuthStateChange listener will handle the session update
    } catch (error: unknown) {
      console.error('[Twitter OAuth] Sign-in failed:', error);
      
      // Extract more detailed error information
      const errorMessage = error instanceof Error ? error.message : String(error);
      const errorDetails = (error as { status?: number; code?: string })?.status || (error as { code?: string })?.code;
      
      console.error('[Twitter OAuth] Error details:', { message: errorMessage, details: errorDetails });
      
      toast.error(`Failed to sign in with X: ${errorMessage}`);
      dispatch({ type: 'SET_LOADING', payload: false });
    }
  }, []);

  // Sign out
  const handleSignOut = useCallback(async () => {
    try {
      // Clear backend session (httpOnly cookie)
      try {
        await fetch(`${API_BASE_URL}/api/v1/auth/session`, {
          method: 'DELETE',
          credentials: 'include',
        });
        console.log('Backend session cleared');
      } catch (error) {
        console.error('Failed to clear backend session:', error);
        // Continue with Supabase signout even if backend session clear fails
      }
      
      await supabaseSignOut();
      dispatch({ type: 'SIGN_OUT' });
      toast.success('Signed out successfully');
    } catch (error) {
      console.error('Sign out failed:', error);
      toast.error('Failed to sign out');
    }
  }, []);

  // Get API keys for the current user
  const getAPIKeys = useCallback(async (): Promise<APIKey[]> => {
    if (!state.session?.access_token) {
      throw new Error('Not authenticated');
    }

    const response = await fetch('/api/v1/auth/api-keys', {
      headers: {
        'Authorization': `Bearer ${state.session.access_token}`,
      },
    });

    if (!response.ok) {
      throw new Error('Failed to fetch API keys');
    }

    return response.json();
  }, [state.session]);

  // Create a new API key
  const createAPIKey = useCallback(async (name: string = 'Default'): Promise<APIKey> => {
    if (!state.session?.access_token) {
      throw new Error('Not authenticated');
    }

    const response = await fetch('/api/v1/auth/api-keys', {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${state.session.access_token}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ name }),
    });

    if (!response.ok) {
      throw new Error('Failed to create API key');
    }

    const data = await response.json();
    toast.success('API key created! Make sure to copy it now.');
    return data;
  }, [state.session]);

  // Revoke an API key
  const revokeAPIKey = useCallback(async (keyId: string): Promise<boolean> => {
    if (!state.session?.access_token) {
      throw new Error('Not authenticated');
    }

    const response = await fetch(`/api/v1/auth/api-keys/${keyId}`, {
      method: 'DELETE',
      headers: {
        'Authorization': `Bearer ${state.session.access_token}`,
      },
    });

    if (!response.ok) {
      throw new Error('Failed to revoke API key');
    }

    toast.success('API key revoked');
    return true;
  }, [state.session]);

  const value: AuthContextType = {
    ...state,
    signInWithGoogle: handleSignInWithGoogle,
    signInWithTwitter: handleSignInWithTwitter,
    signOut: handleSignOut,
    getAPIKeys,
    createAPIKey,
    revokeAPIKey,
  };

  return (
    <AuthContext.Provider value={value}>
      {children}
    </AuthContext.Provider>
  );
};

// ============================================================================
// HOOK
// ============================================================================

export const useAuth = (): AuthContextType => {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}; 
