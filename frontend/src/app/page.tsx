'use client';

/**
 * Landing Page - NeoBot-Net LEAN
 * 
 * Simple landing page showcasing free recon data access.
 */

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { useAuth } from '@/contexts/AuthContext';
import { 
  Globe, 
  Database, 
  Wifi, 
  Code2, 
  Key, 
  Zap,
  Search,
  ArrowRight
} from 'lucide-react';

export default function Home() {
  const router = useRouter();
  const { isAuthenticated, isLoading } = useAuth();

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
    return null; // Will redirect to programs
  }

  return (
    <div className="min-h-screen">
      {/* Hero Section */}
      <section className="relative overflow-hidden">
        {/* Background gradient */}
        <div className="absolute inset-0 bg-gradient-to-br from-primary/5 via-background to-background" />
        
        <div className="relative mx-auto max-w-7xl px-4 sm:px-6 lg:px-8 py-24 sm:py-32">
      <div className="text-center space-y-8">
            {/* Badge */}
            <Badge variant="secondary" className="px-4 py-2 text-sm">
              🚀 Free for Bug Bounty Researchers
            </Badge>

            {/* Title */}
            <h1 className="text-5xl sm:text-6xl lg:text-7xl font-bold tracking-tight">
              <span className="bg-gradient-to-r from-primary to-primary/60 bg-clip-text text-transparent">
                NeoBot-Net
              </span>
        </h1>
        
            {/* Subtitle */}
            <p className="max-w-2xl mx-auto text-xl text-muted-foreground">
              Free reconnaissance data for bug bounty programs. 
              Access subdomains, DNS records, and HTTP probes via a simple API or UI.
            </p>

            {/* CTA Buttons */}
        <div className="flex flex-col sm:flex-row gap-4 justify-center">
              <Button size="lg" asChild className="text-lg px-8">
                <Link href="/auth/login">
                  Get Started Free
                  <ArrowRight className="ml-2 h-5 w-5" />
            </Link>
          </Button>
              <Button variant="outline" size="lg" asChild className="text-lg px-8">
                <Link href="/api-docs">
                  <Code2 className="mr-2 h-5 w-5" />
                  View API Docs
            </Link>
          </Button>
        </div>
      </div>
        </div>
      </section>

      {/* Features Grid */}
      <section className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8 py-16">
        <div className="text-center mb-12">
          <h2 className="text-3xl font-bold">What You Get</h2>
          <p className="text-muted-foreground mt-2">
            Everything you need for bug bounty reconnaissance
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {/* Subdomains */}
          <Card className="border-2 hover:border-primary/30 transition-colors">
            <CardHeader>
              <Globe className="h-10 w-10 text-blue-500 mb-2" />
              <CardTitle>Subdomains</CardTitle>
              <CardDescription>
                Comprehensive subdomain enumeration using Subfinder
              </CardDescription>
            </CardHeader>
            <CardContent>
              <ul className="text-sm text-muted-foreground space-y-1">
                <li>• Multiple data sources</li>
                <li>• Daily updates</li>
                <li>• Export to file</li>
              </ul>
            </CardContent>
          </Card>

          {/* DNS Records */}
          <Card className="border-2 hover:border-primary/30 transition-colors">
            <CardHeader>
              <Database className="h-10 w-10 text-green-500 mb-2" />
              <CardTitle>DNS Records</CardTitle>
              <CardDescription>
                A, AAAA, CNAME, and more from DNSx scans
              </CardDescription>
            </CardHeader>
            <CardContent>
              <ul className="text-sm text-muted-foreground space-y-1">
                <li>• All record types</li>
                <li>• IP resolution</li>
                <li>• CNAME chains</li>
              </ul>
            </CardContent>
          </Card>

          {/* HTTP Probes */}
          <Card className="border-2 hover:border-primary/30 transition-colors">
            <CardHeader>
              <Wifi className="h-10 w-10 text-orange-500 mb-2" />
              <CardTitle>HTTP Probes</CardTitle>
              <CardDescription>
                Live host detection and technology fingerprinting
              </CardDescription>
            </CardHeader>
            <CardContent>
              <ul className="text-sm text-muted-foreground space-y-1">
                <li>• Status codes</li>
                <li>• Title extraction</li>
                <li>• Tech detection</li>
              </ul>
            </CardContent>
          </Card>

          {/* API Access */}
          <Card className="border-2 hover:border-primary/30 transition-colors">
            <CardHeader>
              <Code2 className="h-10 w-10 text-purple-500 mb-2" />
              <CardTitle>REST API</CardTitle>
              <CardDescription>
                Programmatic access to all reconnaissance data
              </CardDescription>
            </CardHeader>
            <CardContent>
              <ul className="text-sm text-muted-foreground space-y-1">
                <li>• JSON responses</li>
                <li>• Pagination</li>
                <li>• Filter & search</li>
              </ul>
            </CardContent>
          </Card>

          {/* API Keys */}
          <Card className="border-2 hover:border-primary/30 transition-colors">
            <CardHeader>
              <Key className="h-10 w-10 text-yellow-500 mb-2" />
              <CardTitle>API Keys</CardTitle>
              <CardDescription>
                Generate personal API keys for programmatic access
              </CardDescription>
            </CardHeader>
            <CardContent>
              <ul className="text-sm text-muted-foreground space-y-1">
                <li>• Instant generation</li>
                <li>• Multiple keys</li>
                <li>• Easy revocation</li>
              </ul>
            </CardContent>
          </Card>

          {/* Fast Updates */}
          <Card className="border-2 hover:border-primary/30 transition-colors">
            <CardHeader>
              <Zap className="h-10 w-10 text-cyan-500 mb-2" />
              <CardTitle>Regular Scans</CardTitle>
              <CardDescription>
                Programs are scanned regularly for fresh data
              </CardDescription>
            </CardHeader>
            <CardContent>
              <ul className="text-sm text-muted-foreground space-y-1">
                <li>• Streaming pipeline</li>
                <li>• Last scan dates</li>
                <li>• Growing coverage</li>
              </ul>
            </CardContent>
          </Card>
        </div>
      </section>

      {/* How It Works */}
      <section className="bg-muted/30 py-16">
        <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
          <div className="text-center mb-12">
            <h2 className="text-3xl font-bold">How It Works</h2>
            <p className="text-muted-foreground mt-2">
              Get started in 3 simple steps
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
            <div className="text-center">
              <div className="w-12 h-12 rounded-full bg-primary text-primary-foreground flex items-center justify-center text-xl font-bold mx-auto mb-4">
                1
              </div>
              <h3 className="text-lg font-semibold mb-2">Sign In</h3>
              <p className="text-sm text-muted-foreground">
                Use Google or X to sign in instantly. No email verification needed.
              </p>
            </div>

            <div className="text-center">
              <div className="w-12 h-12 rounded-full bg-primary text-primary-foreground flex items-center justify-center text-xl font-bold mx-auto mb-4">
                2
              </div>
              <h3 className="text-lg font-semibold mb-2">Get API Key</h3>
              <p className="text-sm text-muted-foreground">
                Generate your personal API key from the dashboard for programmatic access.
              </p>
            </div>

            <div className="text-center">
              <div className="w-12 h-12 rounded-full bg-primary text-primary-foreground flex items-center justify-center text-xl font-bold mx-auto mb-4">
                3
              </div>
              <h3 className="text-lg font-semibold mb-2">Access Data</h3>
              <p className="text-sm text-muted-foreground">
                Browse programs in the UI or query the API for bulk data access.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* CTA Section */}
      <section className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8 py-16">
        <Card className="bg-gradient-to-r from-primary/10 to-primary/5 border-primary/20">
          <CardContent className="py-12 text-center">
            <Search className="h-12 w-12 mx-auto mb-4 text-primary" />
            <h2 className="text-2xl font-bold mb-2">Ready to Start Hunting?</h2>
            <p className="text-muted-foreground mb-6 max-w-xl mx-auto">
              Join security researchers using NeoBot-Net for bug bounty reconnaissance.
              Free access to all programs and data.
            </p>
            <Button size="lg" asChild>
              <Link href="/auth/login">
                Sign In Now
                <ArrowRight className="ml-2 h-5 w-5" />
              </Link>
            </Button>
          </CardContent>
        </Card>
      </section>

      {/* Footer */}
      <footer className="border-t py-8">
        <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
          <div className="flex flex-col sm:flex-row justify-between items-center gap-4">
            <p className="text-sm text-muted-foreground">
              © 2025 NeoBot-Net. Built for bug bounty researchers.
            </p>
            <div className="flex gap-4">
              <Link href="/api-docs" className="text-sm text-muted-foreground hover:text-foreground">
                API Docs
              </Link>
              <Link href="/auth/login" className="text-sm text-muted-foreground hover:text-foreground">
                Sign In
              </Link>
            </div>
          </div>
        </div>
      </footer>
    </div>
  );
}
