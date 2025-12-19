'use client';

import Link from 'next/link';

export default function AboutPage() {
  return (
    <div className="min-h-screen flex flex-col">
      {/* Background pattern */}
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
        <div className="w-full max-w-2xl space-y-8">
          
          {/* Title */}
          <div className="text-center space-y-2">
            <h1 className="text-4xl sm:text-5xl font-bold tracking-tight font-mono text-foreground">
              about
            </h1>
            <div className="h-px w-16 bg-[--terminal-green] mx-auto" />
          </div>

          {/* Content */}
          <div className="space-y-6 text-center">
            <p className="text-lg text-muted-foreground font-mono leading-relaxed">
              neobotnet is a web reconnaissance framework built for security researchers and bug bounty hunters. 
              We continuously scan and index public-facing assets—subdomains, DNS records, and web servers—across 
              bug bounty programs, making reconnaissance data instantly accessible via a clean web interface and 
              a powerful API. Our goal is to eliminate the tedious setup and waiting time, so you can focus on 
              what matters: finding vulnerabilities.
            </p>

            <p className="text-sm text-muted-foreground/70 font-mono">
              More details coming soon.
            </p>
          </div>

          {/* Back Link */}
          <div className="text-center pt-8">
            <Link 
              href="/"
              className="text-[--terminal-green] hover:text-[--terminal-green]/80 font-bold font-mono transition-colors"
            >
              ← back to home
            </Link>
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

