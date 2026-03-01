"use client";

import { useState, useEffect, useRef } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  X,
  Loader2,
  CheckCircle,
  AlertCircle,
  ExternalLink,
  Globe,
  Clock,
} from "lucide-react";
import { api } from "@/lib/api";
import type { OnboardStatus, OnboardRiskRaw } from "@/lib/api";
import { useRouter } from "next/navigation";

type ModalState = "idle" | "input" | "loading" | "done" | "error";

function formatInterval(seconds?: number): string {
  if (!seconds) return "daily";
  if (seconds <= 3600) return "hourly";
  if (seconds <= 86400) return "daily";
  if (seconds <= 604800) return "weekly";
  return "monthly";
}

export function CommandBar({
  onWatchesCreated,
}: {
  onWatchesCreated?: () => void;
}) {
  const [modalState, setModalState] = useState<ModalState>("idle");
  const [productUrl, setProductUrl] = useState("");
  const [jobId, setJobId] = useState<string | null>(null);
  const [jobStatus, setJobStatus] = useState<OnboardStatus | null>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const logsEndRef = useRef<HTMLDivElement>(null);
  const router = useRouter();

  useEffect(() => {
    if (!jobId || modalState !== "loading") return;
    pollRef.current = setInterval(async () => {
      try {
        const status = await api.onboard.status(jobId);
        setJobStatus(status);
        if (status.status === "completed") {
          clearInterval(pollRef.current!);
          setModalState("done");
          onWatchesCreated?.();
        } else if (status.status === "failed") {
          clearInterval(pollRef.current!);
          setModalState("error");
        }
      } catch {
        clearInterval(pollRef.current!);
        setModalState("error");
      }
    }, 2000);
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, [jobId, modalState, onWatchesCreated]);

  useEffect(() => {
    logsEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [jobStatus?.logs]);

  const handleAnalyze = async () => {
    if (!productUrl.trim()) return;
    setModalState("loading");
    setJobStatus(null);
    try {
      const { job_id } = await api.onboard.start(productUrl.trim());
      setJobId(job_id);
    } catch {
      setModalState("error");
    }
  };

  const closeModal = () => {
    if (pollRef.current) clearInterval(pollRef.current);
    setModalState("idle");
    setProductUrl("");
    setJobId(null);
    setJobStatus(null);
  };

  const goToWatches = () => {
    closeModal();
    router.push("/watches");
  };

  const logs = jobStatus?.logs ?? [];
  const risks: OnboardRiskRaw[] = jobStatus?.risks ?? [];

  return (
    <>
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
        <Button className="shrink-0" onClick={() => setModalState("input")}>
          Analyze product
        </Button>
      </div>

      {modalState !== "idle" && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4">
          <div className="relative w-full max-w-2xl max-h-[85vh] overflow-auto rounded-2xl border border-border bg-card p-6 shadow-2xl">
            <button
              onClick={closeModal}
              className="absolute right-4 top-4 text-muted-foreground hover:text-foreground"
            >
              <X className="h-4 w-4" />
            </button>

            {modalState === "input" && (
              <>
                <h2 className="text-lg font-semibold text-foreground">
                  Analyze product for compliance risks
                </h2>
                <p className="mt-1 text-sm text-muted-foreground">
                  Paste your product URL. Claude will identify every applicable
                  regulation and create watches automatically.
                </p>
                <div className="mt-4 flex gap-2">
                  <Input
                    placeholder="https://yourapp.com"
                    value={productUrl}
                    onChange={(e) => setProductUrl(e.target.value)}
                    onKeyDown={(e) => e.key === "Enter" && handleAnalyze()}
                    className="flex-1"
                    autoFocus
                  />
                  <Button
                    onClick={handleAnalyze}
                    disabled={!productUrl.trim()}
                  >
                    Analyze
                  </Button>
                </div>
              </>
            )}

            {modalState === "loading" && (
              <>
                <div className="flex items-center gap-3 mb-4">
                  <Loader2 className="h-5 w-5 animate-spin text-primary" />
                  <h2 className="text-lg font-semibold text-foreground">
                    Analyzing {productUrl}
                  </h2>
                </div>

                {/* Live logs */}
                <div className="rounded-lg border border-border bg-background/60 p-3 max-h-48 overflow-auto font-mono text-xs space-y-1 mb-4">
                  {logs.length === 0 && (
                    <p className="text-muted-foreground">
                      Starting analysis...
                    </p>
                  )}
                  {logs.map((log, i) => (
                    <div key={i} className="flex gap-2">
                      <span className="text-muted-foreground shrink-0">
                        [{new Date(log.t * 1000).toLocaleTimeString()}]
                      </span>
                      <span className="text-foreground">{log.msg}</span>
                    </div>
                  ))}
                  <div ref={logsEndRef} />
                </div>

                {/* Show risks as they come in */}
                {risks.length > 0 && (
                  <div className="space-y-2 max-h-[40vh] overflow-auto">
                    <p className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
                      {risks.length} risks identified — creating watches...
                    </p>
                    {risks.map((r, i) => (
                      <div
                        key={i}
                        className="rounded-lg border border-border bg-muted/30 p-3 space-y-1"
                      >
                        <div className="flex items-start justify-between gap-2">
                          <span className="text-sm font-medium text-foreground">
                            {r.regulation_title}
                          </span>
                          {r.jurisdiction && (
                            <span className="flex items-center gap-1 rounded-full bg-primary/15 px-2 py-0.5 text-[10px] font-medium text-primary shrink-0">
                              <Globe className="h-3 w-3" />
                              {r.jurisdiction}
                            </span>
                          )}
                        </div>
                        {r.risk_rationale && (
                          <p className="text-xs text-muted-foreground">
                            {r.risk_rationale}
                          </p>
                        )}
                      </div>
                    ))}
                  </div>
                )}
              </>
            )}

            {modalState === "done" && jobStatus && (
              <>
                <div className="flex items-center gap-2 mb-2">
                  <CheckCircle className="h-5 w-5 text-primary" />
                  <h2 className="text-lg font-semibold text-foreground">
                    Analysis complete
                  </h2>
                </div>
                <div className="flex gap-4 text-sm text-muted-foreground mb-3">
                  <span>
                    <span className="font-medium text-foreground">
                      {jobStatus.risks_identified ?? 0}
                    </span>{" "}
                    risks
                  </span>
                  <span>
                    <span className="font-medium text-foreground">
                      {jobStatus.watches_created ?? 0}
                    </span>{" "}
                    watches
                  </span>
                </div>

                <details className="mb-3">
                  <summary className="text-xs text-muted-foreground cursor-pointer hover:text-foreground">
                    View logs ({logs.length})
                  </summary>
                  <div className="mt-2 rounded-lg border border-border bg-background/60 p-3 max-h-32 overflow-auto font-mono text-xs space-y-1">
                    {logs.map((log, i) => (
                      <div key={i} className="flex gap-2">
                        <span className="text-muted-foreground shrink-0">
                          [{new Date(log.t * 1000).toLocaleTimeString()}]
                        </span>
                        <span className="text-foreground">{log.msg}</span>
                      </div>
                    ))}
                  </div>
                </details>

                {risks.length > 0 && (
                  <div className="space-y-2 max-h-[40vh] overflow-auto mb-4">
                    {risks.map((r, i) => (
                      <div
                        key={i}
                        className="rounded-lg border border-border bg-muted/30 p-3 space-y-1"
                      >
                        <div className="flex items-start justify-between gap-2">
                          <span className="text-sm font-medium text-foreground">
                            {r.regulation_title}
                          </span>
                          {r.jurisdiction && (
                            <span className="flex items-center gap-1 rounded-full bg-primary/15 px-2 py-0.5 text-[10px] font-medium text-primary shrink-0">
                              <Globe className="h-3 w-3" />
                              {r.jurisdiction}
                            </span>
                          )}
                        </div>
                        {r.risk_rationale && (
                          <p className="text-xs text-muted-foreground">
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
                            {formatInterval(r.check_interval_seconds)}
                          </span>
                        </div>
                      </div>
                    ))}
                  </div>
                )}

                <div className="flex gap-2">
                  <Button onClick={goToWatches} className="flex-1">
                    View watches
                  </Button>
                  <Button variant="outline" onClick={closeModal}>
                    Close
                  </Button>
                </div>
              </>
            )}

            {modalState === "error" && (
              <>
                <div className="flex items-center gap-2">
                  <AlertCircle className="h-5 w-5 text-destructive" />
                  <h2 className="text-lg font-semibold text-foreground">
                    Analysis failed
                  </h2>
                </div>
                <p className="mt-2 text-sm text-muted-foreground">
                  {jobStatus?.error ??
                    "Something went wrong. Please try again."}
                </p>
                {logs.length > 0 && (
                  <details className="mt-3">
                    <summary className="text-xs text-muted-foreground cursor-pointer hover:text-foreground">
                      View logs ({logs.length})
                    </summary>
                    <div className="mt-2 rounded-lg border border-border bg-background/60 p-3 max-h-32 overflow-auto font-mono text-xs space-y-1">
                      {logs.map((log, i) => (
                        <div key={i} className="flex gap-2">
                          <span className="text-muted-foreground shrink-0">
                            [{new Date(log.t * 1000).toLocaleTimeString()}]
                          </span>
                          <span className="text-foreground">{log.msg}</span>
                        </div>
                      ))}
                    </div>
                  </details>
                )}
                <div className="mt-4 flex gap-2">
                  <Button
                    onClick={() => setModalState("input")}
                    className="flex-1"
                  >
                    Try again
                  </Button>
                  <Button variant="outline" onClick={closeModal}>
                    Close
                  </Button>
                </div>
              </>
            )}
          </div>
        </div>
      )}
    </>
  );
}
