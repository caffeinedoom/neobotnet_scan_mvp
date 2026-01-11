'use client';

/**
 * API Documentation & Key Management Page - NeoBot-Net LEAN
 * 
 * Simplified API hub:
 * - One API key per user (one-click generate/delete)
 * - Key can be revealed anytime
 * - API documentation with examples
 */

import { useEffect, useState, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/contexts/AuthContext';
import { apiClient } from '@/lib/api/client';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { 
  Key,
  Copy,
  Check,
  Code2,
  Terminal,
  Plus,
  Trash2,
  Loader2,
  Eye,
  EyeOff
} from 'lucide-react';
import { toast } from 'sonner';

// Types - Simplified for one key per user
interface APIKey {
  id: string;
  key_prefix: string;
  created_at: string;
  last_used_at: string | null;
  is_active: boolean;
}

interface APIKeyWithSecret extends APIKey {
  key: string;
}

export default function APIDocsPage() {
  const router = useRouter();
  const { isAuthenticated, isLoading: authLoading, session } = useAuth();
  const [copied, setCopied] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState('programs');
  
  // API Key State - Simplified for one key
  const [apiKey, setApiKey] = useState<APIKey | null>(null);
  const [revealedKey, setRevealedKey] = useState<string | null>(null);
  const [showKey, setShowKey] = useState(false);
  const [loading, setLoading] = useState(true);
  const [creating, setCreating] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [revealing, setRevealing] = useState(false);

  // Auth redirect
  useEffect(() => {
    if (!isAuthenticated && !authLoading) {
      if (typeof window !== 'undefined' && !window.location.pathname.startsWith('/auth/')) {
        router.push('/');
      }
    }
  }, [isAuthenticated, authLoading, router]);

  // Fetch user's API key
  const fetchApiKey = useCallback(async () => {
    if (!session?.access_token) return;
    
    try {
      setLoading(true);
      const response = await apiClient.get<APIKey | null>('/api/v1/auth/api-key');
      setApiKey(response.data);
      // Clear revealed key when fetching fresh data
      setRevealedKey(null);
      setShowKey(false);
    } catch (error) {
      console.error('Failed to fetch API key:', error);
      // 404 means no key exists, which is fine
      setApiKey(null);
    } finally {
      setLoading(false);
    }
  }, [session?.access_token]);

  useEffect(() => {
    if (isAuthenticated && session?.access_token) {
      fetchApiKey();
    }
  }, [isAuthenticated, session?.access_token, fetchApiKey]);

  // Create API key (one-click)
  const createApiKey = async () => {
    if (!session?.access_token) return;
    
    try {
      setCreating(true);
      const response = await apiClient.post<APIKeyWithSecret>('/api/v1/auth/api-key');
      
      // Set the key and reveal it immediately
      setApiKey(response.data);
      setRevealedKey(response.data.key);
      setShowKey(true);
      
      toast.success('API key created!');
    } catch (error: unknown) {
      console.error('Failed to create API key:', error);
      const errorMessage = error instanceof Error ? error.message : 'Failed to create API key';
      toast.error(errorMessage);
    } finally {
      setCreating(false);
    }
  };

  // Reveal API key
  const revealApiKey = async () => {
    if (!session?.access_token || revealedKey) {
      setShowKey(!showKey);
      return;
    }
    
    try {
      setRevealing(true);
      const response = await apiClient.get<APIKeyWithSecret>('/api/v1/auth/api-key/reveal');
      setRevealedKey(response.data.key);
      setShowKey(true);
    } catch (error) {
      console.error('Failed to reveal API key:', error);
      toast.error('Failed to reveal API key');
    } finally {
      setRevealing(false);
    }
  };

  // Delete API key
  const deleteApiKey = async () => {
    if (!session?.access_token) return;
    
    try {
      setDeleting(true);
      await apiClient.delete('/api/v1/auth/api-key');
      setApiKey(null);
      setRevealedKey(null);
      setShowKey(false);
      toast.success('API key deleted');
    } catch (error) {
      console.error('Failed to delete API key:', error);
      toast.error('Failed to delete API key');
    } finally {
      setDeleting(false);
    }
  };

  const copyToClipboard = async (text: string, key: string) => {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(key);
      toast.success('Copied to clipboard!');
      setTimeout(() => setCopied(null), 2000);
    } catch {
      toast.error('Failed to copy');
    }
  };

  const CodeBlock = ({ code, id }: { code: string; id: string }) => (
    <div className="relative">
      <pre className="bg-zinc-950 text-zinc-100 rounded-lg p-4 overflow-x-auto text-sm">
        <code>{code}</code>
      </pre>
      <Button
        size="sm"
        variant="ghost"
        className="absolute top-2 right-2 h-8 w-8 p-0 hover:bg-zinc-800"
        onClick={() => copyToClipboard(code, id)}
      >
        {copied === id ? (
          <Check className="h-4 w-4 text-green-500" />
        ) : (
          <Copy className="h-4 w-4 text-zinc-400" />
        )}
      </Button>
    </div>
  );

  if (!isAuthenticated && !authLoading) {
    return null;
  }

  // Correct base URL
  const baseUrl = 'https://aldous-api.neobotnet.com';

  return (
    <div className="mx-auto max-w-5xl px-4 sm:px-6 lg:px-8 py-8">
      <div className="space-y-8">
        {/* Header */}
        <div>
          <h1 className="text-3xl font-bold tracking-tight flex items-center gap-3">
            <Code2 className="h-8 w-8 text-primary" />
            API Access
          </h1>
          <p className="text-muted-foreground mt-2 max-w-2xl">
            Generate API keys to access reconnaissance data programmatically.
            Perfect for CLI tools, scripts, and integrations.
          </p>
        </div>

        {/* API Key Management Section - Simplified One Key */}
        <Card className="border-primary/20">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Key className="h-5 w-5" />
              Your API Key
            </CardTitle>
            <CardDescription>
              One API key for all programmatic access
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            {loading ? (
              <div className="flex items-center justify-center py-8">
                <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
              </div>
            ) : apiKey ? (
              /* Has API Key - Show with reveal/delete options */
              <div className="space-y-4">
                <div className="flex items-center gap-3 p-4 bg-muted/50 rounded-lg">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-2">
                      <Badge variant="secondary" className="bg-green-500/10 text-green-600 dark:text-green-400">
                        Active
                      </Badge>
                      <span className="text-xs text-muted-foreground">
                        Created {new Date(apiKey.created_at).toLocaleDateString()}
                      </span>
                      {apiKey.last_used_at && (
                        <span className="text-xs text-muted-foreground">
                          · Last used {new Date(apiKey.last_used_at).toLocaleDateString()}
                        </span>
                      )}
                    </div>
                    
                    {/* Key display with reveal toggle */}
                    <div className="flex items-center gap-2">
                      <code className="flex-1 bg-zinc-950 text-zinc-100 px-3 py-2 rounded font-mono text-sm overflow-hidden">
                        {showKey && revealedKey ? revealedKey : apiKey.key_prefix}
                      </code>
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={revealApiKey}
                        disabled={revealing}
                        title={showKey ? "Hide key" : "Reveal key"}
                      >
                        {revealing ? (
                          <Loader2 className="h-4 w-4 animate-spin" />
                        ) : showKey ? (
                          <EyeOff className="h-4 w-4" />
                        ) : (
                          <Eye className="h-4 w-4" />
                        )}
                      </Button>
                      {revealedKey && (
                        <Button
                          size="sm"
                          onClick={() => copyToClipboard(revealedKey, 'api-key')}
                          title="Copy to clipboard"
                        >
                          {copied === 'api-key' ? (
                            <Check className="h-4 w-4 text-green-500" />
                          ) : (
                            <Copy className="h-4 w-4" />
                          )}
                        </Button>
                      )}
                    </div>
                  </div>
                </div>

                {/* Delete button */}
                <div className="flex justify-end">
                  <Button
                    variant="outline"
                    size="sm"
                    className="text-destructive hover:text-destructive hover:bg-destructive/10"
                    onClick={deleteApiKey}
                    disabled={deleting}
                  >
                    {deleting ? (
                      <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                    ) : (
                      <Trash2 className="h-4 w-4 mr-2" />
                    )}
                    Delete Key
                  </Button>
                </div>
              </div>
            ) : (
              /* No API Key - Show create button */
              <div className="text-center py-8 space-y-4">
                <div>
                  <Key className="h-12 w-12 mx-auto mb-3 text-muted-foreground/50" />
                  <p className="text-muted-foreground">
                    No API key yet. Generate one to access the API programmatically.
                  </p>
                </div>
                <Button onClick={createApiKey} disabled={creating} size="lg">
                  {creating ? (
                    <Loader2 className="h-5 w-5 mr-2 animate-spin" />
                  ) : (
                    <Plus className="h-5 w-5 mr-2" />
                  )}
                  Generate API Key
                </Button>
              </div>
            )}
          </CardContent>
        </Card>

        {/* Authentication Docs */}
        <Card>
          <CardHeader>
            <CardTitle>Authentication</CardTitle>
            <CardDescription>
              Include your API key in the request header
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <p className="text-sm text-muted-foreground">
              All API requests require authentication. Generate an API key using the form above, 
              then include it in the <code className="text-primary">X-API-Key</code> header.
            </p>
            
            <CodeBlock 
              id="auth-header"
              code={`# Include this header in all requests
X-API-Key: nb_live_your_key_here`}
            />

            <div className="bg-amber-500/10 border border-amber-500/20 rounded-lg p-4">
              <p className="text-sm text-amber-600 dark:text-amber-400">
                <strong>Security Note:</strong> Keep your API key secret. 
                Never expose it in client-side code or public repositories.
              </p>
            </div>
          </CardContent>
        </Card>

        {/* Base URL */}
        <Card>
          <CardHeader>
            <CardTitle>Base URL</CardTitle>
          </CardHeader>
          <CardContent>
            <CodeBlock 
              id="base-url"
              code={baseUrl}
            />
          </CardContent>
        </Card>

        {/* Endpoints */}
        <div className="space-y-6">
          <h2 className="text-2xl font-bold">Endpoints</h2>

          <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full">
            <TabsList className="grid w-full grid-cols-5">
              <TabsTrigger value="programs">Programs</TabsTrigger>
              <TabsTrigger value="subdomains">Subdomains</TabsTrigger>
              <TabsTrigger value="dns">DNS</TabsTrigger>
              <TabsTrigger value="probes">Servers</TabsTrigger>
              <TabsTrigger value="urls">URLs</TabsTrigger>
            </TabsList>

            {/* Programs */}
            <TabsContent value="programs" className="space-y-4">
              <Card>
                <CardHeader>
                  <div className="flex items-center gap-2">
                    <Badge variant="secondary">GET</Badge>
                    <code className="text-sm">/api/v1/programs</code>
                  </div>
                  <CardDescription>List all bug bounty programs with pagination</CardDescription>
                </CardHeader>
                <CardContent>
                  <CodeBlock
                    id="list-programs"
                    code={`curl -X GET "${baseUrl}/api/v1/programs?page=1&per_page=25" \\
  -H "X-API-Key: YOUR_API_KEY"`}
                  />
                  
                  <div className="mt-4 space-y-2">
                    <h4 className="font-medium text-sm">Query Parameters</h4>
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="border-b">
                          <th className="text-left py-2">Parameter</th>
                          <th className="text-left py-2">Type</th>
                          <th className="text-left py-2">Description</th>
                        </tr>
                      </thead>
                      <tbody>
                        <tr className="border-b">
                          <td className="py-2"><code>page</code></td>
                          <td className="py-2">integer</td>
                          <td className="py-2">Page number, 1-indexed (default: 1)</td>
                        </tr>
                        <tr className="border-b">
                          <td className="py-2"><code>per_page</code></td>
                          <td className="py-2">integer</td>
                          <td className="py-2">Results per page (default: 25, max: 100)</td>
                        </tr>
                        <tr className="border-b">
                          <td className="py-2"><code>search</code></td>
                          <td className="py-2">string</td>
                          <td className="py-2">Filter by program name</td>
                        </tr>
                        <tr className="border-b">
                          <td className="py-2"><code>include_stats</code></td>
                          <td className="py-2">boolean</td>
                          <td className="py-2">Include domain/subdomain counts (default: true)</td>
                        </tr>
                      </tbody>
                    </table>
                  </div>
                  
                  <details className="mt-4">
                    <summary className="cursor-pointer text-sm font-medium text-muted-foreground hover:text-foreground">
                      Example Response
                    </summary>
                    <pre className="mt-2 bg-zinc-950 text-zinc-100 rounded-lg p-4 text-xs overflow-x-auto">
{`{
  "programs": [
    {
      "id": "uuid",
      "name": "Example Program",
      "description": "https://hackerone.com/example",
      "is_active": true,
      "priority": 3,
      "tags": ["vdp"],
      "domain_count": 15,
      "subdomain_count": 2340,
      "last_scan_date": "2026-01-10T10:00:00Z",
      "created_at": "2025-12-14T10:00:00Z"
    }
  ],
  "pagination": {
    "total": 59,
    "page": 1,
    "per_page": 25,
    "total_pages": 3,
    "has_next": true,
    "has_prev": false
  }
}`}
                    </pre>
                  </details>
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <div className="flex items-center gap-2">
                    <Badge variant="secondary">GET</Badge>
                    <code className="text-sm">/api/v1/programs/:id</code>
                  </div>
                  <CardDescription>Get program details with statistics</CardDescription>
                </CardHeader>
                <CardContent>
                  <CodeBlock
                    id="get-program"
                    code={`curl -X GET "${baseUrl}/api/v1/programs/PROGRAM_ID" \\
  -H "X-API-Key: YOUR_API_KEY"`}
                  />
                  
                  <details className="mt-4">
                    <summary className="cursor-pointer text-sm font-medium text-muted-foreground hover:text-foreground">
                      Example Response
                    </summary>
                    <pre className="mt-2 bg-zinc-950 text-zinc-100 rounded-lg p-4 text-xs overflow-x-auto">
{`{
  "id": "ad9a8a21-6611-4846-bc39-ae803d4053a5",
  "name": "Verisign",
  "description": "https://bugcrowd.com/engagements/verisign",
  "is_active": true,
  "priority": 3,
  "tags": ["cli-created"],
  "domain_count": 4,
  "subdomain_count": 1147,
  "last_scan_date": "2026-01-10T16:20:00Z",
  "created_at": "2026-01-09T22:00:00Z",
  "updated_at": "2026-01-09T22:00:00Z"
}`}
                    </pre>
                  </details>
                </CardContent>
              </Card>
            </TabsContent>

            {/* Subdomains */}
            <TabsContent value="subdomains" className="space-y-4">
              <Card>
                <CardHeader>
                  <div className="flex items-center gap-2">
                    <Badge variant="secondary">GET</Badge>
                    <code className="text-sm">/api/v1/programs/:id/subdomains</code>
                  </div>
                  <CardDescription>Get subdomains for a program</CardDescription>
                </CardHeader>
                <CardContent>
                  <CodeBlock
                    id="get-subdomains"
                    code={`curl -X GET "${baseUrl}/api/v1/programs/PROGRAM_ID/subdomains" \\
  -H "X-API-Key: YOUR_API_KEY" \\
  -G \\
  -d "page=1" \\
  -d "per_page=100" \\
  -d "search=api"`}
                  />
                  
                  <div className="mt-4 space-y-2">
                    <h4 className="font-medium text-sm">Query Parameters</h4>
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="border-b">
                          <th className="text-left py-2">Parameter</th>
                          <th className="text-left py-2">Type</th>
                          <th className="text-left py-2">Description</th>
                        </tr>
                      </thead>
                      <tbody>
                        <tr className="border-b">
                          <td className="py-2"><code>page</code></td>
                          <td className="py-2">integer</td>
                          <td className="py-2">Page number (default: 1)</td>
                        </tr>
                        <tr className="border-b">
                          <td className="py-2"><code>per_page</code></td>
                          <td className="py-2">integer</td>
                          <td className="py-2">Results per page (max: 1000)</td>
                        </tr>
                        <tr className="border-b">
                          <td className="py-2"><code>search</code></td>
                          <td className="py-2">string</td>
                          <td className="py-2">Filter by subdomain name (case-insensitive)</td>
                        </tr>
                      </tbody>
                    </table>
                  </div>

                  <details className="mt-4">
                    <summary className="cursor-pointer text-sm font-medium text-muted-foreground hover:text-foreground">
                      Example Response
                    </summary>
                    <pre className="mt-2 bg-zinc-950 text-zinc-100 rounded-lg p-4 text-xs overflow-x-auto">
{`{
  "subdomains": [
    {
      "id": "f5d49f43-dbbc-495c-87ba-ffaf99182a77",
      "subdomain": "api.example.com",
      "parent_domain": "example.com",
      "discovered_at": "2026-01-09T03:49:41+00:00",
      "scan_job_id": "3e1626cf-0258-4279-8fca-4b45c7a91ea1"
    }
  ],
  "pagination": {
    "total": 1147,
    "page": 1,
    "per_page": 100,
    "total_pages": 12,
    "has_next": true,
    "has_prev": false
  }
}`}
                    </pre>
                    
                    <div className="mt-3 space-y-2">
                      <h4 className="font-medium text-sm">Response Fields</h4>
                      <table className="w-full text-sm">
                        <tbody>
                          <tr className="border-b">
                            <td className="py-2"><code>id</code></td>
                            <td className="py-2">Unique subdomain identifier</td>
                          </tr>
                          <tr className="border-b">
                            <td className="py-2"><code>subdomain</code></td>
                            <td className="py-2">Full subdomain name</td>
                          </tr>
                          <tr className="border-b">
                            <td className="py-2"><code>parent_domain</code></td>
                            <td className="py-2">Root domain the subdomain belongs to</td>
                          </tr>
                          <tr className="border-b">
                            <td className="py-2"><code>discovered_at</code></td>
                            <td className="py-2">ISO 8601 timestamp of discovery</td>
                          </tr>
                          <tr className="border-b">
                            <td className="py-2"><code>scan_job_id</code></td>
                            <td className="py-2">ID of the scan that discovered this subdomain</td>
                          </tr>
                        </tbody>
                      </table>
                    </div>
                  </details>
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <div className="flex items-center gap-2">
                    <Badge variant="secondary">GET</Badge>
                    <code className="text-sm">/api/v1/programs/all/subdomains</code>
                  </div>
                  <CardDescription>Get all subdomains across all programs</CardDescription>
                </CardHeader>
                <CardContent>
                  <CodeBlock
                    id="get-all-subdomains"
                    code={`curl -X GET "${baseUrl}/api/v1/programs/all/subdomains" \\
  -H "X-API-Key: YOUR_API_KEY" \\
  -G \\
  -d "page=1" \\
  -d "per_page=100"`}
                  />
                  <p className="mt-3 text-sm text-muted-foreground">
                    Returns the same response structure as the program-specific endpoint above.
                  </p>
                </CardContent>
              </Card>
            </TabsContent>

            {/* DNS */}
            <TabsContent value="dns" className="space-y-4">
              <Card>
                <CardHeader>
                  <div className="flex items-center gap-2">
                    <Badge variant="secondary">GET</Badge>
                    <code className="text-sm">/api/v1/programs/:id/dns</code>
                  </div>
                  <CardDescription>Get DNS records for a program</CardDescription>
                </CardHeader>
                <CardContent>
                  <CodeBlock
                    id="get-dns"
                    code={`curl -X GET "${baseUrl}/api/v1/programs/PROGRAM_ID/dns" \\
  -H "X-API-Key: YOUR_API_KEY" \\
  -G \\
  -d "page=1" \\
  -d "per_page=100" \\
  -d "record_type=A"`}
                  />
                  
                  <div className="mt-4 space-y-2">
                    <h4 className="font-medium text-sm">Query Parameters</h4>
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="border-b">
                          <th className="text-left py-2">Parameter</th>
                          <th className="text-left py-2">Type</th>
                          <th className="text-left py-2">Description</th>
                        </tr>
                      </thead>
                      <tbody>
                        <tr className="border-b">
                          <td className="py-2"><code>page</code></td>
                          <td className="py-2">integer</td>
                          <td className="py-2">Page number (default: 1)</td>
                        </tr>
                        <tr className="border-b">
                          <td className="py-2"><code>per_page</code></td>
                          <td className="py-2">integer</td>
                          <td className="py-2">Results per page (max: 1000)</td>
                        </tr>
                        <tr className="border-b">
                          <td className="py-2"><code>record_type</code></td>
                          <td className="py-2">string</td>
                          <td className="py-2">Filter by type: A, AAAA, CNAME, MX, TXT</td>
                        </tr>
                        <tr className="border-b">
                          <td className="py-2"><code>subdomain</code></td>
                          <td className="py-2">string</td>
                          <td className="py-2">Filter by subdomain (exact match)</td>
                        </tr>
                      </tbody>
                    </table>
                  </div>

                  <details className="mt-4">
                    <summary className="cursor-pointer text-sm font-medium text-muted-foreground hover:text-foreground">
                      Example Response
                    </summary>
                    <pre className="mt-2 bg-zinc-950 text-zinc-100 rounded-lg p-4 text-xs overflow-x-auto">
{`{
  "dns_records": [
    {
      "id": "53e78102-409e-4d82-8d22-5283e0d6c301",
      "subdomain": "api.example.com",
      "parent_domain": "example.com",
      "record_type": "A",
      "record_value": "72.13.50.38",
      "ttl": 900,
      "resolved_at": "2026-01-11T02:36:26+00:00",
      "cloud_provider": null,
      "cdn_provider": null
    }
  ],
  "pagination": {
    "total": 1653,
    "page": 1,
    "per_page": 100,
    "total_pages": 17,
    "has_next": true,
    "has_prev": false
  }
}`}
                    </pre>
                    
                    <div className="mt-3 space-y-2">
                      <h4 className="font-medium text-sm">Response Fields</h4>
                      <table className="w-full text-sm">
                        <tbody>
                          <tr className="border-b">
                            <td className="py-2"><code>id</code></td>
                            <td className="py-2">Unique DNS record identifier</td>
                          </tr>
                          <tr className="border-b">
                            <td className="py-2"><code>subdomain</code></td>
                            <td className="py-2">Full subdomain name</td>
                          </tr>
                          <tr className="border-b">
                            <td className="py-2"><code>parent_domain</code></td>
                            <td className="py-2">Root domain</td>
                          </tr>
                          <tr className="border-b">
                            <td className="py-2"><code>record_type</code></td>
                            <td className="py-2">DNS record type (A, AAAA, CNAME, MX, TXT)</td>
                          </tr>
                          <tr className="border-b">
                            <td className="py-2"><code>record_value</code></td>
                            <td className="py-2">Resolved value (IP address, hostname, etc.)</td>
                          </tr>
                          <tr className="border-b">
                            <td className="py-2"><code>ttl</code></td>
                            <td className="py-2">Time-to-live in seconds</td>
                          </tr>
                          <tr className="border-b">
                            <td className="py-2"><code>resolved_at</code></td>
                            <td className="py-2">ISO 8601 timestamp of resolution</td>
                          </tr>
                          <tr className="border-b">
                            <td className="py-2"><code>cloud_provider</code></td>
                            <td className="py-2">Detected cloud provider (AWS, GCP, Azure) or null</td>
                          </tr>
                          <tr className="border-b">
                            <td className="py-2"><code>cdn_provider</code></td>
                            <td className="py-2">Detected CDN provider (Cloudflare, Akamai) or null</td>
                          </tr>
                        </tbody>
                      </table>
                    </div>
                  </details>
                </CardContent>
              </Card>
            </TabsContent>

            {/* HTTP Probes */}
            <TabsContent value="probes" className="space-y-4">
              <Card>
                <CardHeader>
                  <div className="flex items-center gap-2">
                    <Badge variant="secondary">GET</Badge>
                    <code className="text-sm">/api/v1/http-probes</code>
                  </div>
                  <CardDescription>Get HTTP probe results with filtering and pagination</CardDescription>
                </CardHeader>
                <CardContent>
                  <CodeBlock
                    id="get-probes"
                    code={`curl -X GET "${baseUrl}/api/v1/http-probes" \\
  -H "X-API-Key: YOUR_API_KEY" \\
  -G \\
  -d "asset_id=PROGRAM_ID" \\
  -d "status_code=200" \\
  -d "limit=100"`}
                  />
                  
                  <div className="mt-4 space-y-2">
                    <h4 className="font-medium text-sm">Query Parameters</h4>
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="border-b">
                          <th className="text-left py-2">Parameter</th>
                          <th className="text-left py-2">Type</th>
                          <th className="text-left py-2">Description</th>
                        </tr>
                      </thead>
                      <tbody>
                        <tr className="border-b">
                          <td className="py-2"><code>asset_id</code></td>
                          <td className="py-2">uuid</td>
                          <td className="py-2">Filter by program ID</td>
                        </tr>
                        <tr className="border-b">
                          <td className="py-2"><code>scan_job_id</code></td>
                          <td className="py-2">uuid</td>
                          <td className="py-2">Filter by scan job ID</td>
                        </tr>
                        <tr className="border-b">
                          <td className="py-2"><code>parent_domain</code></td>
                          <td className="py-2">string</td>
                          <td className="py-2">Filter by apex domain (exact match)</td>
                        </tr>
                        <tr className="border-b">
                          <td className="py-2"><code>status_code</code></td>
                          <td className="py-2">integer</td>
                          <td className="py-2">Filter by HTTP status code</td>
                        </tr>
                        <tr className="border-b">
                          <td className="py-2"><code>subdomain</code></td>
                          <td className="py-2">string</td>
                          <td className="py-2">Filter by subdomain (partial match)</td>
                        </tr>
                        <tr className="border-b">
                          <td className="py-2"><code>technology</code></td>
                          <td className="py-2">string</td>
                          <td className="py-2">Filter by detected technology (e.g., &quot;IIS:10.0&quot;)</td>
                        </tr>
                        <tr className="border-b">
                          <td className="py-2"><code>limit</code></td>
                          <td className="py-2">integer</td>
                          <td className="py-2">Max results (default: 100, max: 1000)</td>
                        </tr>
                        <tr className="border-b">
                          <td className="py-2"><code>offset</code></td>
                          <td className="py-2">integer</td>
                          <td className="py-2">Skip N results for pagination</td>
                        </tr>
                      </tbody>
                    </table>
                  </div>

                  <details className="mt-4">
                    <summary className="cursor-pointer text-sm font-medium text-muted-foreground hover:text-foreground">
                      Example Response
                    </summary>
                    <pre className="mt-2 bg-zinc-950 text-zinc-100 rounded-lg p-4 text-xs overflow-x-auto">
{`{
  "probes": [
    {
      "id": "028eee74-0969-43e3-9e5e-e690c3358888",
      "scan_job_id": "ed37f1ae-47f8-4b2a-b1ca-697497634c03",
      "asset_id": "eb195902-ef52-4dae-8d0d-875ee6ef9661",
      "status_code": 200,
      "url": "https://api.example.com",
      "title": "Example API",
      "webserver": "nginx",
      "content_length": 1234,
      "final_url": null,
      "ip": "104.18.6.107",
      "technologies": ["Cloudflare", "HSTS", "nginx"],
      "cdn_name": "cloudflare",
      "content_type": "application/json",
      "asn": null,
      "chain_status_codes": [],
      "location": null,
      "favicon_md5": null,
      "subdomain": "api.example.com",
      "parent_domain": "example.com",
      "scheme": "https",
      "port": 443,
      "created_at": "2026-01-11T03:18:53+00:00"
    }
  ],
  "total": 53225,
  "limit": 100,
  "offset": 0
}`}
                    </pre>
                    
                    <div className="mt-3 space-y-2">
                      <h4 className="font-medium text-sm">Key Response Fields</h4>
                      <table className="w-full text-sm">
                        <tbody>
                          <tr className="border-b">
                            <td className="py-2"><code>status_code</code></td>
                            <td className="py-2">HTTP response status code</td>
                          </tr>
                          <tr className="border-b">
                            <td className="py-2"><code>url</code></td>
                            <td className="py-2">Full URL that was probed</td>
                          </tr>
                          <tr className="border-b">
                            <td className="py-2"><code>title</code></td>
                            <td className="py-2">HTML page title (if extracted)</td>
                          </tr>
                          <tr className="border-b">
                            <td className="py-2"><code>webserver</code></td>
                            <td className="py-2">Detected web server (nginx, Apache, IIS)</td>
                          </tr>
                          <tr className="border-b">
                            <td className="py-2"><code>technologies</code></td>
                            <td className="py-2">Array of detected technologies</td>
                          </tr>
                          <tr className="border-b">
                            <td className="py-2"><code>cdn_name</code></td>
                            <td className="py-2">CDN provider if detected</td>
                          </tr>
                          <tr className="border-b">
                            <td className="py-2"><code>final_url</code></td>
                            <td className="py-2">Final URL after redirects (if any)</td>
                          </tr>
                          <tr className="border-b">
                            <td className="py-2"><code>chain_status_codes</code></td>
                            <td className="py-2">Status codes in redirect chain</td>
                          </tr>
                        </tbody>
                      </table>
                    </div>
                  </details>
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <div className="flex items-center gap-2">
                    <Badge variant="secondary">GET</Badge>
                    <code className="text-sm">/api/v1/http-probes/stats/summary</code>
                  </div>
                  <CardDescription>Get aggregate statistics for HTTP probes</CardDescription>
                </CardHeader>
                <CardContent>
                  <CodeBlock
                    id="get-probes-stats"
                    code={`curl -X GET "${baseUrl}/api/v1/http-probes/stats/summary" \\
  -H "X-API-Key: YOUR_API_KEY" \\
  -G \\
  -d "asset_id=PROGRAM_ID"`}
                  />
                  <p className="mt-3 text-sm text-muted-foreground">
                    Returns pre-computed aggregates: total count, status code distribution, top technologies, web servers, and CDN usage.
                  </p>
                </CardContent>
              </Card>
            </TabsContent>

            {/* URLs */}
            <TabsContent value="urls" className="space-y-4">
              <Card>
                <CardHeader>
                  <div className="flex items-center gap-2">
                    <Badge variant="secondary">GET</Badge>
                    <code className="text-sm">/api/v1/urls</code>
                  </div>
                  <CardDescription>Get discovered URLs with filtering and pagination</CardDescription>
                </CardHeader>
                <CardContent>
                  <CodeBlock
                    id="get-urls"
                    code={`curl -X GET "${baseUrl}/api/v1/urls" \\
  -H "X-API-Key: YOUR_API_KEY" \\
  -G \\
  -d "asset_id=PROGRAM_ID" \\
  -d "is_alive=true" \\
  -d "status_code=200" \\
  -d "limit=100"`}
                  />

                  <div className="mt-4 p-3 bg-yellow-500/10 border border-yellow-500/20 rounded-lg">
                    <p className="text-sm text-yellow-600 dark:text-yellow-400">
                      <strong>⚠️ Important:</strong> Always filter by <code>asset_id</code> to avoid timeouts. 
                      The URLs dataset is very large and unfiltered queries may fail.
                    </p>
                  </div>
                  
                  <div className="mt-4 space-y-2">
                    <h4 className="font-medium text-sm">Query Parameters</h4>
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="border-b">
                          <th className="text-left py-2">Parameter</th>
                          <th className="text-left py-2">Type</th>
                          <th className="text-left py-2">Description</th>
                        </tr>
                      </thead>
                      <tbody>
                        <tr className="border-b">
                          <td className="py-2"><code>asset_id</code></td>
                          <td className="py-2">uuid</td>
                          <td className="py-2">Filter by program/asset ID <strong>(recommended)</strong></td>
                        </tr>
                        <tr className="border-b">
                          <td className="py-2"><code>is_alive</code></td>
                          <td className="py-2">boolean</td>
                          <td className="py-2">Filter by alive status (true/false)</td>
                        </tr>
                        <tr className="border-b">
                          <td className="py-2"><code>status_code</code></td>
                          <td className="py-2">integer</td>
                          <td className="py-2">Filter by HTTP status code</td>
                        </tr>
                        <tr className="border-b">
                          <td className="py-2"><code>has_params</code></td>
                          <td className="py-2">boolean</td>
                          <td className="py-2">Filter by URLs with query parameters</td>
                        </tr>
                        <tr className="border-b">
                          <td className="py-2"><code>search</code></td>
                          <td className="py-2">string</td>
                          <td className="py-2">Search in URL, domain, or title</td>
                        </tr>
                        <tr className="border-b">
                          <td className="py-2"><code>limit</code></td>
                          <td className="py-2">integer</td>
                          <td className="py-2">Max results (default: 100, max: 1000)</td>
                        </tr>
                        <tr className="border-b">
                          <td className="py-2"><code>offset</code></td>
                          <td className="py-2">integer</td>
                          <td className="py-2">Skip N results for pagination</td>
                        </tr>
                      </tbody>
                    </table>
                  </div>

                  <details className="mt-4">
                    <summary className="cursor-pointer text-sm font-medium text-muted-foreground hover:text-foreground">
                      Example Response
                    </summary>
                    <pre className="mt-2 bg-zinc-950 text-zinc-100 rounded-lg p-4 text-xs overflow-x-auto">
{`{
  "urls": [
    {
      "id": "02905c83-52ee-4441-963f-e7408f8a86f8",
      "asset_id": "ad9a8a21-6611-4846-bc39-ae803d4053a5",
      "url": "https://example.com/api/users",
      "domain": "example.com",
      "path": "/api/users",
      "query_params": {},
      "is_alive": true,
      "status_code": 200,
      "content_type": "application/json",
      "content_length": 1234,
      "response_time_ms": 156,
      "title": "API Response",
      "final_url": null,
      "redirect_chain": [],
      "webserver": "nginx",
      "technologies": ["nginx", "HSTS"],
      "has_params": false,
      "file_extension": null,
      "first_discovered_at": "2026-01-09T05:34:57+00:00",
      "created_at": "2026-01-09T05:34:57+00:00"
    }
  ],
  "total": 4829,
  "limit": 100,
  "offset": 0,
  "quota": {
    "plan_type": "pro",
    "urls_limit": null,
    "urls_viewed": 0,
    "urls_remaining": null,
    "is_limited": false
  }
}`}
                    </pre>
                    
                    <div className="mt-3 space-y-2">
                      <h4 className="font-medium text-sm">Key Response Fields</h4>
                      <table className="w-full text-sm">
                        <tbody>
                          <tr className="border-b">
                            <td className="py-2"><code>url</code></td>
                            <td className="py-2">Full discovered URL</td>
                          </tr>
                          <tr className="border-b">
                            <td className="py-2"><code>is_alive</code></td>
                            <td className="py-2">Whether URL responds successfully</td>
                          </tr>
                          <tr className="border-b">
                            <td className="py-2"><code>status_code</code></td>
                            <td className="py-2">HTTP response status code</td>
                          </tr>
                          <tr className="border-b">
                            <td className="py-2"><code>technologies</code></td>
                            <td className="py-2">Detected technologies array</td>
                          </tr>
                          <tr className="border-b">
                            <td className="py-2"><code>has_params</code></td>
                            <td className="py-2">Whether URL has query parameters</td>
                          </tr>
                          <tr className="border-b">
                            <td className="py-2"><code>file_extension</code></td>
                            <td className="py-2">Detected file extension (e.g., .html, .js)</td>
                          </tr>
                          <tr className="border-b">
                            <td className="py-2"><code>quota</code></td>
                            <td className="py-2">Your plan&apos;s URL viewing quota info</td>
                          </tr>
                        </tbody>
                      </table>
                    </div>
                  </details>
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <div className="flex items-center gap-2">
                    <Badge variant="secondary">GET</Badge>
                    <code className="text-sm">/api/v1/urls/stats</code>
                  </div>
                  <CardDescription>Get aggregate URL statistics</CardDescription>
                </CardHeader>
                <CardContent>
                  <CodeBlock
                    id="get-url-stats"
                    code={`curl -X GET "${baseUrl}/api/v1/urls/stats" \\
  -H "X-API-Key: YOUR_API_KEY" \\
  -G \\
  -d "asset_id=PROGRAM_ID"`}
                  />
                  <p className="mt-3 text-sm text-muted-foreground">
                    Filter by <code>asset_id</code> to get stats for a specific program.
                  </p>
                  
                  <details className="mt-4">
                    <summary className="cursor-pointer text-sm font-medium text-muted-foreground hover:text-foreground">
                      Example Response
                    </summary>
                    <pre className="mt-2 bg-zinc-950 text-zinc-100 rounded-lg p-4 text-xs overflow-x-auto">
{`{
  "total_urls": 359168,
  "alive_urls": 331137,
  "dead_urls": 28031,
  "pending_urls": 0,
  "urls_with_params": 120470,
  "unique_domains": 48767,
  "top_status_codes": [
    {"status_code": 200, "count": 215709},
    {"status_code": 403, "count": 85463},
    {"status_code": 404, "count": 15051}
  ],
  "top_technologies": [
    {"name": "Amazon Web Services", "count": 227},
    {"name": "Cloudflare", "count": 158}
  ],
  "top_file_extensions": [
    {"extension": ".html", "count": 5693},
    {"extension": ".js", "count": 1739}
  ]
}`}
                    </pre>
                  </details>
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <div className="flex items-center gap-2">
                    <Badge variant="secondary">GET</Badge>
                    <code className="text-sm">/api/v1/urls/:id</code>
                  </div>
                  <CardDescription>Get a specific URL by ID</CardDescription>
                </CardHeader>
                <CardContent>
                  <CodeBlock
                    id="get-url-by-id"
                    code={`curl -X GET "${baseUrl}/api/v1/urls/URL_ID" \\
  -H "X-API-Key: YOUR_API_KEY"`}
                  />
                </CardContent>
              </Card>
            </TabsContent>
          </Tabs>
        </div>

        {/* Rate Limits */}
        <Card>
          <CardHeader>
            <CardTitle>Rate Limits</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-sm text-muted-foreground">
              Currently, there are no rate limits. This may change in the future.
              Please be respectful and avoid making excessive requests.
            </p>
          </CardContent>
        </Card>

        {/* Pagination Best Practices */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Terminal className="h-5 w-5" />
              Pagination &amp; Best Practices
            </CardTitle>
            <CardDescription>
              How to efficiently work with large datasets
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-6">
            <div className="bg-amber-500/10 border border-amber-500/20 rounded-lg p-4">
              <p className="text-sm text-amber-600 dark:text-amber-400">
                <strong>Important:</strong> Always use pagination when fetching data. 
                Large datasets (like URLs with 350k+ records) will timeout without filters.
              </p>
            </div>

            <div>
              <h4 className="font-medium text-sm mb-2">Paginate through all programs</h4>
              <CodeBlock
                id="paginate-programs"
                code={`# Fetch page 1
curl -s "${baseUrl}/api/v1/programs?page=1&per_page=25" \\
  -H "X-API-Key: YOUR_API_KEY" | jq '.programs[].name, .pagination'

# Check has_next and increment page until false`}
              />
            </div>

            <div>
              <h4 className="font-medium text-sm mb-2">Export subdomains for a specific program</h4>
              <CodeBlock
                id="export-subdomains"
                code={`# Get subdomains with pagination (max 1000 per page)
curl -s "${baseUrl}/api/v1/programs/PROGRAM_ID/subdomains?page=1&per_page=1000" \\
  -H "X-API-Key: YOUR_API_KEY" | \\
  jq -r '.subdomains[].subdomain' > subdomains.txt`}
              />
            </div>

            <div>
              <h4 className="font-medium text-sm mb-2">Get live servers (200 OK) for a program</h4>
              <CodeBlock
                id="find-live-hosts"
                code={`curl -s "${baseUrl}/api/v1/http-probes?asset_id=PROGRAM_ID&status_code=200&limit=100" \\
  -H "X-API-Key: YOUR_API_KEY" | \\
  jq -r '.probes[].url'`}
              />
            </div>

            <div>
              <h4 className="font-medium text-sm mb-2">Get all HTTP probes and pipe to nuclei</h4>
              <CodeBlock
                id="pipe-example"
                code={`# Get live servers and pipe to nuclei
curl -s "${baseUrl}/api/v1/http-probes?status_code=200&limit=500" \\
  -H "X-API-Key: YOUR_API_KEY" | \\
  jq -r '.probes[].url' | nuclei -t cves/`}
              />
            </div>

            <div>
              <h4 className="font-medium text-sm mb-2">Get DNS CNAME records for takeover analysis</h4>
              <CodeBlock
                id="get-program-dns"
                code={`curl -s "${baseUrl}/api/v1/programs/PROGRAM_ID/dns?record_type=CNAME&per_page=500" \\
  -H "X-API-Key: YOUR_API_KEY" | \\
  jq -r '.dns_records[] | "\\(.subdomain) -> \\(.record_value)"'`}
              />
            </div>

            <div>
              <h4 className="font-medium text-sm mb-2">Export URLs with parameters (always filter by asset)</h4>
              <CodeBlock
                id="export-urls-params"
                code={`# Filter by asset_id to avoid timeout on large datasets
curl -s "${baseUrl}/api/v1/urls?asset_id=PROGRAM_ID&has_params=true&is_alive=true&limit=500" \\
  -H "X-API-Key: YOUR_API_KEY" | \\
  jq -r '.urls[].url' > urls_with_params.txt`}
              />
            </div>

            <div>
              <h4 className="font-medium text-sm mb-2">Bash loop to paginate through all subdomains</h4>
              <CodeBlock
                id="bash-pagination"
                code={`#!/bin/bash
API_KEY="YOUR_API_KEY"
PROGRAM_ID="YOUR_PROGRAM_ID"
PAGE=1

while true; do
  RESPONSE=$(curl -s "${baseUrl}/api/v1/programs/$PROGRAM_ID/subdomains?page=$PAGE&per_page=1000" \\
    -H "X-API-Key: $API_KEY")
  
  echo "$RESPONSE" | jq -r '.subdomains[].subdomain' >> all_subdomains.txt
  
  HAS_NEXT=$(echo "$RESPONSE" | jq -r '.pagination.has_next')
  [ "$HAS_NEXT" != "true" ] && break
  
  PAGE=$((PAGE + 1))
done`}
              />
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
