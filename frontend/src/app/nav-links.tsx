"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

export function NavLinks({ nav }: { nav: { href: string; label: string }[] }) {
  const pathname = usePathname();
  return (
    <>
      {nav.map((item) => {
        const isActive = pathname === item.href || (item.href !== "/" && pathname.startsWith(item.href));
        return (
          <Link
            key={item.href}
            href={item.href}
            className={`block px-3 py-2 rounded-md text-sm transition-colors ${
              isActive
                ? "bg-[var(--primary)]/15 text-[var(--primary)] font-medium"
                : "text-[var(--muted-foreground)] hover:text-[var(--foreground)] hover:bg-[var(--muted)]"
            }`}
          >
            {item.label}
          </Link>
        );
      })}
    </>
  );
}
