'use client';

/**
 * Landing Page - neobotnet
 * 
 * Minimal, data-first landing page showcasing REAL reconnaissance data.
 * Data fetched from public showcase API endpoint (no auth required).
 * "Web Reconnaissance. Delivered."
 */

import { useState, useEffect, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { Button } from '@/components/ui/button';
import { useAuth } from '@/contexts/AuthContext';
import { Code2, Globe, Copy, ExternalLink, Lock } from 'lucide-react';
import { API_BASE_URL } from '@/lib/api/config';

// ============================================================================
// TYPES - Matching backend ShowcaseResponse
// ============================================================================

interface ShowcaseSubdomain {
  subdomain: string;
  parent_domain: string;
  program_name: string;
}

interface ShowcaseDNSRecord {
  subdomain: string;
  record_type: string;
  value: string;
  ttl: number | null;
  program_name: string;
}

interface ShowcaseWebServer {
  url: string;
  status_code: number;
  title: string | null;
  webserver: string | null;
  content_length: number | null;
  technologies: string[];
  program_name: string;
}

interface ShowcaseProgram {
  id: string;
  name: string;
  subdomain_count: number;
  server_count: number;
}

interface ShowcaseStats {
  total_subdomains: number;
  total_dns_records: number;
  total_web_servers: number;
  total_urls: number;
  total_programs: number;
}

interface ShowcaseData {
  subdomains: ShowcaseSubdomain[];
  dns_records: ShowcaseDNSRecord[];
  web_servers: ShowcaseWebServer[];
  programs: ShowcaseProgram[];
  stats: ShowcaseStats;
}

// ============================================================================
// FALLBACK DATA - Used if API fails
// ============================================================================

const FALLBACK_DATA: ShowcaseData = {
  subdomains: [
    { subdomain: 'api.example.com', parent_domain: 'example.com', program_name: 'Demo' },
    { subdomain: 'staging.example.com', parent_domain: 'example.com', program_name: 'Demo' },
    { subdomain: 'developer.example.com', parent_domain: 'example.com', program_name: 'Demo' },
  ],
  dns_records: [
    { subdomain: 'api.example.com', record_type: 'A', value: '104.18.20.35', ttl: 300, program_name: 'Demo' },
    { subdomain: 'mail.example.com', record_type: 'MX', value: 'mail.google.com', ttl: 3600, program_name: 'Demo' },
    { subdomain: 'cdn.example.com', record_type: 'CNAME', value: 'd1.cloudfront.net', ttl: 86400, program_name: 'Demo' },
  ],
  web_servers: [
    { url: 'https://api.example.com', status_code: 200, title: 'API Gateway', webserver: 'nginx', content_length: 2400, technologies: ['React', 'Node.js'], program_name: 'Demo' },
    { url: 'https://staging.example.com', status_code: 403, title: 'Forbidden', webserver: 'nginx', content_length: 512, technologies: [], program_name: 'Demo' },
    { url: 'https://developer.example.com', status_code: 200, title: 'Developer Portal', webserver: 'gunicorn', content_length: 45000, technologies: ['Python', 'Django'], program_name: 'Demo' },
  ],
  programs: [
    { id: '1', name: 'Demo Program', subdomain_count: 1000, server_count: 500 },
  ],
  stats: {
    total_subdomains: 10000,
    total_dns_records: 25000,
    total_web_servers: 5000,
    total_urls: 50000,
    total_programs: 50,
  },
};

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
const StatusBadge = ({ status, large = false }: { status: number; large?: boolean }) => {
  const getStyles = () => {
    if (status >= 200 && status < 300) return 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30';
    if (status >= 300 && status < 400) return 'bg-blue-500/20 text-blue-400 border-blue-500/30';
    if (status >= 400 && status < 500) return 'bg-amber-500/20 text-amber-400 border-amber-500/30';
    return 'bg-red-500/20 text-red-400 border-red-500/30';
  };
  
  return (
    <span className={`font-mono font-bold border rounded px-1.5 py-0.5 ${getStyles()} ${large ? 'text-sm' : 'text-xs'}`}>
      {status}
    </span>
  );
};

// DNS Type badge with background
const TypeBadge = ({ type }: { type: string }) => {
  const styles: Record<string, string> = {
    'A': 'bg-cyan-500/20 text-cyan-400 border-cyan-500/30',
    'AAAA': 'bg-purple-500/20 text-purple-400 border-purple-500/30',
    'CNAME': 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30',
    'MX': 'bg-amber-500/20 text-amber-400 border-amber-500/30',
    'TXT': 'bg-pink-500/20 text-pink-400 border-pink-500/30',
  };
  
  return (
    <span className={`font-mono text-xs font-semibold border rounded px-1.5 py-0.5 ${styles[type] || 'bg-muted text-muted-foreground border-border'}`}>
      {type}
    </span>
  );
};

// Technology badge
const TechBadge = ({ tech }: { tech: string }) => (
  <span className="text-xs font-mono bg-muted/50 text-muted-foreground border border-border rounded px-1.5 py-0.5">
    {tech}
  </span>
);

// Skeleton loading card - subtle pulsing animation
const SkeletonCard = () => (
  <div className="rounded-lg border border-border bg-card/50 p-4 animate-pulse">
    <div className="flex items-center gap-3 mb-3">
      <div className="h-6 w-12 bg-muted rounded" />
      <div className="h-4 flex-1 bg-muted rounded" />
    </div>
    <div className="flex items-center gap-2 mb-3">
      <div className="h-3 w-32 bg-muted/60 rounded" />
      <div className="h-3 w-20 bg-muted/60 rounded" />
    </div>
    <div className="flex gap-1.5">
      <div className="h-5 w-16 bg-muted/40 rounded" />
      <div className="h-5 w-20 bg-muted/40 rounded" />
    </div>
  </div>
);

// ============================================================================
// CARD COMPONENTS - Matching authenticated experience
// ============================================================================

// Web Server Card (matches /probes) - Uses ShowcaseWebServer
const ServerCard = ({ server, fade = false }: { 
  server: ShowcaseWebServer; 
  fade?: boolean;
}) => {
  const formatSize = (bytes: number | null) => {
    if (!bytes) return null;
    if (bytes < 1024) return `${bytes}b`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)}kb`;
    return `${(bytes / 1024 / 1024).toFixed(1)}mb`;
  };

  return (
    <div className={`relative rounded-lg border border-border bg-card/50 p-4 transition-all hover:border-[--terminal-green]/30 ${fade ? 'opacity-60' : ''}`}>
      {/* Header: Status + URL + Actions */}
      <div className="flex items-center gap-3 mb-3">
        <StatusBadge status={server.status_code} large />
        <span className="font-mono text-sm text-[--terminal-green] truncate flex-1">{server.url}</span>
        <div className="flex items-center gap-1 opacity-50">
          <Copy className="h-3.5 w-3.5 text-muted-foreground" />
          <ExternalLink className="h-3.5 w-3.5 text-muted-foreground" />
        </div>
      </div>
      
      {/* Meta: Title, Server, Size */}
      <div className="flex items-center gap-2 text-xs text-muted-foreground mb-3 font-mono">
        {server.title && <span className="text-foreground/80 truncate">{server.title}</span>}
        {server.webserver && (
          <>
            <span>·</span>
            <span>{server.webserver}</span>
          </>
        )}
        {server.content_length && (
          <>
            <span>·</span>
            <span className="text-cyan-400">{formatSize(server.content_length)}</span>
          </>
        )}
        <span className="ml-auto text-muted-foreground/60">{server.program_name}</span>
      </div>
      
      {/* Technologies */}
      {server.technologies.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {server.technologies.slice(0, 5).map((tech, i) => (
            <TechBadge key={i} tech={tech} />
          ))}
          {server.technologies.length > 5 && (
            <span className="text-xs text-muted-foreground">+{server.technologies.length - 5}</span>
          )}
        </div>
      )}
      
      {/* Fade overlay for last card */}
      {fade && (
        <div className="absolute inset-0 bg-gradient-to-b from-transparent via-transparent to-card rounded-lg pointer-events-none" />
      )}
    </div>
  );
};

// DNS Record Card (matches /dns) - Uses ShowcaseDNSRecord
const DNSCard = ({ record, fade = false }: { 
  record: ShowcaseDNSRecord; 
  fade?: boolean;
}) => (
  <div className={`relative rounded-lg border border-border bg-card/50 p-4 transition-all hover:border-[--terminal-green]/30 ${fade ? 'opacity-60' : ''}`}>
    {/* Header: Subdomain + Copy */}
    <div className="flex items-center gap-3 mb-3">
      <Globe className="h-4 w-4 text-[--terminal-green]" />
      <span className="font-mono text-sm text-[--terminal-green] truncate flex-1">{record.subdomain}</span>
      <Copy className="h-3.5 w-3.5 text-muted-foreground opacity-50" />
    </div>
    
    {/* Single Record */}
    <div className="flex items-center gap-2 text-xs font-mono">
      <TypeBadge type={record.record_type} />
      <span className="text-muted-foreground">→</span>
      <span className="text-foreground/80 truncate flex-1">{record.value}</span>
      {record.ttl && <span className="text-muted-foreground/60">TTL: {record.ttl}s</span>}
    </div>
    
    {/* Footer */}
    <div className="mt-3 pt-2 border-t border-border/50 flex items-center justify-between text-xs text-muted-foreground">
      <span>{record.program_name}</span>
    </div>
    
    {fade && (
      <div className="absolute inset-0 bg-gradient-to-b from-transparent via-transparent to-card rounded-lg pointer-events-none" />
    )}
  </div>
);

// Subdomain Card (matches /subdomains) - Uses ShowcaseSubdomain
const SubdomainCard = ({ sub, fade = false }: { 
  sub: ShowcaseSubdomain; 
  fade?: boolean;
}) => (
  <div className={`relative rounded-lg border border-border bg-card/50 p-4 transition-all hover:border-[--terminal-green]/30 ${fade ? 'opacity-60' : ''}`}>
    {/* Header: Subdomain + Actions */}
    <div className="flex items-center gap-3 mb-2">
      <Globe className="h-4 w-4 text-[--terminal-green]" />
      <span className="font-mono text-sm text-[--terminal-green] truncate flex-1">{sub.subdomain}</span>
      <div className="flex items-center gap-1 opacity-50">
        <Copy className="h-3.5 w-3.5 text-muted-foreground" />
        <ExternalLink className="h-3.5 w-3.5 text-muted-foreground" />
      </div>
    </div>
    
    {/* Footer */}
    <div className="flex items-center justify-between text-xs text-muted-foreground font-mono">
      <span>{sub.parent_domain}</span>
      <span>{sub.program_name}</span>
    </div>
    
    {fade && (
      <div className="absolute inset-0 bg-gradient-to-b from-transparent via-transparent to-card rounded-lg pointer-events-none" />
    )}
  </div>
);

// ============================================================================
// MAIN COMPONENT
// ============================================================================

type TabType = 'subdomains' | 'dns' | 'probes' | 'urls';
type APITabType = 'export' | 'live' | 'dns' | 'nuclei';

// Tab order: Web Servers first, then DNS, then Subdomains, then URLs (locked)
const TAB_ORDER: TabType[] = ['probes', 'dns', 'subdomains'];

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

type ViewMode = 'web' | 'api' | 'programs';

// Typing animation text
const TITLE_TEXT = 'neobotnet';
const TAGLINE_TEXT = 'Web Reconnaissance. Delivered.';

export default function Home() {
  const router = useRouter();
  const { isAuthenticated, isLoading, signInWithGoogle, signInWithTwitter } = useAuth();
  const [viewMode, setViewMode] = useState<ViewMode>('web');
  const [activeTab, setActiveTab] = useState<TabType>('probes'); // Start with Web Servers
  const [activeAPITab, setActiveAPITab] = useState<APITabType>('export');
  const [autoToggle, setAutoToggle] = useState(true);
  
  // Showcase data from API
  const [showcaseData, setShowcaseData] = useState<ShowcaseData | null>(null);
  const [isDataLoading, setIsDataLoading] = useState(true);
  
  // Typing animation state
  const [typedTitle, setTypedTitle] = useState('');
  const [typedTagline, setTypedTagline] = useState('');
  const [showCursor, setShowCursor] = useState(true);
  const [typingPhase, setTypingPhase] = useState<'title' | 'tagline' | 'done'>('title');
  
  // Fetch showcase data from public API
  const fetchShowcaseData = useCallback(async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/v1/public/showcase`);
      if (response.ok) {
        const data: ShowcaseData = await response.json();
        setShowcaseData(data);
      } else {
        // API failed, use fallback
        setShowcaseData(FALLBACK_DATA);
      }
    } catch (error) {
      console.warn('Failed to fetch showcase data, using fallback:', error);
      setShowcaseData(FALLBACK_DATA);
    } finally {
      setIsDataLoading(false);
    }
  }, []);
  
  // Fetch data on mount
  useEffect(() => {
    fetchShowcaseData();
  }, [fetchShowcaseData]);

  // Typing animation effect
  useEffect(() => {
    if (typingPhase === 'title') {
      if (typedTitle.length < TITLE_TEXT.length) {
        const timeout = setTimeout(() => {
          setTypedTitle(TITLE_TEXT.slice(0, typedTitle.length + 1));
        }, 80); // Speed of typing
        return () => clearTimeout(timeout);
      } else {
        // Pause before starting tagline
        const timeout = setTimeout(() => setTypingPhase('tagline'), 300);
        return () => clearTimeout(timeout);
      }
    } else if (typingPhase === 'tagline') {
      if (typedTagline.length < TAGLINE_TEXT.length) {
        const timeout = setTimeout(() => {
          setTypedTagline(TAGLINE_TEXT.slice(0, typedTagline.length + 1));
        }, 50); // Slightly faster for tagline
        return () => clearTimeout(timeout);
      } else {
        setTypingPhase('done');
      }
    }
  }, [typedTitle, typedTagline, typingPhase]);

  // Blinking cursor effect
  useEffect(() => {
    const interval = setInterval(() => {
      setShowCursor(prev => !prev);
    }, 530); // Blink speed
    return () => clearInterval(interval);
  }, []);

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

  // Format number with commas
  const formatNumber = (num: number) => num.toLocaleString();
  
  // Get stats safely (handle loading/null state)
  const stats = showcaseData?.stats;
  
  // Tab order: Web Servers, DNS Records, Subdomains, URLs (locked)
  const tabs: { id: TabType; label: string; count: string; locked?: boolean }[] = [
    { id: 'probes', label: 'Web Servers', count: isDataLoading ? '...' : formatNumber(stats?.total_web_servers || 0) },
    { id: 'dns', label: 'DNS Records', count: isDataLoading ? '...' : formatNumber(stats?.total_dns_records || 0) },
    { id: 'subdomains', label: 'Subdomains', count: isDataLoading ? '...' : formatNumber(stats?.total_subdomains || 0) },
    { id: 'urls', label: 'URLs', count: isDataLoading ? '...' : formatNumber(stats?.total_urls || 0), locked: true },
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
            {/* Logo/Title - Typing animation with persistent blinking cursor */}
            <h1 className="text-6xl sm:text-7xl lg:text-8xl font-bold tracking-tight font-mono text-foreground">
              {typedTitle}
              <span className={`${typingPhase === 'done' ? 'text-[--terminal-green]' : ''} ${showCursor ? 'opacity-100' : 'opacity-0'} transition-opacity`}>_</span>
            </h1>
        
            {/* Mode Toggle: Web | API | Programs - Framed for visual clarity */}
            <div className="flex justify-center pt-2">
              <div className="inline-flex items-center gap-1 p-1 rounded-lg bg-muted/50 border border-border">
                <button 
                  onClick={() => handleModeSwitch('web')}
                  className={`flex items-center gap-2 px-4 py-2 text-sm font-mono font-bold rounded-md transition-all ${
                    viewMode === 'web' 
                      ? 'text-[--terminal-green] bg-background shadow-sm' 
                      : 'text-muted-foreground hover:text-foreground'
                  }`}
                >
                  <Globe className="h-4 w-4" />
                  <span>Web</span>
                </button>
                <button 
                  onClick={() => handleModeSwitch('api')}
                  className={`flex items-center gap-2 px-4 py-2 text-sm font-mono font-bold rounded-md transition-all ${
                    viewMode === 'api' 
                      ? 'text-[--terminal-green] bg-background shadow-sm' 
                      : 'text-muted-foreground hover:text-foreground'
                  }`}
                >
                  <Code2 className="h-4 w-4" />
                  <span>API</span>
                </button>
                <button 
                  onClick={() => handleModeSwitch('programs')}
                  className={`flex items-center gap-2 px-4 py-2 text-sm font-mono font-bold rounded-md transition-all ${
                    viewMode === 'programs' 
                      ? 'text-[--terminal-green] bg-background shadow-sm' 
                      : 'text-muted-foreground hover:text-foreground'
                  }`}
                >
                  <span>Programs</span>
                </button>
              </div>
            </div>
            
            {/* Tagline - Typing animation (no cursor, cursor stays on title) */}
            <p className="text-xl sm:text-2xl text-foreground font-bold font-mono tracking-wide pt-2 min-h-[2em]">
              {typingPhase !== 'title' && typedTagline}
            </p>

            {/* CTA Buttons - Dark with inverted hover */}
            <div className="flex flex-col sm:flex-row gap-3 justify-center pt-4">
              <Button 
                size="lg" 
                onClick={() => signInWithGoogle()}
                className="h-12 px-6 text-base font-mono font-medium bg-card text-foreground border border-border hover:bg-foreground hover:text-background hover:border-foreground transition-all"
              >
                <GoogleIcon />
                <span className="ml-2">Sign in with Google</span>
              </Button>
              <Button 
                size="lg" 
                onClick={() => signInWithTwitter()}
                className="h-12 px-6 text-base font-mono font-medium bg-card text-foreground border border-border hover:bg-foreground hover:text-background hover:border-foreground transition-all"
              >
                <XIcon />
                <span className="ml-2">Sign in with X</span>
              </Button>
            </div>
      </div>

          {/* Content Area - Switches based on viewMode */}
          <div className="space-y-4 transition-all duration-300">
            {viewMode === 'web' && (
              <>
                {/* Web Mode: Data Tabs */}
                <div className="flex justify-center">
                  <div className="inline-flex items-center gap-1 p-1 rounded-lg bg-muted/50 border border-border">
                    {tabs.map((tab) => (
                      <button
                        key={tab.id}
                        onClick={() => handleTabClick(tab.id)}
                        className={`
                          px-4 py-2 rounded-md text-sm font-mono font-medium transition-all duration-300 flex items-center gap-1.5
                          ${activeTab === tab.id 
                            ? 'bg-background text-foreground shadow-sm' 
                            : 'text-muted-foreground hover:text-foreground'
                          }
                        `}
                      >
                        {tab.locked && <Lock className="h-3 w-3" />}
                        {tab.label}
                      </button>
                    ))}
                  </div>
                </div>

                {/* Web Mode: Card Display - Fixed height container to prevent page jumping */}
                <div className="relative h-[420px] overflow-hidden">
                  <div className="space-y-3">
                    {/* Loading State - Show skeletons */}
                    {isDataLoading && activeTab !== 'urls' && (
                      <>
                        <SkeletonCard />
                        <SkeletonCard />
                        <SkeletonCard />
                      </>
                    )}
                    
                    {/* Loaded State - Show real data */}
                    {!isDataLoading && showcaseData && activeTab === 'probes' && showcaseData.web_servers.slice(0, 3).map((server, i) => (
                      <ServerCard key={i} server={server} fade={i === 2} />
                    ))}
                    
                    {!isDataLoading && showcaseData && activeTab === 'dns' && showcaseData.dns_records.slice(0, 3).map((record, i) => (
                      <DNSCard key={i} record={record} fade={i === 2} />
                    ))}
                    
                    {!isDataLoading && showcaseData && activeTab === 'subdomains' && showcaseData.subdomains.slice(0, 4).map((sub, i) => (
                      <SubdomainCard key={i} sub={sub} fade={i === 3} />
                    ))}
                    
                    {/* URLs - Locked State */}
                    {activeTab === 'urls' && (
                      <div className="flex flex-col items-center justify-center h-full py-16 text-center">
                        <div className="rounded-full bg-muted/50 p-6 mb-6">
                          <Lock className="h-12 w-12 text-[--terminal-green]" />
                        </div>
                        <h3 className="text-2xl font-bold font-mono text-foreground mb-2">
                          {isDataLoading ? '...' : formatNumber(showcaseData?.stats.total_urls || 0)} URLs Discovered
                        </h3>
                        <p className="text-muted-foreground font-mono max-w-md mb-6">
                          Sign up to explore URLs, parameters, paths, and more curated intelligence from our reconnaissance scans.
                        </p>
                        <Button 
                          size="lg"
                          onClick={() => signInWithGoogle()}
                          className="h-12 px-6 text-base font-mono font-medium bg-[--terminal-green] text-background hover:bg-[--terminal-green]/90 transition-all"
                        >
                          Sign Up to Unlock →
                        </Button>
                      </div>
                    )}
                  </div>
                  
                  {/* Bottom fade gradient - only show for non-locked tabs */}
                  {activeTab !== 'urls' && (
                    <div className="absolute bottom-0 left-0 right-0 h-24 bg-gradient-to-t from-background via-background/80 to-transparent pointer-events-none" />
                  )}
                </div>

                {/* Web Mode: Stats */}
                <div className="flex justify-center items-center gap-8 py-4 font-mono">
                  <div className="text-center">
                    <div className={`text-2xl sm:text-3xl font-bold text-[--terminal-green] ${isDataLoading ? 'animate-pulse' : ''}`}>
                      {tabs.find(t => t.id === activeTab)?.count}
                    </div>
                    <div className="text-xs text-muted-foreground uppercase tracking-wider mt-1">
                      {activeTab === 'subdomains' ? 'subdomains' : activeTab === 'dns' ? 'dns records' : activeTab === 'urls' ? 'urls' : 'web servers'}
                    </div>
                  </div>
                  <div className="h-8 w-px bg-border" />
                  <div className="text-center">
                    <div className={`text-2xl sm:text-3xl font-bold text-foreground ${isDataLoading ? 'animate-pulse' : ''}`}>
                      {isDataLoading ? '...' : stats?.total_programs || 0}
                    </div>
                    <div className="text-xs text-muted-foreground uppercase tracking-wider mt-1">programs</div>
                  </div>
                </div>

                {/* Web Mode: CTA - only show for non-locked tabs */}
                {activeTab !== 'urls' && (
                  <div className="text-center">
                    <Button 
                      variant="link" 
                      className="text-[--terminal-green] hover:text-[--terminal-green]/80 font-bold font-mono"
                      onClick={() => signInWithGoogle()}
                    >
                      Sign in to explore all data →
                    </Button>
                  </div>
                )}
              </>
            )}

            {viewMode === 'api' && (
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

                {/* API Mode: Terminal - Same height as Web mode */}
                <div className="relative rounded-xl border border-border bg-card overflow-hidden shadow-[0_0_50px_-12px_rgba(0,0,0,0.9)] ring-1 ring-white/5">
                  <div className="px-4 py-2 border-b border-border bg-muted/50 flex items-center gap-2">
                    <div className="flex gap-1.5">
                      <div className="w-2.5 h-2.5 rounded-full bg-red-500/80" />
                      <div className="w-2.5 h-2.5 rounded-full bg-yellow-500/80" />
                      <div className="w-2.5 h-2.5 rounded-full bg-green-500/80" />
                    </div>
                    <span className="text-xs text-muted-foreground font-mono ml-2">terminal</span>
                  </div>
                  <div className="h-[248px] overflow-hidden p-4 font-mono text-sm">
                    <div className="text-muted-foreground whitespace-pre-wrap">
                      <span className="text-[--terminal-green]">$</span> {API_EXAMPLES.find(e => e.id === activeAPITab)?.command}
                    </div>
                    <div className="mt-3 text-foreground/80">
                      {API_EXAMPLES.find(e => e.id === activeAPITab)?.output.map((line, i) => (
                        <div key={i} className={line === '...' ? 'text-muted-foreground' : ''}>{line}</div>
                      ))}
                    </div>
                  </div>
                  <div className="absolute bottom-0 left-0 right-0 h-20 bg-gradient-to-t from-card via-card/80 to-transparent pointer-events-none" />
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

            {/* Programs Mode */}
            {viewMode === 'programs' && (
              <>
                {/* Programs Table - Columnar Layout */}
                <div className="relative h-[420px] overflow-hidden">
                  <div className="rounded-xl border border-border bg-card/50 overflow-hidden">
                    {/* Table Header */}
                    <div className="grid grid-cols-[auto_1fr_100px_100px] gap-4 px-4 py-3 border-b border-border bg-muted/30 font-mono text-xs text-muted-foreground uppercase tracking-wider">
                      <div className="w-8"></div>
                      <div>Program</div>
                      <div className="text-right">Subs</div>
                      <div className="text-right">Servers</div>
                    </div>
                    
                    {/* Loading State */}
                    {isDataLoading && (
                      <div className="divide-y divide-border">
                        {[1, 2, 3, 4].map((i) => (
                          <div key={i} className="grid grid-cols-[auto_1fr_100px_100px] gap-4 px-4 py-3 animate-pulse">
                            <div className="h-8 w-8 bg-muted rounded-full" />
                            <div className="h-4 w-32 bg-muted rounded self-center" />
                            <div className="h-4 w-12 bg-muted rounded self-center ml-auto" />
                            <div className="h-4 w-12 bg-muted rounded self-center ml-auto" />
                          </div>
                        ))}
                      </div>
                    )}
                    
                    {/* Loaded State - Programs with stats */}
                    {!isDataLoading && showcaseData && (
                      <div className="divide-y divide-border">
                        {showcaseData.programs.map((program) => (
                          <div 
                            key={program.id} 
                            className="grid grid-cols-[auto_1fr_100px_100px] gap-4 px-4 py-3 transition-colors hover:bg-muted/20"
                          >
                            {/* Initial Badge */}
                            <div className="h-8 w-8 rounded-full bg-muted flex items-center justify-center text-sm font-bold font-mono text-foreground">
                              {program.name.charAt(0).toUpperCase()}
                            </div>
                            {/* Program Name */}
                            <span className="font-mono text-sm text-foreground self-center">{program.name}</span>
                            {/* Subdomain Count */}
                            <span className="font-mono text-sm text-muted-foreground text-right self-center">
                              {formatNumber(program.subdomain_count)}
                            </span>
                            {/* Server Count */}
                            <span className="font-mono text-sm text-muted-foreground text-right self-center">
                              {formatNumber(program.server_count)}
                            </span>
                          </div>
                        ))}
                        
                        {/* More programs teaser row */}
                        <div className="grid grid-cols-[auto_1fr_100px_100px] gap-4 px-4 py-3 opacity-50">
                          <div className="h-8 w-8 rounded-full bg-muted/30 flex items-center justify-center text-sm font-mono text-muted-foreground">
                            +
                          </div>
                          <span className="font-mono text-sm text-muted-foreground self-center">more programs...</span>
                          <span></span>
                          <span></span>
                        </div>
                      </div>
                    )}
                  </div>
                </div>

                {/* Programs Mode: CTA */}
                <div className="text-center pt-4">
                  <Button 
                    variant="link" 
                    className="text-[--terminal-green] hover:text-[--terminal-green]/80 font-bold font-mono"
                    onClick={() => signInWithGoogle()}
                  >
                    Sign up to explore all programs →
                  </Button>
                </div>
              </>
            )}
          </div>
        </div>
      </main>

      {/* Footer */}
      <footer className="py-8 text-center font-mono">
        <p className="text-xs text-muted-foreground">
          neobotnet 2025
        </p>
      </footer>
    </div>
  );
}
