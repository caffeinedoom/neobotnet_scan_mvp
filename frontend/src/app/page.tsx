'use client';

/**
 * Landing Page - neobotnet
 * 
 * Minimal, data-first landing page showcasing reconnaissance results.
 * "Web Reconnaissance. Delivered."
 */

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { Button } from '@/components/ui/button';
import { useAuth } from '@/contexts/AuthContext';
import { Code2, Globe } from 'lucide-react';

// ============================================================================
// MOCK DATA - Realistic reconnaissance results
// ============================================================================

const MOCK_SUBDOMAINS = [
  { subdomain: 'api.acmecorp.com', discovered: 'Dec 17, 2025' },
  { subdomain: 'staging.acmecorp.com', discovered: 'Dec 17, 2025' },
  { subdomain: 'developer.acmecorp.com', discovered: 'Dec 17, 2025' },
  { subdomain: 'partners-api.acmecorp.com', discovered: 'Dec 16, 2025' },
  { subdomain: 'internal-tools.acmecorp.com', discovered: 'Dec 16, 2025' },
  { subdomain: 'cdn-assets.acmecorp.com', discovered: 'Dec 16, 2025' },
  { subdomain: 'mail.acmecorp.com', discovered: 'Dec 15, 2025' },
  { subdomain: 'vpn.acmecorp.com', discovered: 'Dec 15, 2025' },
  { subdomain: 'jira.acmecorp.com', discovered: 'Dec 15, 2025' },
  { subdomain: 'confluence.acmecorp.com', discovered: 'Dec 14, 2025' },
];

const MOCK_DNS = [
  { subdomain: 'api.acmecorp.com', type: 'A', value: '104.18.20.35', ttl: '300s' },
  { subdomain: 'mail.acmecorp.com', type: 'MX', value: 'aspmx.google.com', ttl: '3600s' },
  { subdomain: 'cdn.acmecorp.com', type: 'CNAME', value: 'd1abc.cloudfront.net', ttl: '86400s' },
  { subdomain: 'staging.acmecorp.com', type: 'A', value: '52.14.123.89', ttl: '300s' },
  { subdomain: 'api.acmecorp.com', type: 'AAAA', value: '2606:4700::6812:1423', ttl: '300s' },
  { subdomain: 'developer.acmecorp.com', type: 'CNAME', value: 'docs.acmecorp.com', ttl: '3600s' },
  { subdomain: 'vpn.acmecorp.com', type: 'A', value: '203.0.113.50', ttl: '600s' },
  { subdomain: 'jira.acmecorp.com', type: 'CNAME', value: 'acmecorp.atlassian.net', ttl: '3600s' },
];

const MOCK_PROBES = [
  { url: 'https://api.acmecorp.com', status: 200, server: 'nginx/1.24', cdn: 'Cloudflare' },
  { url: 'https://staging.acmecorp.com', status: 403, server: 'nginx', cdn: 'AWS' },
  { url: 'https://developer.acmecorp.com', status: 200, server: 'nginx', cdn: 'Fastly' },
  { url: 'https://partners-api.acmecorp.com', status: 200, server: 'gunicorn', cdn: '—' },
  { url: 'https://internal-tools.acmecorp.com', status: 401, server: 'Apache/2.4', cdn: '—' },
  { url: 'https://cdn-assets.acmecorp.com', status: 200, server: 'CloudFront', cdn: 'AWS' },
  { url: 'https://mail.acmecorp.com', status: 301, server: 'gws', cdn: 'Google' },
  { url: 'https://jira.acmecorp.com', status: 200, server: 'Atlassian', cdn: 'Cloudflare' },
];

// ============================================================================
// COMPONENTS
// ============================================================================

// Google Icon SVG
const GoogleIcon = () => (
  <svg className="h-5 w-5" viewBox="0 0 24 24">
    <path
      fill="currentColor"
      d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"
    />
    <path
      fill="currentColor"
      d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
    />
    <path
      fill="currentColor"
      d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"
    />
    <path
      fill="currentColor"
      d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"
    />
  </svg>
);

// X (Twitter) Icon SVG
const XIcon = () => (
  <svg className="h-5 w-5" viewBox="0 0 24 24" fill="currentColor">
    <path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z" />
  </svg>
);

// Status code badge with color coding
const StatusBadge = ({ status }: { status: number }) => {
  const getColor = () => {
    if (status >= 200 && status < 300) return 'text-emerald-400';
    if (status >= 300 && status < 400) return 'text-blue-400';
    if (status >= 400 && status < 500) return 'text-amber-400';
    return 'text-red-400';
  };
  
  return <span className={`font-mono font-semibold ${getColor()}`}>{status}</span>;
};

