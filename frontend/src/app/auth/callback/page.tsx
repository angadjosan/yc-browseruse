"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { supabase } from "@/lib/supabase";

export default function AuthCallbackPage() {
  const router = useRouter();

  useEffect(() => {
    // Supabase JS client auto-detects the code/hash in the URL and exchanges it
    // for a session when onAuthStateChange fires. We just wait for that.
    const {
      data: { subscription },
    } = supabase.auth.onAuthStateChange((event) => {
      if (event === "SIGNED_IN") {
        const returnTo = localStorage.getItem("auth_return_to") || "/app";
        localStorage.removeItem("auth_return_to");
        router.replace(returnTo);
      }
    });

    // Fallback: if already signed in (e.g. page refresh), redirect immediately
    supabase.auth.getSession().then(({ data: { session } }) => {
      if (session) {
        const returnTo = localStorage.getItem("auth_return_to") || "/app";
        localStorage.removeItem("auth_return_to");
        router.replace(returnTo);
      }
    });

    return () => subscription.unsubscribe();
  }, [router]);

  return (
    <div className="flex min-h-screen items-center justify-center">
      <div className="h-8 w-8 animate-spin rounded-full border-2 border-primary border-t-transparent" />
    </div>
  );
}
