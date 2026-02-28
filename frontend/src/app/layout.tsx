import type { Metadata } from "next";
import Link from "next/link";
import "./globals.css";
import { NavLinks } from "./nav-links";

export const metadata: Metadata = {
  title: "Compliance Change Radar",
  description: "Describe your product; we watch every regulation and vendor policy that affects you and ticket your team when something changes.",
};

const nav = [
  { href: "/", label: "Dashboard" },
  { href: "/watches", label: "Watches" },
  { href: "/history", label: "History" },
  { href: "/evidence", label: "Evidence" },
];

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="dark">
      <body className="min-h-screen bg-[var(--background)] text-[var(--foreground)] antialiased">
        <div className="flex min-h-screen">
          <aside className="w-56 border-r border-[var(--border)] bg-[var(--card)] flex flex-col">
            <div className="p-6 border-b border-[var(--border)]">
              <Link href="/" className="flex items-center gap-2">
                <span className="w-8 h-8 rounded-lg bg-[var(--primary)] flex items-center justify-center text-[var(--primary-foreground)] font-semibold text-sm">
                  CR
                </span>
                <span className="font-semibold text-sm">Compliance Radar</span>
              </Link>
            </div>
            <nav className="flex-1 p-3 space-y-0.5">
              <NavLinks nav={nav} />
            </nav>
          </aside>
          <main className="flex-1 overflow-auto">
            {children}
          </main>
        </div>
      </body>
    </html>
  );
}
