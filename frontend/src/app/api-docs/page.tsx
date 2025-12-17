'use client';

/**
 * API Documentation & Key Management Page - NeoBot-Net LEAN
 * 
 * Complete API hub for researchers:
 * - Generate and manage API keys
 * - View API documentation
 * - Copy working examples
 */

import { useEffect, useState, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/contexts/AuthContext';
import { apiClient } from '@/lib/api/client';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Input } from '@/components/ui/input';
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
  EyeOff,
  AlertCircle
} from 'lucide-react';
import { toast } from 'sonner';

// Types
interface APIKey {
  id: string;
  key?: string; // Only present on creation
  key_prefix: string;
  name: string;
  created_at: string;
  last_used_at: string | null;
  is_active: boolean;
}

export default function APIDocsPage() {
  const router = useRouter();
  const { isAuthenticated, isLoading: authLoading, session } = useAuth();
  const [copied, setCopied] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState('programs');
  
  // API Key Management State
  const [apiKeys, setApiKeys] = useState<APIKey[]>([]);
  const [keysLoading, setKeysLoading] = useState(true);
  const [creating, setCreating] = useState(false);
  const [newKeyName, setNewKeyName] = useState('');
  const [newlyCreatedKey, setNewlyCreatedKey] = useState<string | null>(null);
  const [showNewKey, setShowNewKey] = useState(true);
  const [revokingId, setRevokingId] = useState<string | null>(null);

  // Auth redirect
  useEffect(() => {
    if (!isAuthenticated && !authLoading) {
      if (typeof window !== 'undefined' && !window.location.pathname.startsWith('/auth/')) {
        router.push('/auth/login');
      }
    }
  }, [isAuthenticated, authLoading, router]);

  // Fetch API keys
  const fetchApiKeys = useCallback(async () => {
    if (!session?.access_token) return;
    
    try {
      setKeysLoading(true);
      const response = await apiClient.get<APIKey[]>('/api/v1/auth/api-keys');
      setApiKeys(response.data);
    } catch (error) {
      console.error('Failed to fetch API keys:', error);
      toast.error('Failed to load API keys');
    } finally {
      setKeysLoading(false);
    }
  }, [session?.access_token]);

  useEffect(() => {
    if (isAuthenticated && session?.access_token) {
      fetchApiKeys();
    }
  }, [isAuthenticated, session?.access_token, fetchApiKeys]);

  // Create new API key
  const createApiKey = async () => {
    if (!session?.access_token) return;
    
    try {
      setCreating(true);
      const response = await apiClient.post<APIKey & { key: string }>('/api/v1/auth/api-keys', {
        name: newKeyName || 'Default'
      });
      
      // Store the newly created key to show it once
      setNewlyCreatedKey(response.data.key);
      setShowNewKey(true);
      setNewKeyName('');
      
      // Refresh the list
      await fetchApiKeys();
      toast.success('API key created! Copy it now - it won\'t be shown again.');
    } catch (error) {
      console.error('Failed to create API key:', error);
      toast.error('Failed to create API key');
    } finally {
      setCreating(false);
    }
  };

  // Revoke API key
  const revokeApiKey = async (keyId: string) => {
    if (!session?.access_token) return;
    
    try {
      setRevokingId(keyId);
      await apiClient.delete(`/api/v1/auth/api-keys/${keyId}`);
      toast.success('API key revoked');
      await fetchApiKeys();
    } catch (error) {
      console.error('Failed to revoke API key:', error);
      toast.error('Failed to revoke API key');
    } finally {
      setRevokingId(null);
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

        {/* API Key Management Section */}
        <Card className="border-primary/20">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Key className="h-5 w-5" />
              Your API Keys
            </CardTitle>
            <CardDescription>
              Create and manage API keys for programmatic access
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-6">
            {/* Create New Key */}
            <div className="flex gap-3">
              <Input
                placeholder="Key name (e.g., 'CLI Tool', 'CI/CD')"
                value={newKeyName}
                onChange={(e) => setNewKeyName(e.target.value)}
                className="max-w-xs"
                onKeyDown={(e) => e.key === 'Enter' && createApiKey()}
              />
              <Button onClick={createApiKey} disabled={creating}>
                {creating ? (
                  <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                ) : (
                  <Plus className="h-4 w-4 mr-2" />
                )}
                Generate Key
              </Button>
            </div>

            {/* Newly Created Key Alert */}
            {newlyCreatedKey && (
              <div className="bg-green-500/10 border border-green-500/30 rounded-lg p-4 space-y-3">
                <div className="flex items-start gap-2">
                  <AlertCircle className="h-5 w-5 text-green-500 mt-0.5" />
                  <div className="flex-1">
                    <p className="text-sm font-medium text-green-600 dark:text-green-400">
                      New API Key Created
                    </p>
                    <p className="text-xs text-muted-foreground mt-1">
                      Copy this key now. For security, it won't be shown again.
                    </p>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <code className="flex-1 bg-zinc-950 text-zinc-100 px-3 py-2 rounded font-mono text-sm">
                    {showNewKey ? newlyCreatedKey : '•'.repeat(40)}
                  </code>
                  <Button
                    size="sm"
                    variant="ghost"
                    onClick={() => setShowNewKey(!showNewKey)}
                  >
                    {showNewKey ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                  </Button>
                  <Button
                    size="sm"
                    onClick={() => copyToClipboard(newlyCreatedKey, 'new-key')}
                  >
                    {copied === 'new-key' ? (
                      <Check className="h-4 w-4 text-green-500" />
                    ) : (
                      <Copy className="h-4 w-4" />
                    )}
                  </Button>
                </div>
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => setNewlyCreatedKey(null)}
                  className="mt-2"
                >
                  I've copied my key
                </Button>
              </div>
            )}

            {/* Existing Keys List */}
            <div className="space-y-2">
              <h4 className="text-sm font-medium text-muted-foreground">Active Keys</h4>
              {keysLoading ? (
                <div className="flex items-center justify-center py-8">
                  <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
                </div>
              ) : apiKeys.length === 0 ? (
                <div className="text-center py-8 text-muted-foreground">
                  <Key className="h-8 w-8 mx-auto mb-2 opacity-50" />
                  <p className="text-sm">No API keys yet. Create one to get started.</p>
                </div>
              ) : (
                <div className="space-y-2">
                  {apiKeys.filter(k => k.is_active).map((key) => (
                    <div
                      key={key.id}
                      className="flex items-center justify-between p-3 bg-muted/50 rounded-lg"
                    >
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2">
                          <span className="font-medium text-sm">{key.name}</span>
                          <Badge variant="outline" className="text-xs">
                            {key.key_prefix}
                          </Badge>
                        </div>
                        <p className="text-xs text-muted-foreground mt-1">
                          Created {new Date(key.created_at).toLocaleDateString()}
                          {key.last_used_at && (
                            <> · Last used {new Date(key.last_used_at).toLocaleDateString()}</>
                          )}
                        </p>
                      </div>
                      <Button
                        size="sm"
                        variant="ghost"
                        className="text-destructive hover:text-destructive hover:bg-destructive/10"
                        onClick={() => revokeApiKey(key.id)}
                        disabled={revokingId === key.id}
                      >
                        {revokingId === key.id ? (
                          <Loader2 className="h-4 w-4 animate-spin" />
                        ) : (
                          <Trash2 className="h-4 w-4" />
                        )}
                      </Button>
                    </div>
                  ))}
                </div>
              )}
            </div>
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
            <TabsList className="grid w-full grid-cols-4">
              <TabsTrigger value="programs">Programs</TabsTrigger>
              <TabsTrigger value="subdomains">Subdomains</TabsTrigger>
              <TabsTrigger value="dns">DNS</TabsTrigger>
              <TabsTrigger value="probes">HTTP Probes</TabsTrigger>
            </TabsList>

            {/* Programs */}
            <TabsContent value="programs" className="space-y-4">
              <Card>
                <CardHeader>
                  <div className="flex items-center gap-2">
                    <Badge variant="secondary">GET</Badge>
                    <code className="text-sm">/api/v1/programs</code>
                  </div>
                  <CardDescription>List all bug bounty programs</CardDescription>
                </CardHeader>
                <CardContent>
                  <CodeBlock
                    id="list-programs"
                    code={`curl -X GET "${baseUrl}/api/v1/programs" \\
  -H "X-API-Key: YOUR_API_KEY"`}
                  />
                  
                  <details className="mt-4">
                    <summary className="cursor-pointer text-sm font-medium text-muted-foreground hover:text-foreground">
                      Example Response
                    </summary>
                    <pre className="mt-2 bg-zinc-950 text-zinc-100 rounded-lg p-4 text-xs overflow-x-auto">
{`[
  {
    "id": "uuid",
    "name": "Example Program",
    "domains_count": 15,
    "subdomains_count": 2340,
    "created_at": "2025-12-14T10:00:00Z"
  }
]`}
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
                  <CardDescription>Get program details</CardDescription>
                </CardHeader>
                <CardContent>
                  <CodeBlock
                    id="get-program"
                    code={`curl -X GET "${baseUrl}/api/v1/programs/PROGRAM_ID" \\
  -H "X-API-Key: YOUR_API_KEY"`}
                  />
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
                          <td className="py-2">Results per page (max: 100)</td>
                        </tr>
                        <tr className="border-b">
                          <td className="py-2"><code>search</code></td>
                          <td className="py-2">string</td>
                          <td className="py-2">Filter by subdomain name</td>
                        </tr>
                      </tbody>
                    </table>
                  </div>
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
                          <td className="py-2"><code>record_type</code></td>
                          <td className="py-2">string</td>
                          <td className="py-2">Filter by type: A, AAAA, CNAME, MX, TXT</td>
                        </tr>
                        <tr className="border-b">
                          <td className="py-2"><code>subdomain</code></td>
                          <td className="py-2">string</td>
                          <td className="py-2">Filter by subdomain</td>
                        </tr>
                      </tbody>
                    </table>
                  </div>
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
                  <CardDescription>Get HTTP probe results</CardDescription>
                </CardHeader>
                <CardContent>
                  <CodeBlock
                    id="get-probes"
                    code={`curl -X GET "${baseUrl}/api/v1/http-probes" \\
  -H "X-API-Key: YOUR_API_KEY" \\
  -G \\
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
                          <td className="py-2"><code>status_code</code></td>
                          <td className="py-2">integer</td>
                          <td className="py-2">Filter by HTTP status code</td>
                        </tr>
                        <tr className="border-b">
                          <td className="py-2"><code>technology</code></td>
                          <td className="py-2">string</td>
                          <td className="py-2">Filter by detected technology</td>
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
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <div className="flex items-center gap-2">
                    <Badge variant="secondary">GET</Badge>
                    <code className="text-sm">/api/v1/programs/:id/probes</code>
                  </div>
                  <CardDescription>Get HTTP probes for a specific program</CardDescription>
                </CardHeader>
                <CardContent>
                  <CodeBlock
                    id="get-program-probes"
                    code={`curl -X GET "${baseUrl}/api/v1/programs/PROGRAM_ID/probes" \\
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

        {/* CLI Usage */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Terminal className="h-5 w-5" />
              Quick Examples
            </CardTitle>
            <CardDescription>
              Common use cases for researchers
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div>
              <h4 className="font-medium text-sm mb-2">Export all subdomains to a file</h4>
              <CodeBlock
                id="export-subdomains"
                code={`curl -s "${baseUrl}/api/v1/programs/all/subdomains?per_page=10000" \\
  -H "X-API-Key: YOUR_API_KEY" | \\
  jq -r '.subdomains[].subdomain' > subdomains.txt`}
              />
            </div>

            <div>
              <h4 className="font-medium text-sm mb-2">Find live hosts with specific status</h4>
              <CodeBlock
                id="find-live-hosts"
                code={`curl -s "${baseUrl}/api/v1/http-probes?status_code=200&limit=1000" \\
  -H "X-API-Key: YOUR_API_KEY" | \\
  jq -r '.[].url'`}
              />
            </div>

            <div>
              <h4 className="font-medium text-sm mb-2">Get CNAME records for a program</h4>
              <CodeBlock
                id="get-program-dns"
                code={`curl -s "${baseUrl}/api/v1/programs/PROGRAM_ID/dns?record_type=CNAME" \\
  -H "X-API-Key: YOUR_API_KEY" | \\
  jq '.records[] | {subdomain, value}'`}
              />
            </div>

            <div>
              <h4 className="font-medium text-sm mb-2">Pipe to other tools (httpx, nuclei)</h4>
              <CodeBlock
                id="pipe-example"
                code={`# Get live URLs and pipe to nuclei
curl -s "${baseUrl}/api/v1/http-probes?status_code=200" \\
  -H "X-API-Key: YOUR_API_KEY" | \\
  jq -r '.[].url' | nuclei -t cves/`}
              />
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
