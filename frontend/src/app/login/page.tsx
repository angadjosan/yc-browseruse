"use client";

import { useAuth } from "@/lib/auth";
import { GitHubSignInButton } from "@/components/github-sign-in";
import { useRouter, useSearchParams } from "next/navigation";
import { useEffect } from "react";

export default function LoginPage() {
  const { session, loading } = useAuth();
  const router = useRouter();
  const searchParams = useSearchParams();
  const next = searchParams.get("next") || "/app";

  useEffect(() => {
    if (!loading && session) {
      router.replace(next);
    }
  }, [loading, session, router, next]);

  if (loading || session) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <div className="h-8 w-8 animate-spin rounded-full border-2 border-primary border-t-transparent" />
      </div>
    );
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-background px-4">
      <div className="w-full max-w-sm space-y-6">
        <div className="text-center">
          <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-xl bg-primary text-lg font-bold text-primary-foreground">
            CR
          </div>
          <h1 className="mt-4 text-2xl font-semibold">Welcome</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Sign in to Compliance Radar
          </p>
        </div>

        {searchParams.get("error") === "auth" && (
          <p className="rounded-lg bg-red-500/10 px-3 py-2 text-sm text-red-400">
            Authentication failed. Please try again.
          </p>
        )}

        <GitHubSignInButton returnTo={next} />
      </div>
    </div>
  );
}
