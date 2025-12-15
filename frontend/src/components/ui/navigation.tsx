'use client';

import { useAuth } from '@/contexts/AuthContext';
import { Button } from '@/components/ui/button';
import { LogOut, User, Building2, Search, BarChart3, Radar } from 'lucide-react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';

export const Navigation: React.FC = () => {
  const { user, isAuthenticated, logout, isLoading } = useAuth();
  const pathname = usePathname();

  if (isLoading) {
    return (
      <nav className="border-b bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
        <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
          <div className="flex h-14 items-center justify-between">
            <div className="flex items-center">
              <Link href="/" className="flex items-center space-x-2">
                <span className="font-bold text-lg">Neobotnet</span>
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
    await logout();
  };

  const navItems = [
    {
      href: '/dashboard',
      label: 'Dashboard',
      icon: BarChart3,
      active: pathname === '/dashboard'
    },
    {
      href: '/assets',
      label: 'Assets',
      icon: Building2,
      active: pathname.startsWith('/assets')
    },
    {
      href: '/scans',
      label: 'Scans',
      icon: Radar,
      active: pathname.startsWith('/scans')
    },
    {
      href: '/recon',
      label: 'Recon',
      icon: Search,
      active: pathname.startsWith('/recon') || pathname.startsWith('/subdomains')
    }
  ];

  return (
    <nav className="border-b bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
        <div className="flex h-14 items-center justify-between">
          <div className="flex items-center space-x-8">
            <Link href="/" className="flex items-center space-x-2">
              <span className="font-bold text-lg">Neobotnet</span>
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
              <div className="md:hidden">
                <Button variant="ghost" size="sm" asChild>
                  <Link href="/dashboard">
                    <BarChart3 className="h-4 w-4" />
                  </Link>
                </Button>
                <Button variant="ghost" size="sm" asChild>
                  <Link href="/assets">
                    <Building2 className="h-4 w-4" />
                  </Link>
                </Button>
                <Button variant="ghost" size="sm" asChild>
                  <Link href="/scans">
                    <Radar className="h-4 w-4" />
                  </Link>
                </Button>
                <Button variant="ghost" size="sm" asChild>
                  <Link href="/recon">
                    <Search className="h-4 w-4" />
                  </Link>
                </Button>
              </div>

              <div className="hidden sm:flex items-center space-x-2 text-sm">
                <User className="h-4 w-4" />
                <span className="truncate max-w-[150px]">
                  {user?.full_name || user?.email}
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
            // Unauthenticated state
            <div className="flex items-center space-x-2">
              <Button variant="ghost" size="sm" asChild>
                <Link href="/auth/login">Sign in</Link>
              </Button>
              <Button size="sm" asChild>
                <Link href="/auth/register">Sign up</Link>
              </Button>
            </div>
          )}
          </div>
        </div>
      </div>
    </nav>
  );
}; 