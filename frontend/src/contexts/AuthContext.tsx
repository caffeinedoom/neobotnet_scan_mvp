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

import React, { createContext, useContext, useEffect, useReducer, ReactNode, useCallback } from 'react';
import { toast } from 'sonner';
import { supabase, signInWithGoogle, signInWithTwitter, signOut as supabaseSignOut, getSession } from '@/lib/supabase';
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

  // Initialize auth state on mount
  useEffect(() => {
    const initializeAuth = async () => {
      try {
        const session = await getSession();
        dispatch({
          type: 'SET_SESSION',
          payload: {
            user: session?.user ?? null,
            session: session ?? null,
          },
        });
      } catch (error) {
        console.error('Failed to initialize auth:', error);
        dispatch({ type: 'SET_LOADING', payload: false });
      }
    };

    initializeAuth();

    // Subscribe to auth state changes
    const { data: { subscription } } = supabase.auth.onAuthStateChange(
      async (event, session) => {
        console.log('Auth state changed:', event);
        
        if (event === 'SIGNED_IN' && session) {
          dispatch({
            type: 'SET_SESSION',
            payload: {
              user: session.user,
              session: session,
            },
          });
          toast.success('Signed in successfully!');
        } else if (event === 'SIGNED_OUT') {
          dispatch({ type: 'SIGN_OUT' });
        } else if (event === 'TOKEN_REFRESHED' && session) {
          dispatch({
            type: 'SET_SESSION',
            payload: {
              user: session.user,
              session: session,
            },
          });
        }
      }
    );

    return () => {
      subscription.unsubscribe();
    };
  }, []);

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
      await signInWithTwitter();
      // Note: The actual sign-in happens via redirect
      // The onAuthStateChange listener will handle the session update
    } catch (error) {
      console.error('Twitter sign-in failed:', error);
      toast.error('Failed to sign in with X');
      dispatch({ type: 'SET_LOADING', payload: false });
    }
  }, []);

  // Sign out
  const handleSignOut = useCallback(async () => {
    try {
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
