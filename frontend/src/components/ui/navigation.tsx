'use client';

/**
 * Navigation Component for neobotnet
 * 
 * Simplified navigation with:
 * - Data browsers (Programs, Subdomains, DNS, Servers)
 * - API documentation
 * - Google/X SSO authentication
 * 
 * Hidden on landing page for unauthenticated users for clean UX.
 */

import { useState, useEffect } from 'react';
import { useAuth } from '@/contexts/AuthContext';
import { Button } from '@/components/ui/button';
import { LogOut, User, Globe, Database, Server, Building2, Code2, Link2 } from 'lucide-react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';

export const Navigation: React.FC = () => {
  const { user, isAuthenticated, signOut, isLoading } = useAuth();
  const pathname = usePathname();
  const [showCursor, setShowCursor] = useState(true);

  // Blinking cursor effect
  useEffect(() => {
    const interval = setInterval(() => {
      setShowCursor(s => !s);
    }, 530);
    return () => clearInterval(interval);
  }, []);

  // Hide navigation on landing page for unauthenticated users
  // The landing page has its own minimal UI
  if (!isAuthenticated && !isLoading && pathname === '/') {
    return null;
  }

  if (isLoading) {
    return (
      <nav className="border-b border-border/50 bg-background/80 backdrop-blur-xl supports-[backdrop-filter]:bg-background/60">
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
    await signOut();
  };

  // LEAN navigation - programs and data browsing
  const navItems = [
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
      icon: Database,
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

  return (
    <nav className="border-b border-border/50 bg-background/80 backdrop-blur-xl supports-[backdrop-filter]:bg-background/60">
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
            // Authenticated state
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

              <div className="hidden sm:flex items-center space-x-2 text-sm">
                <User className="h-4 w-4" />
                <span className="truncate max-w-[150px]">
                  {user?.user_metadata?.full_name || user?.email}
                </span>
              </div>
              <Button 
                variant="outline" 
                size="sm" 
                onClick={handleLogout}
                className="flex items-center space-x-2"
              >
                <LogOut className="h-4 w-4" />
                <span className="hidden sm:inline">Logout</span>
              </Button>
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