// DNS Type badge
const TypeBadge = ({ type }: { type: string }) => {
  const colors: Record<string, string> = {
    'A': 'text-cyan-400',
    'AAAA': 'text-purple-400',
    'CNAME': 'text-emerald-400',
    'MX': 'text-amber-400',
    'TXT': 'text-pink-400',
  };
  
  return (
    <span className={`font-mono text-xs font-semibold ${colors[type] || 'text-muted-foreground'}`}>
      {type.padEnd(5)}
    </span>
  );
};

// ============================================================================
// MAIN COMPONENT
// ============================================================================

type TabType = 'subdomains' | 'dns' | 'probes';
type APITabType = 'export' | 'live' | 'dns' | 'nuclei';

const TAB_ORDER: TabType[] = ['subdomains', 'dns', 'probes'];

// API Examples
const API_EXAMPLES: { id: APITabType; label: string; command: string; output: string[] }[] = [
  {
    id: 'export',
    label: 'Export',
    command: `curl -s "https://api.neobotnet.com/v1/programs/all/subdomains" \\
  -H "X-API-Key: YOUR_API_KEY" | jq -r '.[].subdomain' > subs.txt`,
    output: ['Saved 47,832 subdomains to subs.txt'],
  },
  {
    id: 'live',
    label: 'Live Hosts',
    command: `curl -s "https://api.neobotnet.com/v1/http-probes?status_code=200" \\
  -H "X-API-Key: YOUR_API_KEY" | jq -r '.[].url'`,
    output: ['https://api.acmecorp.com', 'https://developer.acmecorp.com', 'https://cdn.acmecorp.com', '...'],
  },
  {
    id: 'dns',
    label: 'DNS',
    command: `curl -s "https://api.neobotnet.com/v1/dns?record_type=CNAME" \\
  -H "X-API-Key: YOUR_API_KEY" | jq '.[] | {sub: .subdomain, target: .value}'`,
    output: ['{"sub": "cdn.acmecorp.com", "target": "d1abc.cloudfront.net"}', '{"sub": "jira.acmecorp.com", "target": "acmecorp.atlassian.net"}', '...'],
  },
  {
    id: 'nuclei',
    label: 'Nuclei',
    command: `curl -s "https://api.neobotnet.com/v1/http-probes?status_code=200" \\
  -H "X-API-Key: YOUR_API_KEY" | jq -r '.[].url' | nuclei -t cves/`,
    output: ['[CVE-2024-XXXX] https://api.acmecorp.com', '[info] Scanning 1,247 targets...', '...'],
  },
];

type ViewMode = 'web' | 'api';

