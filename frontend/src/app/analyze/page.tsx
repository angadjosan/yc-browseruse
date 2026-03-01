"use client";

import { useState, useEffect, useRef } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
import type { OnboardStatus, OnboardRiskRaw } from "@/lib/api";
import {
  Loader2,
  CheckCircle,
  AlertCircle,
  Globe,
  Clock,
  ExternalLink,
  ArrowRight,
  Radar,
  ArrowLeft,
} from "lucide-react";

type FlowState = "input" | "analyzing" | "done" | "error";

function formatInterval(seconds?: number): string {
  if (!seconds) return "daily";
  if (seconds <= 3600) return "hourly";
  if (seconds <= 86400) return "daily";
  if (seconds <= 604800) return "weekly";
  return "monthly";
}

export default function AnalyzePage() {
  const router = useRouter();
  const [flowState, setFlowState] = useState<FlowState>("input");
  const [productUrl, setProductUrl] = useState("");
  const [jobId, setJobId] = useState<string | null>(null);
  const [jobStatus, setJobStatus] = useState<OnboardStatus | null>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const logsEndRef = useRef<HTMLDivElement>(null);

  // Poll job status
  useEffect(() => {
    if (!jobId || flowState === "done" || flowState === "error" || flowState === "input")
      return;
    pollRef.current = setInterval(async () => {
      try {
        const status = await api.onboard.status(jobId);
        setJobStatus(status);
        if (status.status === "completed") {
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

  // Auto-scroll logs
  useEffect(() => {
    logsEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [jobStatus?.logs?.length]);

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

  const logs = jobStatus?.logs ?? [];
  const risks: OnboardRiskRaw[] = jobStatus?.risks ?? [];

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

        {/* ─── INPUT ─── */}
        {flowState === "input" && (
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
        {flowState === "analyzing" && (
          <div className="w-full max-w-4xl flex flex-col gap-4 flex-1">
            <div className="flex items-center gap-3">
              <Loader2 className="h-5 w-5 animate-spin text-primary" />
              <h2 className="text-lg font-semibold text-foreground">
                Analyzing {productUrl}
              </h2>
            </div>

            {/* Risks as they come in */}
            {risks.length > 0 && (
              <div className="rounded-xl border border-border bg-card/80 p-4 backdrop-blur-sm">
                <p className="text-xs font-medium uppercase tracking-wider text-muted-foreground mb-2">
                  {risks.length} risks identified
                  {jobStatus?.watches_created
                    ? ` — ${jobStatus.watches_created} watches created`
                    : " — creating watches..."}
                </p>
                <div className="space-y-1.5 max-h-48 overflow-auto">
                  {risks.map((r, i) => (
                    <div
                      key={i}
                      className="flex items-center justify-between gap-2 rounded-lg bg-muted/30 px-3 py-2"
                    >
                      <span className="text-sm text-foreground truncate">
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
                  ))}
                </div>
              </div>
            )}

            {/* Full log output */}
            <div className="rounded-xl border border-border bg-black/60 backdrop-blur-sm flex-1 min-h-[300px] max-h-[60vh] overflow-auto p-4 font-mono text-xs leading-relaxed">
              {logs.length === 0 && (
                <p className="text-muted-foreground animate-pulse">
                  Waiting for agent output...
                </p>
              )}
              {logs.map((log, i) => (
                <div key={i} className="flex gap-2 py-0.5">
                  <span className="text-muted-foreground shrink-0 select-none">
                    {new Date(log.t * 1000).toLocaleTimeString()}
                  </span>
                  <span
                    className={
                      log.msg.startsWith("───")
                        ? "text-primary font-semibold"
                        : log.msg.startsWith("  ")
                          ? "text-muted-foreground"
                          : "text-foreground"
                    }
                  >
                    {log.msg}
                  </span>
                </div>
              ))}
              <div ref={logsEndRef} />
            </div>
          </div>
        )}

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

            {/* Full log output (scrollable) */}
            <details>
              <summary className="text-xs text-muted-foreground cursor-pointer hover:text-foreground">
                Full agent logs ({logs.length} entries)
              </summary>
              <div className="mt-2 rounded-xl border border-border bg-black/60 backdrop-blur-sm max-h-[40vh] overflow-auto p-4 font-mono text-xs leading-relaxed">
                {logs.map((log, i) => (
                  <div key={i} className="flex gap-2 py-0.5">
                    <span className="text-muted-foreground shrink-0 select-none">
                      {new Date(log.t * 1000).toLocaleTimeString()}
                    </span>
                    <span
                      className={
                        log.msg.startsWith("───")
                          ? "text-primary font-semibold"
                          : log.msg.startsWith("  ")
                            ? "text-muted-foreground"
                            : "text-foreground"
                      }
                    >
                      {log.msg}
                    </span>
                  </div>
                ))}
              </div>
            </details>

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

              {logs.length > 0 && (
                <div className="rounded-xl border border-border bg-black/60 max-h-[40vh] overflow-auto p-4 font-mono text-xs leading-relaxed mb-4">
                  {logs.map((log, i) => (
                    <div key={i} className="flex gap-2 py-0.5">
                      <span className="text-muted-foreground shrink-0 select-none">
                        {new Date(log.t * 1000).toLocaleTimeString()}
                      </span>
                      <span className="text-foreground">{log.msg}</span>
                    </div>
                  ))}
                </div>
              )}

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
