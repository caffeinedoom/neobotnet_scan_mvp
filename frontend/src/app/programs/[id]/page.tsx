'use client';

/**
 * Program Detail Page - neobotnet
 * 
 * Displays detailed reconnaissance data for a specific program.
 * Clean, minimal design with navigation to subdomains, DNS, and servers.
 */

import { useEffect, useState } from 'react';
import { useRouter, useParams } from 'next/navigation';
import { useAuth } from '@/contexts/AuthContext';
import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { 
  ArrowLeft,
  Globe, 
  ExternalLink,
  Network,
  Server,
  CircleDot,
  ChevronRight,
  Link2
} from 'lucide-react';
import Link from 'next/link';
import { reconDataService, type ReconAsset } from '@/lib/api/recon-data';
import { apiClient } from '@/lib/api/client';
import { toast } from 'sonner';

// Apex Domain type
interface ApexDomain {
  id: string;
  domain: string;
  total_subdomains: number;
  last_scanned_at?: string;
}

// Letter Avatar component (matching /programs page)
function LetterAvatar({ name, className = '' }: { name: string; className?: string }) {
  const letter = name.charAt(0).toUpperCase();
  
  const colors = [
    'bg-red-500/20 text-red-400',
    'bg-orange-500/20 text-orange-400',
    'bg-amber-500/20 text-amber-400',
    'bg-yellow-500/20 text-yellow-400',
    'bg-lime-500/20 text-lime-400',
    'bg-green-500/20 text-green-400',
    'bg-emerald-500/20 text-emerald-400',
    'bg-teal-500/20 text-teal-400',
    'bg-cyan-500/20 text-cyan-400',
    'bg-sky-500/20 text-sky-400',
    'bg-blue-500/20 text-blue-400',
    'bg-indigo-500/20 text-indigo-400',
    'bg-violet-500/20 text-violet-400',
    'bg-purple-500/20 text-purple-400',
    'bg-fuchsia-500/20 text-fuchsia-400',
    'bg-pink-500/20 text-pink-400',
  ];
  
  const colorIndex = name.split('').reduce((acc, char) => acc + char.charCodeAt(0), 0) % colors.length;
  const colorClass = colors[colorIndex];
  
  return (
    <div className={`flex items-center justify-center rounded-lg font-bold font-mono ${colorClass} ${className}`}>
      {letter}
    </div>
  );
}

