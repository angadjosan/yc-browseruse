"use client";

import { useEffect, useRef, useState } from "react";
import useSWR from "swr";
import { api } from "./api";
import { getAccessToken } from "./supabase";
import type { Run, RunStep } from "./types";

const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

/**
 * Combines SWR polling with SSE streaming for real-time run updates.
 * Uses fetch + ReadableStream (instead of EventSource) so auth headers are sent.
 * Falls back to polling-only if the stream connection fails.
 */
export function useRunStream(runId: string | undefined) {
  const [sseSteps, setSseSteps] = useState<RunStep[]>([]);
  const [sseStatus, setSseStatus] = useState<string | null>(null);
  const [isStreaming, setIsStreaming] = useState(false);
  const abortRef = useRef<AbortController | null>(null);

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
      if (abortRef.current) {
        abortRef.current.abort();
        abortRef.current = null;
        setIsStreaming(false);
      }
      return;
    }

    if (abortRef.current) return;

    const controller = new AbortController();
    abortRef.current = controller;

    (async () => {
      try {
        const token = await getAccessToken();
        const headers: Record<string, string> = {};
        if (token) {
          headers["Authorization"] = `Bearer ${token}`;
        }

        const res = await fetch(`${BASE}/api/runs/${runId}/stream`, {
          headers,
          signal: controller.signal,
        });

        if (!res.ok || !res.body) {
          setIsStreaming(false);
          abortRef.current = null;
          return;
        }

        setIsStreaming(true);

        const reader = res.body.getReader();
        const decoder = new TextDecoder();
        let buffer = "";

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          buffer += decoder.decode(value, { stream: true });

          // Parse SSE frames: lines starting with "data: "
          const lines = buffer.split("\n");
          // Keep the last incomplete line in the buffer
          buffer = lines.pop() ?? "";

          for (const line of lines) {
            if (!line.startsWith("data: ")) continue;
            try {
              const data = JSON.parse(line.slice(6));
              if (data.error) {
                reader.cancel();
                abortRef.current = null;
                setIsStreaming(false);
                return;
              }
              if (data.steps) setSseSteps(data.steps);
              if (data.status) setSseStatus(data.status);
              if (data.status === "completed" || data.status === "failed") {
                reader.cancel();
                abortRef.current = null;
                setIsStreaming(false);
                mutate();
                return;
              }
            } catch {
              // ignore parse errors
            }
          }
        }
      } catch (err: unknown) {
        if (err instanceof DOMException && err.name === "AbortError") return;
        // Stream failed — fall back to polling
      } finally {
        setIsStreaming(false);
        abortRef.current = null;
      }
    })();

    return () => {
      controller.abort();
      abortRef.current = null;
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
