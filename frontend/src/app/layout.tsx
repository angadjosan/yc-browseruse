import type { Metadata } from "next";
import "./globals.css";
import { AppShell } from "./app-shell";

export const metadata: Metadata = {
  title: "Compliance Change Radar",
  description: "Describe your product; we watch every regulation and vendor policy that affects you and ticket your team when something changes.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="dark">
      <body className="min-h-screen bg-background text-foreground antialiased">
        <AppShell>{children}</AppShell>
      </body>
    </html>
  );
}
