import type { Metadata } from 'next';
import { Inter } from 'next/font/google';
import { AppNav } from '@/components/AppNav';
import './globals.css';

const inter = Inter({ subsets: ['latin'], display: 'swap' });

export const metadata: Metadata = {
  title: 'AI Chat System',
  description:
    'Multi-provider LLM gateway demo: SSE streaming, semantic cache, and provider failover, with the telemetry to prove each one.',
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className="h-full dark">
      <body className={`${inter.className} h-full bg-background text-foreground antialiased`}>
        <a
          href="#main"
          className="sr-only focus:not-sr-only focus:absolute focus:left-2 focus:top-2 focus:z-50 focus:rounded-md focus:bg-primary focus:px-3 focus:py-1.5 focus:text-primary-foreground"
        >
          Skip to content
        </a>
        <div className="flex min-h-dvh flex-col">
          <header className="border-b border-border">
            <div className="mx-auto flex max-w-7xl items-center justify-between px-4 py-2.5">
              <div className="flex items-center gap-2">
                <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-gradient-to-br from-blue-500 to-purple-600" aria-hidden="true">
                  <svg className="h-4 w-4 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z" />
                  </svg>
                </div>
                <span className="text-base font-semibold tracking-tight">AI Chat System</span>
                <span className="hidden text-xs text-muted-foreground sm:inline">LLM gateway with visible evidence</span>
              </div>
              <AppNav />
            </div>
          </header>
          <main id="main" className="flex-1">
            <div className="mx-auto max-w-7xl px-4 py-4">{children}</div>
          </main>
        </div>
      </body>
    </html>
  );
}
