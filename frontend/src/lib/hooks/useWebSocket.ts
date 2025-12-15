/**
 * Custom WebSocket Hook for Real-time Batch Progress Updates
 * ========================================================
 * 
 * Provides authenticated WebSocket connection for real-time batch scan
 * progress updates with automatic reconnection and error handling.
 */

import { useState, useEffect, useRef, useCallback, useMemo } from 'react';
import { toast } from 'sonner';

// Global token cache - shared across all hook instances
let globalWebSocketTokenCache: {
  token: string;
  expiresAt: number;
} | null = null;

// Function to clear cached WebSocket token (useful for logout)
export function clearWebSocketTokenCache(): void {
  globalWebSocketTokenCache = null;
  console.log('🧹 WebSocket token cache cleared');
}

// Types for WebSocket messages
export interface BatchProgressMessage {
  type: 'batch_progress' | 'connection_established' | 'error' | 'test_notification';
  batch_id?: string;
  user_id?: string;
  status?: 'started' | 'progress' | 'completed' | 'failed';
  message?: string;
  timestamp?: string;
  progress?: {
    completed_domains?: number;
    total_domains?: number;
    percentage?: number;
    estimated_completion?: string;
  };
  batch_info?: {
    asset_name?: string;
    assets?: string[];
    domain_count?: number;
    modules?: string[];
    strategy?: string;
    estimated_cost_savings?: number;
    type?: string;
  };
  results?: {
    scan_type?: string;
    asset_name?: string;
    assets_processed?: number;
    execution_time_seconds?: number;
    strategy_used?: string;
    domains_processed?: number;
    cost_savings_percent?: number;
  };
  error?: string;
}

export interface WebSocketHookReturn {
  isConnected: boolean;
  connectionStatus: 'connecting' | 'connected' | 'disconnected' | 'error';
  lastMessage: BatchProgressMessage | null;
  sendMessage: (message: Record<string, unknown>) => void;
  connect: () => void;
  disconnect: () => void;
  batchProgress: Map<string, BatchProgressMessage>;
}

interface UseWebSocketOptions {
  autoConnect?: boolean;
  reconnectAttempts?: number;
  reconnectInterval?: number;
  onMessage?: (message: BatchProgressMessage) => void;
  onConnect?: () => void;
  onDisconnect?: () => void;
  onError?: (error: Event) => void;
}

