'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { cn } from '@/lib/utils';

const LINKS = [
  { href: '/', label: 'Chat' },
  { href: '/evals', label: 'Evals' },
];

export function AppNav() {
  const pathname = usePathname();
  return (
    <nav aria-label="Primary" className="flex items-center gap-1 text-sm">
      {LINKS.map((l) => {
        const active = pathname === l.href;
        return (
          <Link
            key={l.href}
            href={l.href}
            aria-current={active ? 'page' : undefined}
            className={cn(
              'rounded-md px-2.5 py-1.5 hover:bg-accent focus:outline-none focus-visible:ring-2 focus-visible:ring-ring',
              active ? 'bg-accent text-foreground' : 'text-muted-foreground',
            )}
          >
            {l.label}
          </Link>
        );
      })}
      <a
        href="https://github.com/cbratkovics/chatbot-ai-system"
        target="_blank"
        rel="noreferrer"
        className="rounded-md px-2.5 py-1.5 text-muted-foreground hover:bg-accent focus:outline-none focus-visible:ring-2 focus-visible:ring-ring"
      >
        GitHub
      </a>
    </nav>
  );
}
