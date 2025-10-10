import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";

const inter = Inter({ subsets: ["latin"], display: "swap" });

export const metadata: Metadata = {
  title: "CB AI Chat System",
  description: "Production chat service with multi-model support",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className="h-full dark">
      <body className={`${inter.className} h-full bg-background text-foreground antialiased`}>
        <div className="min-h-dvh flex flex-col">
          <header className="border-b border-border">
            <div className="mx-auto max-w-5xl px-4 py-3 flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className="h-7 w-7 rounded-xl bg-primary/10 ring-1 ring-primary/30 flex items-center justify-center">💬</div>
                <h1 className="text-lg font-semibold tracking-tight">CB AI Chat</h1>
              </div>
              <div className="text-xs text-muted-foreground">Production</div>
            </div>
          </header>
          <main className="flex-1">
            <div className="mx-auto max-w-5xl px-4 py-6">{children}</div>
          </main>
          <footer className="border-t border-border">
            <div className="mx-auto max-w-5xl px-4 py-3 text-xs text-muted-foreground">
              © CB AI Labs
            </div>
          </footer>
        </div>
      </body>
    </html>
  );
}
