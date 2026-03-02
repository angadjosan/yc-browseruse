"use client";

import { useState, useEffect, useRef } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { OnboardStatus, OnboardRiskRaw, OnboardLog } from "@/lib/api";
import { cn } from "@/lib/utils";
import {
  Loader2,
  CheckCircle,
  Check,
  AlertCircle,
  Globe,
  Clock,
  ExternalLink,
  ArrowRight,
  Radar,
  ArrowLeft,
} from "lucide-react";

const STEPS = [
  "Scraping product page",
  "Analyzing compliance risks",
  "Creating monitors",
] as const;

function getCurrentStep(logs: OnboardLog[]): 1 | 2 | 3 {
  const msgs = logs.map((l) => l.msg);
  if (msgs.some((m) => m.includes("STEP 3"))) return 3;
  if (msgs.some((m) => m.includes("STEP 2"))) return 2;
  return 1;
}

function getDisplayLogs(logs: OnboardLog[]): string[] {
  return logs
    .filter((l) => {
      const m = l.msg;
      if (m.startsWith("    |")) return false;
      if (/^\s+\[\d+\]/.test(m)) return false;
      if (m.startsWith("    Rationale:")) return false;
      if (/^\s+Risk \d+\/\d+:/.test(m)) return false;
      return true;
    })
    .slice(-12)
    .map((l) => {
      const m = l.msg.trim();
      if (m.startsWith("───") || m.endsWith("───")) {
        return m.replace(/─+/g, "").trim();
      }
      return m;
    });
}

type FlowState = "input" | "analyzing" | "done" | "error";

function formatInterval(seconds?: number): string {
  if (!seconds) return "daily";
  if (seconds <= 3600) return "hourly";
  if (seconds <= 86400) return "daily";
  if (seconds <= 604800) return "weekly";
  return "monthly";
}

// ── Inline auth form (login/signup on the analyze page) ──────────────────

function InlineAuth({ onAuthenticated }: { onAuthenticated: () => void }) {
  const { signIn, signUp, session } = useAuth();
  const [mode, setMode] = useState<"login" | "signup">("signup");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [name, setName] = useState("");
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (session) onAuthenticated();
  }, [session, onAuthenticated]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setSubmitting(true);
    try {
      if (mode === "login") {
        await signIn(email, password);
      } else {
        await signUp(email, password, name);
      }
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Something went wrong");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="w-full max-w-xl">
      <div className="rounded-2xl border border-border bg-card/80 p-8 backdrop-blur-sm shadow-2xl">
        <h2 className="text-lg font-semibold text-foreground mb-1">
          {mode === "signup" ? "Create an account to get started" : "Sign in to continue"}
        </h2>
        <p className="text-sm text-muted-foreground mb-6">
          {mode === "signup"
            ? "We'll analyze your product and set up compliance monitors."
            : "Sign in to your existing account."}
        </p>

        <form onSubmit={handleSubmit} className="space-y-3">
          {mode === "signup" && (
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="w-full rounded-lg border border-border bg-background px-4 py-2.5 text-sm text-foreground placeholder:text-muted-foreground focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary"
              placeholder="Your name"
            />
          )}
          <input
            type="email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="w-full rounded-lg border border-border bg-background px-4 py-2.5 text-sm text-foreground placeholder:text-muted-foreground focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary"
            placeholder="you@company.com"
            autoFocus
          />
          <input
            type="password"
            required
            minLength={6}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="w-full rounded-lg border border-border bg-background px-4 py-2.5 text-sm text-foreground placeholder:text-muted-foreground focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary"
            placeholder="Password (6+ characters)"
          />

          {error && (
            <p className="rounded-lg bg-red-500/10 px-3 py-2 text-sm text-red-400">
              {error}
            </p>
          )}

          <button
            type="submit"
            disabled={submitting}
            className="w-full rounded-lg bg-primary px-4 py-2.5 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90 disabled:opacity-50"
          >
            {submitting
              ? "..."
              : mode === "signup"
                ? "Create account"
                : "Sign in"}
          </button>
        </form>

        <p className="mt-4 text-center text-sm text-muted-foreground">
          {mode === "signup" ? (
            <>
              Already have an account?{" "}
              <button
                onClick={() => { setMode("login"); setError(""); }}
                className="font-medium text-primary hover:underline"
              >
                Sign in
              </button>
            </>
          ) : (
            <>
              Don&apos;t have an account?{" "}
              <button
                onClick={() => { setMode("signup"); setError(""); }}
                className="font-medium text-primary hover:underline"
              >
                Sign up
              </button>
            </>
          )}
        </p>
      </div>
    </div>
  );
}