export default function ProgramDetailPage() {
  const router = useRouter();
  const params = useParams();
  const { isAuthenticated, isLoading } = useAuth();
  
  const [program, setProgram] = useState<ReconAsset | null>(null);
  const [apexDomains, setApexDomains] = useState<ApexDomain[]>([]);
  const [loading, setLoading] = useState(true);

  const programId = params.id as string;

  // Auth redirect
  useEffect(() => {
    if (!isAuthenticated && !isLoading) {
      if (typeof window !== 'undefined' && !window.location.pathname.startsWith('/auth/')) {
        router.push('/auth/login');
      }
    }
  }, [isAuthenticated, isLoading, router]);

  // Load program details and apex domains
  const loadProgram = async () => {
    try {
      setLoading(true);
      
      // Fetch program data and apex domains in parallel
      const [programData, domainsResponse] = await Promise.all([
        reconDataService.getAssetDetailData(programId),
        apiClient.get<ApexDomain[]>(`/api/v1/assets/${programId}/domains`).catch(() => ({ data: [] }))
      ]);
      
      if (!programData) {
        toast.error('Program not found');
        router.push('/programs');
        return;
      }
      
      setProgram(programData);
      setApexDomains(domainsResponse.data || []);
    } catch (error) {
      console.error('Failed to load program:', error);
      toast.error('Failed to load program');
      router.push('/programs');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (isAuthenticated && programId) {
      loadProgram();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isAuthenticated, programId]);

  if (!isAuthenticated && !isLoading) {
    return null;
  }

  if (loading) {
    return (
      <div className="mx-auto max-w-5xl px-4 sm:px-6 lg:px-8 py-8">
        <div className="space-y-6">
          <div className="h-6 bg-muted animate-pulse rounded w-24" />
          <div className="flex items-center gap-4">
            <div className="w-14 h-14 bg-muted animate-pulse rounded-lg" />
            <div className="space-y-2 flex-1">
              <div className="h-8 bg-muted animate-pulse rounded w-1/3" />
          <div className="h-4 bg-muted animate-pulse rounded w-1/2" />
            </div>
          </div>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            {[...Array(4)].map((_, i) => (
              <div key={i} className="h-32 bg-muted animate-pulse rounded-lg" />
            ))}
          </div>
        </div>
      </div>
    );
  }

  if (!program) {
    return null;
  }

  // Stat cards data (domains card has no link - shown in section below)
  const statCards = [
    {
      href: null, // No link - apex domains shown in section below
      icon: CircleDot,
      label: 'domains',
      count: program.apex_domain_count || 0,
      subtitle: 'apex',
    },
    {
      href: `/subdomains?asset_id=${program.id}`,
      icon: Globe,
      label: 'subdomains',
      count: program.total_subdomains || 0,
      subtitle: 'discovered',
    },
    {
      href: `/dns?asset_id=${program.id}`,
      icon: Network,
      label: 'dns',
      count: program.total_dns_records || 0,
      subtitle: 'records',
    },
    {
      href: `/probes?asset_id=${program.id}`,
      icon: Server,
      label: 'servers',
      count: program.total_probes || 0,
      subtitle: 'live hosts',
    },
    {
      href: `/urls?asset_id=${program.id}`,
      icon: Link2,
      label: 'urls',
      count: program.total_urls || 0,
      subtitle: 'discovered',
    },
  ];

  return (
    <div className="mx-auto max-w-5xl px-4 sm:px-6 lg:px-8 py-8">
      <div className="space-y-8">
        {/* Back Button */}
        <Link 
          href="/programs"
          className="inline-flex items-center text-sm text-muted-foreground hover:text-foreground transition-colors font-mono"
        >
          <ArrowLeft className="h-4 w-4 mr-2" />
          programs
        </Link>

        {/* Header */}
        <div className="flex items-start gap-4">
          <LetterAvatar name={program.name} className="w-14 h-14 text-2xl flex-shrink-0" />
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-3">
              <h1 className="text-2xl font-bold tracking-tight font-mono text-foreground truncate">
              {program.name}
              </h1>
              {program.bug_bounty_url && (
                <a 
                  href={program.bug_bounty_url} 
                  target="_blank" 
                  rel="noopener noreferrer"
                  className="text-muted-foreground hover:text-[--terminal-green] transition-colors flex-shrink-0"
                >
                  <ExternalLink className="h-5 w-5" />
                </a>
              )}
            </div>
            
            {program.description && (
              <p className="text-sm text-muted-foreground mt-1 font-mono">
                {program.description}
              </p>
            )}
            
            {/* Tags + Last Scan inline */}
            <div className="flex flex-wrap items-center gap-2 mt-3">
            {program.tags && program.tags.length > 0 && (
                <>
                {program.tags.map((tag) => (
                    <Badge key={tag} variant="secondary" className="font-mono text-xs">
                    {tag}
                  </Badge>
                ))}
                  <span className="text-muted-foreground">·</span>
                </>
              )}
              <span className="text-xs text-muted-foreground font-mono">
                {program.last_scan_date 
                  ? `scanned ${new Date(program.last_scan_date).toLocaleDateString()}`
                  : 'no scans yet'
                }
              </span>
              </div>
          </div>
        </div>

        {/* Stat Cards Grid */}
        <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
          {statCards.map((card) => {
            const cardContent = (
              <Card className={`relative border border-border bg-card h-full group overflow-hidden ${
                card.href 
                  ? 'hover:border-[--terminal-green]/50 hover:bg-white/[0.02] transition-all duration-200 cursor-pointer' 
                  : ''
              }`}>
                {/* Hover overlay for clickable cards */}
                {card.href && (
                  <div className="absolute inset-0 bg-gradient-to-br from-white/[0.03] to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-200 pointer-events-none" />
                )}
                <CardContent className="p-4 relative z-10">
                  <div className="flex items-center justify-between mb-3">
                    <card.icon className={`h-4 w-4 text-muted-foreground ${card.href ? 'group-hover:text-[--terminal-green]' : ''} transition-colors`} />
                    {card.href && (
                      <ChevronRight className="h-4 w-4 text-muted-foreground opacity-0 group-hover:opacity-100 transition-opacity" />
                    )}
                  </div>
                  <div className="text-2xl font-bold font-mono text-foreground mb-1">
                    {card.count !== null ? card.count.toLocaleString() : '—'}
                  </div>
                  <div className="text-xs text-muted-foreground uppercase tracking-wider font-mono">
                    {card.label}
                  </div>
                  <div className="text-[10px] text-muted-foreground/70 font-mono mt-1">
                    {card.subtitle}
                  </div>
                </CardContent>
              </Card>
            );
            
            return card.href ? (
              <Link key={card.label} href={card.href}>
                {cardContent}
              </Link>
            ) : (
              <div key={card.label}>
                {cardContent}
              </div>
            );
          })}
        </div>

        {/* Apex Domains Section */}
        {apexDomains.length > 0 && (
          <div className="space-y-4">
            <h2 className="text-sm font-medium text-muted-foreground uppercase tracking-wider font-mono">
              Apex Domains
            </h2>
            <div className="space-y-2">
              {apexDomains.map((domain) => (
                <div 
                  key={domain.id}
                  className="flex items-center justify-between py-3 px-4 rounded-lg border border-border/50 bg-card/30 hover:bg-card/50 transition-colors"
                >
                  <code className="font-mono text-foreground">{domain.domain}</code>
                  <span className="text-sm text-muted-foreground font-mono">
                    {domain.total_subdomains.toLocaleString()} subdomains
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
