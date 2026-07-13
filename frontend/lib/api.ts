"use client";

import { useQuery } from "@tanstack/react-query";

// All browser requests go through the same-origin Next.js proxy
// (app/api/proxy/[...path]/route.ts), which attaches the API key server-side.
const API_BASE = "/api/proxy";

// ---------- FastAPI response schemas ----------
export interface Anomaly {
  detected_at: string;
  project_id: string;
  service: string;
  resource_name: string;
  baseline_cost: number;
  current_cost: number;
  spike_pct: number;
  status: "detected" | "diagnosed" | "alerted" | "resolved";
}

export interface AgentStep {
  node: string;
  at: string;
  summary: Record<string, unknown>;
}

export interface AgentRun {
  id: string;
  started_at: { _seconds?: number } | string;
  finished_at?: { _seconds?: number } | string;
  status: "running" | "completed" | "failed" | "no_anomalies";
  anomaly: Partial<Anomaly>;
  steps: AgentStep[];
  plan?: {
    diagnosis: string;
    remediation_steps: string[];
    est_monthly_savings: number;
    confidence: number;
  };
  confidence?: number;
  alert_sent?: boolean;
}

export interface EvalResult {
  run_at: string;
  git_sha: string;
  faithfulness: number;
  answer_relevancy: number;
  context_recall: number;
  passed: boolean;
}

// ---------- fetch helper ----------
async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, { cache: "no-store" });
  if (!res.ok) throw new Error(`${path} → ${res.status} ${res.statusText}`);
  return res.json() as Promise<T>;
}

// ---------- React Query hooks ----------
const REFETCH_MS = 30_000;

export function useAnomalies() {
  return useQuery<Anomaly[]>({
    queryKey: ["anomalies"],
    queryFn: () => get<Anomaly[]>("/anomalies"),
    refetchInterval: REFETCH_MS,
  });
}

export function useAgentRuns() {
  return useQuery<AgentRun[]>({
    queryKey: ["agent-runs"],
    queryFn: () => get<AgentRun[]>("/agent/runs"),
    refetchInterval: REFETCH_MS,
  });
}

export function useEvals() {
  return useQuery<EvalResult[]>({
    queryKey: ["evals"],
    queryFn: () => get<EvalResult[]>("/evals"),
    refetchInterval: 5 * 60_000,
  });
}

export function formatTimestamp(t: AgentRun["started_at"]): string {
  if (typeof t === "string") return new Date(t).toLocaleString();
  if (t && typeof t === "object" && t._seconds) return new Date(t._seconds * 1000).toLocaleString();
  return "—";
}
