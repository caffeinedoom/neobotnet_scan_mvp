'use client';

/**
 * Programs Page - neobotnet
 * 
 * Displays all bug bounty programs with reconnaissance data.
 * Read-only view - programs are managed via CLI by the operator.
 */

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/contexts/AuthContext';
import { Card, CardContent } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { 
  Building2, 
  Search, 
  Globe,
  Wifi,
  Calendar
} from 'lucide-react';
import Link from 'next/link';
import { reconDataService, type ReconAsset } from '@/lib/api/recon-data';
import { toast } from 'sonner';

// Letter Avatar component
function LetterAvatar({ name, className = '' }: { name: string; className?: string }) {
  const letter = name.charAt(0).toUpperCase();
  
  // Generate consistent color based on name
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

export default function ProgramsPage() {
  const router = useRouter();
  const { isAuthenticated, isLoading } = useAuth();
  
  const [programs, setPrograms] = useState<ReconAsset[]>([]);
  const [filteredPrograms, setFilteredPrograms] = useState<ReconAsset[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState('');

  // Auth redirect
  useEffect(() => {
    if (!isAuthenticated && !isLoading) {
      if (typeof window !== 'undefined' && !window.location.pathname.startsWith('/auth/')) {
        router.push('/auth/login');
      }
    }
  }, [isAuthenticated, isLoading, router]);

  // Load programs
  const loadPrograms = async () => {
    try {
      setLoading(true);
      const { assets } = await reconDataService.getAssetsData();
      setPrograms(assets);
      setFilteredPrograms(assets);
    } catch (error) {
      console.error('Failed to load programs:', error);
      toast.error('Failed to load programs');
      setPrograms([]);
      setFilteredPrograms([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (isAuthenticated) {
      loadPrograms();
    }
  }, [isAuthenticated]);

  // Filter programs by search term
  useEffect(() => {
    if (!searchTerm.trim()) {
      setFilteredPrograms(programs);
    } else {
      const term = searchTerm.toLowerCase();
      setFilteredPrograms(
        programs.filter(p => 
          p.name.toLowerCase().includes(term) ||
          p.description?.toLowerCase().includes(term) ||
          p.tags?.some(t => t.toLowerCase().includes(term))
        )
      );
    }
  }, [searchTerm, programs]);

  if (!isAuthenticated && !isLoading) {
    return null;
  }

  return (
    <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8 py-8">
      <div className="space-y-8">
        {/* Header */}
        <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
          <h1 className="text-2xl font-bold tracking-tight font-mono text-foreground">
            programs
          </h1>
          
          {/* Search */}
          <div className="relative w-full sm:w-80">
            <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-muted-foreground" />
            <Input
              placeholder="search programs..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="pl-10 font-mono bg-card border-border"
            />
          </div>
        </div>

        {/* Programs Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {loading ? (
            // Skeleton loaders
            [...Array(6)].map((_, i) => (
              <Card key={`skeleton-${i}`} className="border border-border bg-card">
                <CardContent className="p-5">
                  <div className="flex items-center gap-3 mb-4">
                    <div className="w-10 h-10 bg-muted animate-pulse rounded-lg" />
                    <div className="h-5 bg-muted animate-pulse rounded w-2/3" />
                  </div>
                  <div className="h-4 bg-muted animate-pulse rounded w-full mb-4" />
                  <div className="grid grid-cols-3 gap-3">
                    <div className="h-12 bg-muted animate-pulse rounded" />
                    <div className="h-12 bg-muted animate-pulse rounded" />
                    <div className="h-12 bg-muted animate-pulse rounded" />
                  </div>
                </CardContent>
              </Card>
            ))
          ) : filteredPrograms.length === 0 ? (
            <Card className="col-span-full border border-border bg-card">
              <CardContent className="flex flex-col items-center justify-center py-16">
                <Building2 className="h-10 w-10 text-muted-foreground mb-4" />
                <h3 className="text-base font-mono font-medium mb-2 text-foreground">
                  {searchTerm ? 'no programs found' : 'no programs yet'}
                </h3>
                <p className="text-sm text-muted-foreground text-center font-mono">
                  {searchTerm 
                    ? 'try adjusting your search term' 
                    : 'programs are added by the operator'
                  }
                </p>
              </CardContent>
            </Card>
          ) : (
            filteredPrograms.map((program) => (
              <Link key={program.id} href={`/programs/${program.id}`}>
                <Card className="border border-border bg-card hover:border-[--terminal-green]/50 transition-all duration-200 cursor-pointer h-full group">
                  <CardContent className="p-5">
                    {/* Program Header: Avatar + Name */}
                    <div className="flex items-center gap-3 mb-3">
                      <LetterAvatar name={program.name} className="w-10 h-10 text-lg" />
                      <h3 className="text-base font-semibold font-mono truncate flex-1 text-foreground group-hover:text-[--terminal-green] transition-colors" title={program.name}>
                        {program.name}
                      </h3>
                    </div>

                    {/* Description */}
                    {program.description && (
                      <p className="text-sm text-muted-foreground mb-4 line-clamp-2 font-mono">
                        {program.description}
                      </p>
                    )}

                    {/* Stats Row */}
                    <div className="grid grid-cols-3 gap-3 mb-4">
                      <div className="text-center">
                        <div className="flex items-center justify-center gap-1 mb-1">
                          <Globe className="h-3 w-3 text-muted-foreground" />
                        </div>
                        <div className="text-lg font-bold font-mono text-foreground">{program.apex_domain_count || 0}</div>
                        <div className="text-[10px] text-muted-foreground uppercase tracking-wider">domains</div>
                      </div>
                      <div className="text-center">
                        <div className="flex items-center justify-center gap-1 mb-1">
                          <Search className="h-3 w-3 text-muted-foreground" />
                        </div>
                        <div className="text-lg font-bold font-mono text-foreground">{(program.total_subdomains || 0).toLocaleString()}</div>
                        <div className="text-[10px] text-muted-foreground uppercase tracking-wider">subdomains</div>
                      </div>
                      <div className="text-center">
                        <div className="flex items-center justify-center gap-1 mb-1">
                          <Wifi className="h-3 w-3 text-muted-foreground" />
                        </div>
                        <div className="text-lg font-bold font-mono text-muted-foreground">—</div>
                        <div className="text-[10px] text-muted-foreground uppercase tracking-wider">servers</div>
                      </div>
                    </div>

                    {/* Last Scan Date */}
                    <div className="flex items-center text-xs text-muted-foreground font-mono pt-3 border-t border-border">
                      <Calendar className="h-3 w-3 mr-2" />
                      {program.last_scan_date ? (
                        <span>scanned {new Date(program.last_scan_date).toLocaleDateString()}</span>
                      ) : (
                        <span>no scans yet</span>
                      )}
                    </div>
                  </CardContent>
                </Card>
              </Link>
            ))
          )}
        </div>
      </div>
    </div>
  );
}

