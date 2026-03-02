"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth";
import { useEffect } from "react";

const nav = [
  { href: "/app", label: "Dashboard" },
  { href: "/watches", label: "Watches" },
  { href: "/alerts", label: "Alerts" },
  { href: "/history", label: "Run History" },
];

// Pages that don't need the sidebar or auth
const PUBLIC_PATHS = ["/", "/login"];

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const { session, loading, signOut, user } = useAuth();

  const isPublic = PUBLIC_PATHS.includes(pathname) || pathname === "/analyze";

  // Redirect to login if not authenticated on protected pages
  useEffect(() => {
    if (!loading && !session && !isPublic) {
      router.replace("/login");
    }
  }, [loading, session, isPublic, router]);

  // Public pages render without shell
  if (isPublic) {
    return <>{children}</>;
  }

  // Show loading while checking auth
  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <div className="h-8 w-8 animate-spin rounded-full border-2 border-primary border-t-transparent" />
      </div>
    );
  }

  // Not authenticated — will redirect via useEffect
  if (!session) return null;

  return (
    <div className="flex min-h-screen">
      <aside className="flex w-56 flex-col border-r border-border bg-card/80 backdrop-blur-sm">
        <div className="border-b border-border p-5">
          <Link href="/" className="flex items-center gap-2">
            <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-primary text-sm font-semibold text-primary-foreground">
              CR
            </span>
            <span className="text-sm font-semibold">Compliance Radar</span>
          </Link>
        </div>
        <nav className="flex-1 space-y-0.5 p-3">
          {nav.map((item) => {
            const isActive =
              pathname === item.href ||
              (item.href !== "/app" && pathname.startsWith(item.href));
            return (
              <Link
                key={item.href}
                href={item.href}
                className={`block rounded-lg px-3 py-2 text-sm transition-colors ${
                  isActive
                    ? "bg-primary/15 font-medium text-primary"
                    : "text-muted-foreground hover:bg-muted hover:text-foreground"
                }`}
              >
                {item.label}
              </Link>
            );
          })}
        </nav>
        <div className="border-t border-border p-3">
          <div className="mb-2 truncate px-3 text-xs text-muted-foreground">
            {user?.email}
          </div>
          <button
            onClick={() => signOut().then(() => router.replace("/login"))}
            className="w-full rounded-lg px-3 py-2 text-left text-sm text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
          >
            Sign out
          </button>
        </div>
      </aside>
      <main className="flex-1 overflow-auto">{children}</main>
    </div>
  );
}