// ── Main page ────────────────────────────────────────────────────────────

export default function AnalyzePage() {
  const router = useRouter();
  const { session, loading } = useAuth();
  const [flowState, setFlowState] = useState<FlowState>("input");
  const [productUrl, setProductUrl] = useState("");
  const [jobId, setJobId] = useState<string | null>(null);
  const [jobStatus, setJobStatus] = useState<OnboardStatus | null>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // Track whether we've passed auth (either already logged in or just signed up)
  const [authed, setAuthed] = useState(false);
  useEffect(() => {
    if (session) setAuthed(true);
  }, [session]);

  // Poll job status
  useEffect(() => {
    if (!jobId || flowState === "done" || flowState === "error" || flowState === "input")
      return;
    pollRef.current = setInterval(async () => {
      try {
        const status = await api.onboard.status(jobId);
        setJobStatus(status);
        if (status.status === "completed" || status.status === "completed_with_errors") {
          clearInterval(pollRef.current!);
          setFlowState("done");
        } else if (status.status === "failed") {
          clearInterval(pollRef.current!);
          setFlowState("error");
        }
      } catch {
        clearInterval(pollRef.current!);
        setFlowState("error");
      }
    }, 1500);
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, [jobId, flowState]);

  const handleAnalyze = async () => {
    if (!productUrl.trim()) return;
    setFlowState("analyzing");
    setJobStatus(null);
    try {
      const { job_id } = await api.onboard.start(productUrl.trim());
      setJobId(job_id);
    } catch {
      setFlowState("error");
    }
  };

  const handleReset = () => {
    if (pollRef.current) clearInterval(pollRef.current);
    setFlowState("input");
    setProductUrl("");
    setJobId(null);
    setJobStatus(null);
  };

  const risks: OnboardRiskRaw[] = jobStatus?.risks ?? [];

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <div className="h-8 w-8 animate-spin rounded-full border-2 border-primary border-t-transparent" />
      </div>
    );
  }

  return (
    <div className="relative min-h-screen">
      {/* Background gradient */}
      <div className="pointer-events-none fixed inset-0 z-0" aria-hidden>
        <div
          className="absolute inset-0 opacity-30"
          style={{
            background:
              "radial-gradient(ellipse 80% 50% at 50% -20%, rgba(0,255,136,0.12), transparent 50%), radial-gradient(ellipse 60% 40% at 100% 50%, rgba(0,255,136,0.06), transparent 40%)",
          }}
        />
      </div>

      <div className="relative z-10 flex min-h-screen flex-col items-center px-4 py-10">
        {/* Header */}
        <div className="flex items-center gap-3 mb-2">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-primary/15 text-primary shadow-[0_0_20px_-4px_rgba(0,255,136,0.3)]">
            <Radar className="h-5 w-5" />
          </div>
          <h1 className="text-2xl font-bold tracking-tight text-foreground">
            Compliance Radar
          </h1>
        </div>
        <p className="text-sm text-muted-foreground mb-8 text-center max-w-lg">
          Paste your product URL. We scrape it, identify every regulation that
          applies, and create monitors that alert you when anything changes.
        </p>

        {/* ─── AUTH GATE ─── */}
        {!authed && flowState === "input" && (
          <InlineAuth onAuthenticated={() => setAuthed(true)} />
        )}

        {/* ─── INPUT ─── */}
        {authed && flowState === "input" && (
          <div className="w-full max-w-xl">
            <div className="rounded-2xl border border-border bg-card/80 p-8 backdrop-blur-sm shadow-2xl">
              <label
                htmlFor="product-url"
                className="block text-sm font-medium text-foreground mb-2"
              >
                Product URL
              </label>
              <div className="flex gap-2">
                <input
                  id="product-url"
                  type="url"
                  value={productUrl}
                  onChange={(e) => setProductUrl(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && handleAnalyze()}
                  placeholder="https://yourapp.com"
                  autoFocus
                  className="flex-1 rounded-lg border border-border bg-background px-4 py-2.5 text-foreground placeholder:text-muted-foreground focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary"
                />
                <button
                  onClick={handleAnalyze}
                  disabled={!productUrl.trim()}
                  className="rounded-lg bg-primary px-5 py-2.5 text-sm font-medium text-primary-foreground hover:opacity-90 disabled:opacity-40 transition-opacity flex items-center gap-2"
                >
                  Analyze <ArrowRight className="h-4 w-4" />
                </button>
              </div>
            </div>
            <button
              onClick={() => router.push("/")}
              className="mt-4 flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground mx-auto"
            >
              <ArrowLeft className="h-3.5 w-3.5" /> Back
            </button>
          </div>
        )}

        {/* ─── ANALYZING ─── */}
        {flowState === "analyzing" && (() => {
          const logs = jobStatus?.logs ?? [];
          const currentStep = getCurrentStep(logs);
          const displayLogs = getDisplayLogs(logs);
          return (
            <div className="w-full max-w-2xl flex flex-col gap-4">
              {/* Header */}
              <div className="flex items-start gap-3">
                <Loader2 className="h-5 w-5 animate-spin text-primary mt-0.5 shrink-0" />
                <div>
                  <h2 className="text-lg font-semibold text-foreground leading-tight">
                    Analyzing {productUrl}
                  </h2>
                  <p className="text-xs text-muted-foreground mt-0.5">
                    This typically takes 2–3 minutes
                  </p>
                </div>
              </div>

              {/* Step progress */}
              <div className="rounded-xl border border-border bg-card/80 p-4 backdrop-blur-sm">
                <div className="space-y-1">
                  {STEPS.map((label, i) => {
                    const stepNum = (i + 1) as 1 | 2 | 3;
                    const done = currentStep > stepNum;
                    const active = currentStep === stepNum;
                    return (
                      <div key={label} className="flex items-center gap-3 py-1.5">
                        <div
                          className={cn(
                            "h-6 w-6 rounded-full flex items-center justify-center text-xs font-bold shrink-0 transition-colors",
                            done
                              ? "bg-primary text-primary-foreground"
                              : active
                              ? "bg-primary/15 text-primary border border-primary"
                              : "bg-muted text-muted-foreground"
                          )}
                        >
                          {done ? <Check className="h-3.5 w-3.5" /> : stepNum}
                        </div>
                        <span
                          className={cn(
                            "text-sm flex-1 transition-colors",
                            done
                              ? "text-foreground"
                              : active
                              ? "text-foreground font-medium"
                              : "text-muted-foreground"
                          )}
                        >
                          {label}
                        </span>
                        {active && (
                          <Loader2 className="h-3.5 w-3.5 animate-spin text-primary shrink-0" />
                        )}
                        {done && (
                          <Check className="h-3.5 w-3.5 text-primary shrink-0" />
                        )}
                      </div>
                    );
                  })}
                </div>
              </div>

              {/* Live activity */}
              {displayLogs.length > 0 && (
                <div className="rounded-xl border border-border bg-card/80 p-3 backdrop-blur-sm">
                  <p className="text-[10px] font-medium uppercase tracking-wider text-muted-foreground mb-2">
                    Live activity
                  </p>
                  <div className="font-mono text-xs space-y-0.5 max-h-36 overflow-auto">
                    {displayLogs.map((line, i) => (
                      <div
                        key={i}
                        className={cn(
                          "flex gap-2",
                          i === displayLogs.length - 1
                            ? "text-foreground"
                            : "text-muted-foreground"
                        )}
                      >
                        <span className="text-primary/50 shrink-0">›</span>
                        <span className="break-all">{line}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Risks as they appear */}
              {risks.length > 0 && (
                <div className="rounded-xl border border-border bg-card/80 p-4 backdrop-blur-sm">
                  <p className="text-xs font-medium uppercase tracking-wider text-muted-foreground mb-3">
                    {risks.length} risks identified
                    {jobStatus?.watches_created
                      ? ` — ${jobStatus.watches_created} monitors created`
                      : " — creating monitors…"}
                  </p>
                  <div className="space-y-1.5 max-h-60 overflow-auto">
                    {risks.map((r, i) => (
                      <div
                        key={i}
                        className="flex items-center justify-between gap-2 rounded-lg bg-muted/30 px-3 py-2"
                      >
                        <span className="text-sm text-foreground truncate">
                          {r.regulation_title}
                        </span>
                        {r.jurisdiction && (
                          <span className="flex items-center gap-1 rounded-full bg-primary/15 px-2 py-0.5 text-[10px] font-medium text-primary shrink-0">
                            <Globe className="h-3 w-3" />
                            {r.jurisdiction}
                          </span>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          );
        })()}

        {/* ─── DONE ─── */}
        {flowState === "done" && jobStatus && (
          <div className="w-full max-w-4xl flex flex-col gap-4 flex-1">
            <div className="flex items-center gap-3">
              <CheckCircle className="h-5 w-5 text-primary" />
              <h2 className="text-lg font-semibold text-foreground">
                Analysis complete
              </h2>
              <span className="text-sm text-muted-foreground">
                {jobStatus.risks_identified ?? 0} risks &middot;{" "}
                {jobStatus.watches_created ?? 0} watches
              </span>
            </div>

            {(jobStatus.watches_failed ?? 0) > 0 && (
              <div className="rounded-xl border border-yellow-500/30 bg-yellow-500/5 px-4 py-3 flex items-start gap-2.5">
                <AlertCircle className="h-4 w-4 text-yellow-500 mt-0.5 shrink-0" />
                <div>
                  <p className="text-sm font-medium text-yellow-500">
                    {jobStatus.watches_failed} monitor{jobStatus.watches_failed === 1 ? "" : "s"} failed to save
                  </p>
                  <p className="text-xs text-muted-foreground mt-0.5">
                    {jobStatus.watches_created ?? 0} of {jobStatus.risks_identified ?? 0} were stored successfully.
                    Re-analyze the product to retry the missing monitors.
                  </p>
                </div>
              </div>
            )}

            {/* Risk list — full detail */}
            <div className="rounded-xl border border-border bg-card/80 p-4 backdrop-blur-sm max-h-[40vh] overflow-auto">
              <p className="text-xs font-medium uppercase tracking-wider text-muted-foreground mb-3">
                Identified risks
              </p>
              <div className="space-y-2">
                {risks.map((r, i) => (
                  <div
                    key={i}
                    className="rounded-lg border border-border bg-muted/30 p-3 space-y-1.5"
                  >
                    <div className="flex items-start justify-between gap-2">
                      <span className="text-sm font-medium text-foreground">
                        {r.regulation_title}
                      </span>
                      <div className="flex items-center gap-1.5 shrink-0">
                        {r.jurisdiction && (
                          <span className="flex items-center gap-1 rounded-full bg-primary/15 px-2 py-0.5 text-[10px] font-medium text-primary">
                            <Globe className="h-3 w-3" />
                            {r.jurisdiction}
                          </span>
                        )}
                      </div>
                    </div>
                    {r.risk_rationale && (
                      <p className="text-xs text-muted-foreground leading-relaxed">
                        {r.risk_rationale}
                      </p>
                    )}
                    <div className="flex items-center gap-3 text-[10px] text-muted-foreground">
                      {r.source_url && (
                        <a
                          href={r.source_url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="flex items-center gap-0.5 text-primary hover:underline"
                        >
                          <ExternalLink className="h-3 w-3" />
                          Source
                        </a>
                      )}
                      <span className="flex items-center gap-0.5">
                        <Clock className="h-3 w-3" />
                        Checks {formatInterval(r.check_interval_seconds)}
                      </span>
                      {r.scope && <span>Scope: {r.scope}</span>}
                    </div>
                  </div>
                ))}
              </div>
            </div>

            <button
              onClick={() => router.push("/watches")}
              className="w-full rounded-lg bg-primary px-5 py-3 text-sm font-medium text-primary-foreground hover:opacity-90 transition-opacity flex items-center justify-center gap-2"
            >
              Go to watches <ArrowRight className="h-4 w-4" />
            </button>
          </div>
        )}

        {/* ─── ERROR ─── */}
        {flowState === "error" && (
          <div className="w-full max-w-2xl">
            <div className="rounded-2xl border border-border bg-card/80 p-6 backdrop-blur-sm shadow-2xl">
              <div className="flex items-center gap-3 mb-3">
                <AlertCircle className="h-5 w-5 text-destructive" />
                <h2 className="text-lg font-semibold text-foreground">
                  Analysis failed
                </h2>
              </div>
              <p className="text-sm text-muted-foreground mb-4">
                {jobStatus?.error ?? "Something went wrong. Please try again."}
              </p>

              <div className="flex gap-2">
                <button
                  onClick={handleReset}
                  className="flex-1 rounded-lg bg-primary px-5 py-2.5 text-sm font-medium text-primary-foreground hover:opacity-90 transition-opacity"
                >
                  Try again
                </button>
                <button
                  onClick={() => router.push("/")}
                  className="rounded-lg border border-border px-4 py-2.5 text-sm font-medium text-foreground hover:bg-muted transition-colors"
                >
                  Back
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
