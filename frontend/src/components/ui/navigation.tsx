'use client';

/**
 * Navigation Component for neobotnet
 * 
 * Simplified navigation with:
 * - Data browsers (Programs, Subdomains, DNS, Servers)
 * - API documentation
 * - Google/X SSO authentication
 * - User dropdown with tier badge
 * 
 * Hidden on landing page for unauthenticated users for clean UX.
 */

import { useState, useEffect, useRef } from 'react';
import { useAuth } from '@/contexts/AuthContext';
import { Button } from '@/components/ui/button';
import { LogOut, User, Globe, Network, Server, Building2, Code2, Link2, Zap, ChevronDown, Crown, LayoutDashboard } from 'lucide-react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { getBillingStatus, BillingStatus } from '@/lib/api/billing';

export const Navigation: React.FC = () => {
  const { user, isAuthenticated, signOut, isLoading } = useAuth();
  const pathname = usePathname();
  const [showCursor, setShowCursor] = useState(true);
  const [billingStatus, setBillingStatus] = useState<BillingStatus | null>(null);
  const [dropdownOpen, setDropdownOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  // Blinking cursor effect
  useEffect(() => {
    const interval = setInterval(() => {
      setShowCursor(s => !s);
    }, 530);
    return () => clearInterval(interval);
  }, []);

  // Fetch billing status for authenticated users
  useEffect(() => {
    async function loadBillingStatus() {
      if (!isAuthenticated || !user) return;
      try {
        const status = await getBillingStatus();
        setBillingStatus(status);
      } catch (error) {
        console.error('Failed to load billing status:', error);
      }
    }
    loadBillingStatus();
  }, [isAuthenticated, user]);

  // Close dropdown when clicking outside
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setDropdownOpen(false);
      }
    }
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  // Hide navigation on landing page for unauthenticated users
  // The landing page has its own minimal UI
  if (!isAuthenticated && !isLoading && pathname === '/') {
    return null;
  }

  if (isLoading) {
    return (
      <nav className="sticky top-0 z-50 border-b border-border/50 bg-background/80 backdrop-blur-xl supports-[backdrop-filter]:bg-background/60">
        <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
          <div className="flex h-14 items-center justify-between">
            <div className="flex items-center">
              <Link href="/" className="flex items-center space-x-2">
                <span className="font-bold text-lg font-mono tracking-tight">neobotnet</span>
              </Link>
            </div>
            <div className="flex items-center space-x-4">
              <div className="h-8 w-20 bg-muted animate-pulse rounded" />
            </div>
          </div>
        </div>
      </nav>
    );
  }

  const handleLogout = async () => {
    setDropdownOpen(false);
    await signOut();
  };

  // LEAN navigation - programs and data browsing
  const navItems = [
    {
      href: '/dashboard',
      label: 'Dashboard',
      icon: LayoutDashboard,
      active: pathname === '/dashboard'
    },
    {
      href: '/programs',
      label: 'Programs',
      icon: Building2,
      active: pathname.startsWith('/programs')
    },
    {
      href: '/subdomains',
      label: 'Subdomains',
      icon: Globe,
      active: pathname.startsWith('/subdomains')
    },
    {
      href: '/dns',
      label: 'DNS',
      icon: Network,
      active: pathname.startsWith('/dns')
    },
    {
      href: '/probes',
      label: 'Servers',
      icon: Server,
      active: pathname.startsWith('/probes')
    },
    {
      href: '/urls',
      label: 'URLs',
      icon: Link2,
      active: pathname.startsWith('/urls')
    },
    {
      href: '/api-docs',
      label: 'API',
      icon: Code2,
      active: pathname.startsWith('/api-docs')
    }
  ];

  const isPaid = billingStatus?.is_paid;
  const userName = user?.user_metadata?.full_name || user?.email?.split('@')[0] || 'User';

  return (
    <nav className="sticky top-0 z-50 border-b border-border/50 bg-background/80 backdrop-blur-xl supports-[backdrop-filter]:bg-background/60">
      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
        <div className="flex h-14 items-center justify-between">
          <div className="flex items-center space-x-8">
            <Link href="/" className="flex items-center">
              <span className="font-bold text-lg font-mono tracking-tight text-foreground">neobotnet</span>
              <span className={`font-bold text-lg font-mono text-[--terminal-green] ${showCursor ? 'opacity-100' : 'opacity-0'} transition-opacity`}>_</span>
            </Link>
            
            {/* Navigation Links - Only show when authenticated */}
            {isAuthenticated && (
              <div className="hidden md:flex items-center space-x-1">
                {navItems.map((item) => (
                  <Button
                    key={item.href}
                    variant={item.active ? "secondary" : "ghost"}
                    size="sm"
                    asChild
                    className="flex items-center space-x-2"
                  >
                    <Link href={item.href}>
                      <item.icon className="h-4 w-4" />
                      <span>{item.label}</span>
                    </Link>
                  </Button>
                ))}
              </div>
            )}
          </div>

          <div className="flex items-center space-x-4">
          {isAuthenticated ? (
            // Authenticated state - User dropdown
            <>
              {/* Mobile Navigation Menu */}
              <div className="md:hidden flex items-center">
                {navItems.map((item) => (
                  <Button key={item.href} variant="ghost" size="sm" asChild>
                    <Link href={item.href}>
                      <item.icon className="h-4 w-4" />
                  </Link>
                </Button>
                ))}
              </div>

              {/* User Dropdown */}
              <div className="relative z-50" ref={dropdownRef}>
                <button
                  onClick={() => setDropdownOpen(!dropdownOpen)}
                  className="flex items-center gap-2 px-3 py-1.5 rounded-lg border-2 border-white/30 hover:border-white hover:bg-white/5 transition-all"
                >
                  <User className="h-4 w-4 text-muted-foreground" />
                  <span className="text-sm font-medium hidden sm:inline">{userName}</span>
                  
                  {/* Tier Badge */}
                  {isPaid ? (
                    <span className="px-2 py-0.5 text-xs font-bold rounded border border-white text-white">
                      PRO
                    </span>
                  ) : (
                    <span className="px-2 py-0.5 text-xs font-bold bg-muted text-muted-foreground rounded">
                      FREE
                    </span>
                  )}
                  
                  <ChevronDown className={`h-4 w-4 text-muted-foreground transition-transform ${dropdownOpen ? 'rotate-180' : ''}`} />
                </button>

                {/* Dropdown Menu */}
                {dropdownOpen && (
                  <div className="absolute right-0 mt-2 w-56 bg-card border border-border rounded-lg shadow-2xl py-1 z-[9999]">
                    {/* User Info */}
                    <div className="px-4 py-3 border-b border-border">
                      <p className="text-sm font-medium">{userName}</p>
                      <p className="text-xs text-muted-foreground truncate">{user?.email}</p>
                    </div>

                    {/* Tier Status */}
                    <div className="px-4 py-3 border-b border-border">
                      {isPaid ? (
                        <div className="flex items-center gap-2">
                          <Crown className="h-4 w-4 text-white" />
                          <span className="text-sm font-medium text-white">Pro Member</span>
                        </div>
                      ) : (
                        <Link
                          href="/upgrade"
                          onClick={() => setDropdownOpen(false)}
                          className="flex items-center justify-center gap-2 w-full px-3 py-2 text-sm font-bold border-2 border-white bg-transparent text-white hover:bg-white hover:text-black rounded transition-all"
                        >
                          <Zap className="h-4 w-4" />
                          Upgrade to Pro
                        </Link>
                      )}
                    </div>

                    {/* Actions */}
                    <div className="py-1">
                      <button
                onClick={handleLogout}
                        className="flex items-center gap-2 w-full px-4 py-2 text-sm text-muted-foreground hover:text-foreground hover:bg-muted/50 transition-colors"
              >
                <LogOut className="h-4 w-4" />
                        Sign out
                      </button>
                    </div>
                  </div>
                )}
              </div>
            </>
          ) : (
            // Unauthenticated state - Google SSO only
              <Button size="sm" asChild>
              <Link href="/auth/login">Sign in with Google</Link>
              </Button>
          )}
          </div>
        </div>
      </div>
    </nav>
  );
}; 
