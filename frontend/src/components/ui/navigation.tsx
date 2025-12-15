'use client';

/**
 * Navigation Component for NeoBot-Net LEAN
 * 
 * Simplified navigation with:
 * - Dashboard (API keys, user info)
 * - Data browsers (subdomains, DNS, probes)
 * - Google SSO authentication
 */

import { useAuth } from '@/contexts/AuthContext';
import { Button } from '@/components/ui/button';
import { LogOut, User, BarChart3, Globe, Database, Wifi } from 'lucide-react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';

export const Navigation: React.FC = () => {
  const { user, isAuthenticated, signOut, isLoading } = useAuth();
  const pathname = usePathname();

  if (isLoading) {
    return (
      <nav className="border-b bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
        <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
          <div className="flex h-14 items-center justify-between">
            <div className="flex items-center">
              <Link href="/" className="flex items-center space-x-2">
                <span className="font-bold text-lg">NeoBot-Net</span>
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

  // LEAN navigation - data browsing only, no scan management
  const navItems = [
    {
      href: '/dashboard',
      label: 'Dashboard',
      icon: BarChart3,
      active: pathname === '/dashboard'
    },
    {
      href: '/subdomains',
      label: 'Subdomains',
      icon: Globe,
      active: pathname.startsWith('/subdomains')
    },
    {
      href: '/dns',
      label: 'DNS Records',
      icon: Database,
      active: pathname.startsWith('/dns')
    },
    {
      href: '/probes',
      label: 'HTTP Probes',
      icon: Wifi,
      active: pathname.startsWith('/probes')
    }
  ];

  return (
    <nav className="border-b bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
        <div className="flex h-14 items-center justify-between">
          <div className="flex items-center space-x-8">
            <Link href="/" className="flex items-center space-x-2">
              <span className="font-bold text-lg">NeoBot-Net</span>
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
