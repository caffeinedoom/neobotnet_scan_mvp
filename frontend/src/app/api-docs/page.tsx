'use client';

/**
 * API Documentation Page - NeoBot-Net LEAN
 * 
 * Simple API documentation for researchers to access recon data.
 */

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/contexts/AuthContext';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { 
  Key,
  Copy,
  Check,
  Code2,
  Terminal
} from 'lucide-react';
import { toast } from 'sonner';

export default function APIDocsPage() {
  const router = useRouter();
  const { isAuthenticated, isLoading } = useAuth();
  const [copied, setCopied] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState('programs');

  // Auth redirect
  useEffect(() => {
    if (!isAuthenticated && !isLoading) {
      if (typeof window !== 'undefined' && !window.location.pathname.startsWith('/auth/')) {
        router.push('/auth/login');
      }
    }
  }, [isAuthenticated, isLoading, router]);

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

  if (!isAuthenticated && !isLoading) {
    return null;
  }

  const baseUrl = 'https://api.neobotnet.com';

  return (
    <div className="mx-auto max-w-5xl px-4 sm:px-6 lg:px-8 py-8">
      <div className="space-y-8">
        {/* Header */}
        <div>
          <h1 className="text-3xl font-bold tracking-tight flex items-center gap-3">
            <Code2 className="h-8 w-8 text-primary" />
            API Documentation
          </h1>
          <p className="text-muted-foreground mt-2 max-w-2xl">
            Access all reconnaissance data programmatically using your API key.
            All endpoints return JSON and require authentication.
          </p>
        </div>

        {/* Authentication */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Key className="h-5 w-5" />
              Authentication
            </CardTitle>
            <CardDescription>
              Include your API key in the request header
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <p className="text-sm text-muted-foreground">
              All API requests require authentication using your API key. 
              You can generate an API key from your{' '}
              <a href="/dashboard" className="text-primary hover:underline">dashboard</a>.
            </p>
            
            <CodeBlock 
              id="auth-header"
              code={`# Include this header in all requests
X-API-Key: your_api_key_here`}
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
                    <code className="text-sm">/v1/programs</code>
                  </div>
                  <CardDescription>List all bug bounty programs</CardDescription>
                </CardHeader>
                <CardContent>
                  <CodeBlock
                    id="list-programs"
                    code={`curl -X GET "${baseUrl}/v1/programs" \\
  -H "X-API-Key: YOUR_API_KEY"`}
                  />
                  
                  <details className="mt-4">
                    <summary className="cursor-pointer text-sm font-medium text-muted-foreground hover:text-foreground">
                      Example Response
                    </summary>
                    <pre className="mt-2 bg-zinc-950 text-zinc-100 rounded-lg p-4 text-xs overflow-x-auto">
{`{
  "programs": [
    {
      "id": "uuid",
      "name": "HackerOne",
      "description": "Bug bounty program",
      "domains": 15,
      "subdomains": 2340,
      "last_scan": "2025-12-14T10:00:00Z"
    }
  ],
  "total": 25
}`}
                    </pre>
                  </details>
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <div className="flex items-center gap-2">
                    <Badge variant="secondary">GET</Badge>
                    <code className="text-sm">/v1/programs/:id</code>
                  </div>
                  <CardDescription>Get program details</CardDescription>
                </CardHeader>
                <CardContent>
                  <CodeBlock
                    id="get-program"
                    code={`curl -X GET "${baseUrl}/v1/programs/PROGRAM_ID" \\
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
                    <code className="text-sm">/v1/programs/:id/subdomains</code>
                  </div>
                  <CardDescription>Get subdomains for a program</CardDescription>
                </CardHeader>
                <CardContent>
                  <CodeBlock
                    id="get-subdomains"
                    code={`curl -X GET "${baseUrl}/v1/programs/PROGRAM_ID/subdomains" \\
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
                    <code className="text-sm">/v1/subdomains</code>
                  </div>
                  <CardDescription>Get all subdomains across all programs</CardDescription>
                </CardHeader>
                <CardContent>
                  <CodeBlock
                    id="get-all-subdomains"
                    code={`curl -X GET "${baseUrl}/v1/subdomains" \\
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
                    <code className="text-sm">/v1/programs/:id/dns</code>
                  </div>
                  <CardDescription>Get DNS records for a program</CardDescription>
                </CardHeader>
                <CardContent>
                  <CodeBlock
                    id="get-dns"
                    code={`curl -X GET "${baseUrl}/v1/programs/PROGRAM_ID/dns" \\
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
                    <code className="text-sm">/v1/programs/:id/probes</code>
                  </div>
                  <CardDescription>Get HTTP probe results for a program</CardDescription>
                </CardHeader>
                <CardContent>
                  <CodeBlock
                    id="get-probes"
                    code={`curl -X GET "${baseUrl}/v1/programs/PROGRAM_ID/probes" \\
  -H "X-API-Key: YOUR_API_KEY" \\
  -G \\
  -d "status_code=200"`}
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
                      </tbody>
                    </table>
                  </div>
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
                code={`curl -s "${baseUrl}/v1/subdomains?per_page=10000" \\
  -H "X-API-Key: YOUR_API_KEY" | \\
  jq -r '.subdomains[].subdomain' > subdomains.txt`}
              />
            </div>

            <div>
              <h4 className="font-medium text-sm mb-2">Find live hosts with specific status</h4>
              <CodeBlock
                id="find-live-hosts"
                code={`curl -s "${baseUrl}/v1/probes?status_code=200" \\
  -H "X-API-Key: YOUR_API_KEY" | \\
  jq -r '.probes[].url'`}
              />
            </div>

            <div>
              <h4 className="font-medium text-sm mb-2">Get DNS records for a specific program</h4>
              <CodeBlock
                id="get-program-dns"
                code={`curl -s "${baseUrl}/v1/programs/PROGRAM_ID/dns?record_type=CNAME" \\
  -H "X-API-Key: YOUR_API_KEY" | \\
  jq '.records[] | {subdomain, value}'`}
              />
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

