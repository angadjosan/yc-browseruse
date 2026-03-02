"use client";

import { useEffect, useRef, useState } from "react";
import useSWR from "swr";
import { api } from "./api";
import type { Run, RunStep } from "./types";

const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

/**
 * Combines SWR polling with SSE streaming for real-time run updates.
 * SSE gives sub-second step updates; SWR provides full data on completion.
 * Falls back to polling-only if SSE connection fails.
 */
export function useRunStream(runId: string | undefined) {
  const [sseSteps, setSseSteps] = useState<RunStep[]>([]);
  const [sseStatus, setSseStatus] = useState<string | null>(null);
  const [isStreaming, setIsStreaming] = useState(false);
  const esRef = useRef<EventSource | null>(null);

  const {
    data: run,
    error,
    isLoading,
    mutate,
  } = useSWR(
    runId ? `run/${runId}` : null,
    () => api.runs.get(runId!),
    {
      refreshInterval: (data) => {
        if (!data || data.status === "running") {
          return isStreaming ? 8_000 : 2_000;
        }
        return 0;
      },
      errorRetryCount: 10,
      errorRetryInterval: 2000,
      shouldRetryOnError: true,
    }
  );

  const shouldStream =
    !!runId && (run?.status === "running" || (!run && !error));

  useEffect(() => {
    if (!shouldStream || !runId) {
      if (esRef.current) {
        esRef.current.close();
        esRef.current = null;
        setIsStreaming(false);
      }
      return;
    }

    if (esRef.current) return;

    const es = new EventSource(`${BASE}/api/runs/${runId}/stream`);
    esRef.current = es;

    es.onopen = () => setIsStreaming(true);

    es.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data.error) {
          es.close();
          esRef.current = null;
          setIsStreaming(false);
          return;
        }
        if (data.steps) setSseSteps(data.steps);
        if (data.status) setSseStatus(data.status);
        if (data.status === "completed" || data.status === "failed") {
          es.close();
          esRef.current = null;
          setIsStreaming(false);
          mutate();
        }
      } catch {
        // ignore parse errors
      }
    };

    es.onerror = () => {
      setIsStreaming(false);
      es.close();
      esRef.current = null;
    };

    return () => {
      es.close();
      esRef.current = null;
      setIsStreaming(false);
    };
  }, [shouldStream, runId, mutate]);

  // Reset SSE state when runId changes
  useEffect(() => {
    setSseSteps([]);
    setSseStatus(null);
  }, [runId]);

  const mergedRun: Run | undefined = run
    ? {
        ...run,
        steps:
          sseSteps.length > 0 && run.status === "running"
            ? sseSteps
            : run.steps,
        status:
          sseStatus && run.status === "running"
            ? (sseStatus as Run["status"])
            : run.status,
      }
    : undefined;

  return {
    run: mergedRun,
    error,
    isLoading,
    isStreaming,
    mutate,
  };
}