export function useWebSocket(options: UseWebSocketOptions = {}): WebSocketHookReturn {
  const {
    autoConnect = true,
    reconnectAttempts = 5,
    reconnectInterval = 3000,
    onMessage,
    onConnect,
    onDisconnect,
    onError
  } = options;

  // State
  const [isConnected, setIsConnected] = useState(false);
  const [connectionStatus, setConnectionStatus] = useState<'connecting' | 'connected' | 'disconnected' | 'error'>('disconnected');
  const [lastMessage, setLastMessage] = useState<BatchProgressMessage | null>(null);
  
  // Fix: Use useMemo to create stable Map reference
  const batchProgress = useMemo(() => new Map<string, BatchProgressMessage>(), []);

  // Refs for WebSocket and reconnection
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const reconnectCountRef = useRef(0);
  const isConnectingRef = useRef(false);
  const mountedRef = useRef(true);

  // Memoize callback options to prevent unnecessary re-renders
  const stableOnMessage = useRef(onMessage);
  const stableOnConnect = useRef(onConnect);
  const stableOnDisconnect = useRef(onDisconnect);
  const stableOnError = useRef(onError);

  // Update refs when options change
  useEffect(() => {
    stableOnMessage.current = onMessage;
    stableOnConnect.current = onConnect;
    stableOnDisconnect.current = onDisconnect;
    stableOnError.current = onError;
  }, [onMessage, onConnect, onDisconnect, onError]);

  // Get authentication token for WebSocket connections
  const getAuthToken = useCallback(async (): Promise<string | null> => {
    if (typeof window === 'undefined') return null;
    
    try {
      // Check if we have a valid cached token
      const now = Date.now();
      if (globalWebSocketTokenCache && globalWebSocketTokenCache.expiresAt > now + 60000) { // 1 minute buffer
        return globalWebSocketTokenCache.token;
      }
      
      // Fetch new token from backend
      const { API_BASE_URL } = await import('../api/config');
      const response = await fetch(`${API_BASE_URL}/api/v1/auth/websocket-token`, {
        method: 'GET',
        credentials: 'include', // Include httpOnly cookies
        headers: {
          'Content-Type': 'application/json',
        },
      });
      
      if (!response.ok) {
        if (response.status === 401) {
          console.warn('⚠️ WebSocket token request failed: User not authenticated');
          return null;
        }
        throw new Error(`Failed to fetch WebSocket token: ${response.status}`);
      }
      
      const tokenData = await response.json();
      
      // Cache the token with expiration
      globalWebSocketTokenCache = {
        token: tokenData.websocket_token,
        expiresAt: now + (tokenData.expires_in * 1000) // Convert seconds to milliseconds
      };
      
      console.log('🔑 WebSocket token obtained and cached');
      return tokenData.websocket_token;
      
    } catch (error) {
      console.error('❌ Failed to obtain WebSocket token:', error);
      return null;
    }
  }, []);

  // Build WebSocket URL with token
  const getWebSocketUrl = useCallback(async (): Promise<string | null> => {
    // Use the same API configuration as the rest of the app
    const { API_BASE_URL } = await import('../api/config');
    
    // Convert HTTP(S) URL to WebSocket URL
    const protocol = API_BASE_URL.startsWith('https:') ? 'wss:' : 'ws:';
    const host = API_BASE_URL.replace(/^https?:\/\//, '');
    
    // Get token for WebSocket authentication
    const token = await getAuthToken();
    if (!token) {
      console.warn('⚠️ No WebSocket token available for connection');
      return null;
    }
    
    const tokenParam = `?token=${encodeURIComponent(token)}`;
    
    return `${protocol}//${host}/api/v1/ws/batch-progress${tokenParam}`;
  }, [getAuthToken]);

  // Handle incoming WebSocket messages
  const handleMessage = useCallback((event: MessageEvent) => {
    if (!mountedRef.current) return; // Prevent updates after unmount
    
    try {
      const message: BatchProgressMessage = JSON.parse(event.data);
      
      setLastMessage(message);
      
      // Store batch progress updates
      if (message.type === 'batch_progress' && message.batch_id) {
        batchProgress.set(message.batch_id, message);
      }
      
      // Handle different message types
      switch (message.type) {
        case 'connection_established':
          console.log('🔌 WebSocket connection established');
          break;
          
        case 'batch_progress':
          if (message.status === 'started') {
            toast.success(
              `Batch scan started: ${message.batch_info?.asset_name || 'Multiple assets'}`,
              {
                description: `Processing ${message.batch_info?.domain_count || 0} domains with ${message.batch_info?.strategy || 'batch processing'}`
              }
            );
          } else if (message.status === 'completed') {
            toast.success(
              `Batch scan completed: ${message.results?.asset_name || 'Multi-asset scan'}`,
              {
                description: `Processed ${message.results?.domains_processed || message.results?.assets_processed || 0} ${message.results?.domains_processed ? 'domains' : 'assets'} in ${message.results?.execution_time_seconds?.toFixed(1) || 0}s`
              }
            );
          } else if (message.status === 'failed') {
            toast.error(
              'Batch scan failed',
              {
                description: message.error || 'Unknown error occurred'
              }
            );
          }
          break;
          
        case 'error':
          console.error('WebSocket error message:', message.message);
          toast.error('WebSocket Error', {
            description: message.message || 'Unknown WebSocket error'
          });
          break;
          
        case 'test_notification':
          toast.info('Test Notification', {
            description: message.message || 'WebSocket test message'
          });
          break;
      }
      
      // Call custom message handler
      stableOnMessage.current?.(message);
      
    } catch (error) {
      console.error('Failed to parse WebSocket message:', error);
    }
  }, [batchProgress]); // Only depend on stable batchProgress

  // Connect to WebSocket
  const connect = useCallback(async () => {
    if (!mountedRef.current || isConnectingRef.current || wsRef.current?.readyState === WebSocket.OPEN) {
      return;
    }

    isConnectingRef.current = true;
    setConnectionStatus('connecting');

    try {
      const wsUrl = await getWebSocketUrl();
      if (!wsUrl) {
        setConnectionStatus('error');
        isConnectingRef.current = false;
        return;
      }
      console.log('🔌 Connecting to WebSocket:', wsUrl);
      
      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;

      ws.onopen = () => {
        if (!mountedRef.current) return;
        
        console.log('✅ WebSocket connected');
        setIsConnected(true);
        setConnectionStatus('connected');
        isConnectingRef.current = false;
        reconnectCountRef.current = 0;
        
        // Send ping to test connection
        ws.send(JSON.stringify({
          type: 'ping',
          timestamp: new Date().toISOString()
        }));
        
        stableOnConnect.current?.();
      };

      ws.onmessage = handleMessage;

      ws.onclose = (event) => {
        if (!mountedRef.current) return;
        
        console.log('🔌 WebSocket disconnected:', event.code, event.reason);
        setIsConnected(false);
        setConnectionStatus('disconnected');
        isConnectingRef.current = false;
        wsRef.current = null;
        
        stableOnDisconnect.current?.();
        
        // Attempt reconnection if not manually disconnected and component is still mounted
        if (event.code !== 1000 && reconnectCountRef.current < reconnectAttempts && mountedRef.current) {
          console.log(`🔄 Attempting reconnection ${reconnectCountRef.current + 1}/${reconnectAttempts}...`);
          reconnectCountRef.current++;
          
          reconnectTimeoutRef.current = setTimeout(async () => {
            if (mountedRef.current) {
              await connect();
            }
          }, reconnectInterval);
        }
      };

      ws.onerror = (error) => {
        if (!mountedRef.current) return;
        
        console.error('❌ WebSocket error:', error);
        setConnectionStatus('error');
        isConnectingRef.current = false;
        
        stableOnError.current?.(error);
      };

    } catch (error) {
      if (!mountedRef.current) return;
      
      console.error('Failed to create WebSocket connection:', error);
      setConnectionStatus('error');
      isConnectingRef.current = false;
    }
  }, [getWebSocketUrl, handleMessage, reconnectAttempts, reconnectInterval]);

  // Disconnect from WebSocket
  const disconnect = useCallback(() => {
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
      reconnectTimeoutRef.current = null;
    }
    
    if (wsRef.current) {
      wsRef.current.close(1000, 'Manual disconnect');
      wsRef.current = null;
    }
    
    if (mountedRef.current) {
      setIsConnected(false);
      setConnectionStatus('disconnected');
    }
    
    isConnectingRef.current = false;
    reconnectCountRef.current = 0;
  }, []);

  // Send message via WebSocket
  const sendMessage = useCallback((message: Record<string, unknown>) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(message));
    } else {
      console.warn('WebSocket not connected, cannot send message');
    }
  }, []);

  // Auto-connect on mount
  useEffect(() => {
    mountedRef.current = true;
    
    if (autoConnect) {
      connect();
    }

    // Cleanup on unmount
    return () => {
      mountedRef.current = false;
      disconnect();
    };
  }, [autoConnect, connect, disconnect]);

  // Handle reconnection attempts and interval changes
  useEffect(() => {
    // This effect handles changes to reconnection settings without triggering reconnection
    // The actual reconnection logic is handled in the onclose event
  }, [reconnectAttempts, reconnectInterval]);

  return {
    isConnected,
    connectionStatus,
    lastMessage,
    sendMessage,
    connect,
    disconnect,
    batchProgress
  };
}
