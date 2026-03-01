"use client";

import { useState, useEffect, useRef } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Search, X, Loader2, CheckCircle, AlertCircle } from "lucide-react";
import { api } from "@/lib/api";
import type { OnboardStatus } from "@/lib/api";
import { useRouter } from "next/navigation";

type ModalState = "idle" | "input" | "loading" | "done" | "error";

export function CommandBar({ onWatchesCreated }: { onWatchesCreated?: () => void }) {
  const [query, setQuery] = useState("");
  const [modalState, setModalState] = useState<ModalState>("idle");
  const [productUrl, setProductUrl] = useState("");
  const [jobId, setJobId] = useState<string | null>(null);
  const [jobStatus, setJobStatus] = useState<OnboardStatus | null>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const router = useRouter();

  // Poll job status
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
    return () => { if (pollRef.current) clearInterval(pollRef.current); };
  }, [jobId, modalState, onWatchesCreated]);

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

  return (
    <>
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            placeholder="Describe what to watch… (e.g., 'GDPR guidance for AI profiling', 'Stripe ToS', 'HIPAA tracking pixels')"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            className="pl-9 border-primary/20 bg-background/60 placeholder:text-muted-foreground focus-visible:ring-primary/50 focus-visible:shadow-[0_0_0_3px_rgba(0,255,136,0.15)]"
          />
        </div>
        <Button className="shrink-0" onClick={() => setModalState("input")}>
          Analyze product
        </Button>
      </div>

      {/* Onboarding modal */}
      {modalState !== "idle" && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4">
          <div className="relative w-full max-w-md rounded-2xl border border-border bg-card p-6 shadow-2xl">
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
                  Paste your product URL. Claude will identify every applicable regulation and create watches automatically.
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
                  <Button onClick={handleAnalyze} disabled={!productUrl.trim()}>
                    Analyze →
                  </Button>
                </div>
              </>
            )}

            {modalState === "loading" && (
              <>
                <h2 className="text-lg font-semibold text-foreground">
                  Analyzing {productUrl}
                </h2>
                <div className="mt-4 space-y-3">
                  <div className="flex items-center gap-3 text-sm">
                    <Loader2 className="h-4 w-4 animate-spin text-primary" />
                    <span className="text-muted-foreground">
                      {!jobStatus || jobStatus.status === "pending"
                        ? "Starting analysis…"
                        : jobStatus.status === "running"
                        ? jobStatus.risks_identified
                          ? `Identified ${jobStatus.risks_identified} risks — creating watches…`
                          : "Scraping product page and analyzing regulations…"
                        : "Processing…"}
                    </span>
                  </div>
                  {jobStatus?.risks_identified && (
                    <p className="text-xs text-muted-foreground pl-7">
                      {jobStatus.risks_identified} compliance risks found so far
                    </p>
                  )}
                </div>
              </>
            )}

            {modalState === "done" && jobStatus && (
              <>
                <div className="flex items-center gap-2">
                  <CheckCircle className="h-5 w-5 text-primary" />
                  <h2 className="text-lg font-semibold text-foreground">Analysis complete</h2>
                </div>
                <div className="mt-3 space-y-1 text-sm text-muted-foreground">
                  <p>
                    <span className="font-medium text-foreground">{jobStatus.risks_identified ?? 0}</span> compliance risks identified
                  </p>
                  <p>
                    <span className="font-medium text-foreground">{jobStatus.watches_created ?? 0}</span> watches created
                  </p>
                  {jobStatus.product_info?.url && (
                    <p className="text-xs truncate">
                      Analyzed:{" "}
                      <span className="text-primary">{jobStatus.product_info.url}</span>
                    </p>
                  )}
                </div>
                <div className="mt-4 flex gap-2">
                  <Button onClick={goToWatches} className="flex-1">
                    View watches →
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
                  <h2 className="text-lg font-semibold text-foreground">Analysis failed</h2>
                </div>
                <p className="mt-2 text-sm text-muted-foreground">
                  {jobStatus?.error ?? "Something went wrong. Please try again."}
                </p>
                <div className="mt-4 flex gap-2">
                  <Button onClick={() => setModalState("input")} className="flex-1">
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