export default function Home() {
  const router = useRouter();
  const { isAuthenticated, isLoading, signInWithGoogle, signInWithTwitter } = useAuth();
  const [viewMode, setViewMode] = useState<ViewMode>('web');
  const [activeTab, setActiveTab] = useState<TabType>('subdomains');
  const [activeAPITab, setActiveAPITab] = useState<APITabType>('export');
  const [autoToggle, setAutoToggle] = useState(true);

  // Auto-toggle through data tabs every 4 seconds (only in web mode, stops when user interacts)
  useEffect(() => {
    if (!autoToggle || viewMode !== 'web') return;
    
    const interval = setInterval(() => {
      setActiveTab(current => {
        const currentIndex = TAB_ORDER.indexOf(current);
        const nextIndex = (currentIndex + 1) % TAB_ORDER.length;
        return TAB_ORDER[nextIndex];
      });
    }, 4000);
    return () => clearInterval(interval);
  }, [autoToggle, viewMode]);

  // Handle manual tab selection (stops auto-toggle)
  const handleTabClick = (tabId: TabType) => {
    setAutoToggle(false);
    setActiveTab(tabId);
  };

  // Handle mode switch
  const handleModeSwitch = (mode: ViewMode) => {
    setViewMode(mode);
    if (mode === 'web') {
      setAutoToggle(true); // Re-enable auto-toggle when switching to web
    }
  };

  useEffect(() => {
    if (isAuthenticated && !isLoading) {
      router.push('/programs');
    }
  }, [isAuthenticated, isLoading, router]);

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
      </div>
    );
  }

  if (isAuthenticated) {
    return null;
  }

  const tabs: { id: TabType; label: string; count: string }[] = [
    { id: 'subdomains', label: 'Subdomains', count: '47,832' },
    { id: 'dns', label: 'DNS Records', count: '124,567' },
    { id: 'probes', label: 'Web Servers', count: '38,291' },
  ];

  return (
    <div className="min-h-screen flex flex-col">
      {/* Background pattern - subtle grid */}
      <div className="fixed inset-0 -z-10">
        <div className="absolute inset-0 bg-background" />
        <div 
          className="absolute inset-0 opacity-[0.03]"
          style={{
            backgroundImage: `url("data:image/svg+xml,%3Csvg width='60' height='60' viewBox='0 0 60 60' xmlns='http://www.w3.org/2000/svg'%3E%3Cg fill='none' fill-rule='evenodd'%3E%3Cg fill='%23ffffff' fill-opacity='1'%3E%3Cpath d='M36 34v-4h-2v4h-4v2h4v4h2v-4h4v-2h-4zm0-30V0h-2v4h-4v2h4v4h2V6h4V4h-4zM6 34v-4H4v4H0v2h4v4h2v-4h4v-2H6zM6 4V0H4v4H0v2h4v4h2V6h4V4H6z'/%3E%3C/g%3E%3C/g%3E%3C/svg%3E")`,
          }}
        />
      </div>

      {/* Main Content */}
      <main className="flex-1 flex flex-col items-center justify-center px-4 py-16">
        <div className="w-full max-w-4xl space-y-12">
          
          {/* Hero Section */}
          <div className="text-center space-y-4">
            {/* Logo/Title */}
            <h1 className="text-6xl sm:text-7xl lg:text-8xl font-bold tracking-tight font-mono text-foreground">
              neobotnet
            </h1>
            
            {/* Mode Toggle: Web | API */}
            <div className="flex justify-center items-center gap-1 pt-2">
              <button 
                onClick={() => handleModeSwitch('web')}
                className={`flex items-center gap-2 px-4 py-2 text-base font-mono font-bold rounded-lg transition-all ${
                  viewMode === 'web' 
                    ? 'text-[--terminal-green] bg-muted' 
                    : 'text-muted-foreground hover:text-foreground'
                }`}
              >
                <Globe className="h-4 w-4" />
                <span>Web</span>
              </button>
              <button 
                onClick={() => handleModeSwitch('api')}
                className={`flex items-center gap-2 px-4 py-2 text-base font-mono font-bold rounded-lg transition-all ${
                  viewMode === 'api' 
                    ? 'text-[--terminal-green] bg-muted' 
                    : 'text-muted-foreground hover:text-foreground'
                }`}
              >
                <Code2 className="h-4 w-4" />
                <span>API</span>
              </button>
            </div>
            
            {/* Tagline */}
            <p className="text-xl sm:text-2xl text-foreground font-bold font-mono tracking-wide pt-2">
              Web Reconnaissance. Delivered.
            </p>

            {/* CTA Buttons */}
            <div className="flex flex-col sm:flex-row gap-3 justify-center pt-4">
              <Button 
                size="lg" 
                onClick={() => signInWithGoogle()}
                className="h-12 px-6 text-base font-mono font-medium bg-foreground text-background hover:bg-foreground/90"
              >
                <GoogleIcon />
                <span className="ml-2">Sign in with Google</span>
              </Button>
              <Button 
                size="lg" 
                variant="outline"
                onClick={() => signInWithTwitter()}
                className="h-12 px-6 text-base font-mono font-medium border-border hover:bg-muted"
              >
                <XIcon />
                <span className="ml-2">Sign in with X</span>
              </Button>
            </div>
          </div>

          {/* Content Area - Switches based on viewMode */}
          <div className="space-y-4 transition-all duration-300">
            {viewMode === 'web' ? (
              <>
                {/* Web Mode: Data Tabs */}
                <div className="flex justify-center">
                  <div className="inline-flex items-center gap-1 p-1 rounded-lg bg-muted/50 border border-border">
                    {tabs.map((tab) => (
                      <button
                        key={tab.id}
                        onClick={() => handleTabClick(tab.id)}
                        className={`
                          px-4 py-2 rounded-md text-sm font-mono font-medium transition-all duration-300
                          ${activeTab === tab.id 
                            ? 'bg-background text-foreground shadow-sm' 
                            : 'text-muted-foreground hover:text-foreground'
                          }
                        `}
                      >
                        {tab.label}
                      </button>
                    ))}
                  </div>
                </div>

                {/* Web Mode: Data Preview */}
                <div className="relative rounded-xl border border-border bg-card overflow-hidden shadow-[0_0_50px_-12px_rgba(0,0,0,0.9)] ring-1 ring-white/5">
                  <div className="h-[360px] overflow-hidden p-4 font-mono text-sm">
                    {activeTab === 'subdomains' && MOCK_SUBDOMAINS.map((item, i) => (
                      <div key={i} className="py-2 hover:bg-muted/20 transition-colors flex">
                        <span className="text-[--terminal-green]">{item.subdomain}</span>
                        <span className="text-muted-foreground ml-auto text-xs">{item.discovered}</span>
                      </div>
                    ))}
                    
                    {activeTab === 'dns' && MOCK_DNS.map((item, i) => (
                      <div key={i} className="py-2 hover:bg-muted/20 transition-colors flex gap-3">
                        <span className="text-[--terminal-green] w-56 truncate">{item.subdomain}</span>
                        <TypeBadge type={item.type} />
                        <span className="text-muted-foreground truncate flex-1">{item.value}</span>
                        <span className="text-muted-foreground/60 text-xs">{item.ttl}</span>
                      </div>
                    ))}
                    
                    {activeTab === 'probes' && MOCK_PROBES.map((item, i) => (
                      <div key={i} className="py-2 hover:bg-muted/20 transition-colors flex gap-3">
                        <StatusBadge status={item.status} />
                        <span className="text-[--terminal-green] truncate flex-1">{item.url}</span>
                        <span className="text-muted-foreground text-xs">[{item.server}]</span>
                        <span className="text-muted-foreground/60 text-xs">{item.cdn}</span>
                      </div>
                    ))}
                  </div>
                  <div className="absolute bottom-0 left-0 right-0 h-24 bg-gradient-to-t from-card via-card/80 to-transparent pointer-events-none" />
                </div>

                {/* Web Mode: Stats */}
                <div className="flex justify-center items-center gap-8 py-4 font-mono">
                  <div className="text-center">
                    <div className="text-2xl sm:text-3xl font-bold text-[--terminal-green]">
                      {tabs.find(t => t.id === activeTab)?.count}
                    </div>
                    <div className="text-xs text-muted-foreground uppercase tracking-wider mt-1">
                      {activeTab === 'subdomains' ? 'subdomains' : activeTab === 'dns' ? 'dns records' : 'web servers'}
                    </div>
                  </div>
                  <div className="h-8 w-px bg-border" />
                  <div className="text-center">
                    <div className="text-2xl sm:text-3xl font-bold text-foreground">156</div>
                    <div className="text-xs text-muted-foreground uppercase tracking-wider mt-1">programs</div>
                  </div>
                </div>

                {/* Web Mode: CTA */}
                <div className="text-center">
                  <Button 
                    variant="link" 
                    className="text-[--terminal-green] hover:text-[--terminal-green]/80 font-bold font-mono"
                    onClick={() => signInWithGoogle()}
                  >
                    Sign in to explore all data →
                  </Button>
                </div>
              </>
            ) : (
              <>
                {/* API Mode: Tabs */}
                <div className="flex justify-center">
                  <div className="inline-flex items-center gap-1 p-1 rounded-lg bg-muted/50 border border-border">
                    {API_EXAMPLES.map((example) => (
                      <button
                        key={example.id}
                        onClick={() => setActiveAPITab(example.id)}
                        className={`px-4 py-2 rounded-md text-sm font-mono font-medium transition-all duration-300 ${
                          activeAPITab === example.id
                            ? 'bg-background text-foreground shadow-sm'
                            : 'text-muted-foreground hover:text-foreground'
                        }`}
                      >
                        {example.label}
                      </button>
                    ))}
                  </div>
                </div>

                {/* API Mode: Terminal */}
                <div className="relative rounded-xl border border-border bg-card overflow-hidden shadow-[0_0_50px_-12px_rgba(0,0,0,0.9)] ring-1 ring-white/5">
                  <div className="px-4 py-3 border-b border-border bg-muted/50 flex items-center gap-2">
                    <div className="flex gap-1.5">
                      <div className="w-3 h-3 rounded-full bg-red-500/80" />
                      <div className="w-3 h-3 rounded-full bg-yellow-500/80" />
                      <div className="w-3 h-3 rounded-full bg-green-500/80" />
                    </div>
                    <span className="text-xs text-muted-foreground font-mono ml-2">terminal</span>
                  </div>
                  <div className="h-[360px] overflow-hidden p-4 font-mono text-sm">
                    <div className="text-muted-foreground whitespace-pre-wrap">
                      <span className="text-[--terminal-green]">$</span> {API_EXAMPLES.find(e => e.id === activeAPITab)?.command}
                    </div>
                    <div className="mt-4 text-foreground/80">
                      {API_EXAMPLES.find(e => e.id === activeAPITab)?.output.map((line, i) => (
                        <div key={i} className={line === '...' ? 'text-muted-foreground' : ''}>{line}</div>
                      ))}
                    </div>
                  </div>
                  <div className="absolute bottom-0 left-0 right-0 h-24 bg-gradient-to-t from-card via-card/80 to-transparent pointer-events-none" />
                </div>

                {/* API Mode: CTA */}
                <div className="text-center pt-4">
                  <Link 
                    href="/api-docs" 
                    className="text-[--terminal-green] hover:text-[--terminal-green]/80 font-bold font-mono transition-colors"
                  >
                    view full api documentation →
                  </Link>
                </div>
              </>
            )}
          </div>
        </div>
      </main>

      {/* Footer */}
      <footer className="py-8 text-center font-mono">
        <p className="text-xs text-muted-foreground">
          Free for security researchers · API access included
        </p>
      </footer>
    </div>
  );
}
