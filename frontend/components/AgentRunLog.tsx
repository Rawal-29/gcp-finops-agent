"use client";

import { formatTimestamp, useAgentRuns, type AgentRun } from "@/lib/api";
import { Badge, Card, ErrorNote, LoadingRows } from "@/components/ui/Card";

const STATUS_TONE: Record<AgentRun["status"], "blue" | "green" | "red" | "slate"> = {
  running: "blue",
  completed: "green",
  failed: "red",
  no_anomalies: "slate",
};

const NODE_LABELS: Record<string, string> = {
  detect_anomaly: "Detect",
  query_rag: "RAG",
  inspect_resource: "Inspect",
  generate_plan: "Plan",
  alert: "Alert",
};

export default function AgentRunLog() {
  const { data, isLoading, error } = useAgentRuns();

  return (
    <Card title="Agent Runs" subtitle="LangGraph decision timeline (Firestore)">
      {isLoading && <LoadingRows />}
      {error != null && <ErrorNote error={error} />}
      {data && (
        <ul className="space-y-4">
          {data.map((run) => (
            <li key={run.id} className="rounded-lg border border-border p-3">
              <div className="mb-2 flex items-center justify-between">
                <span className="font-mono text-xs text-slate-400">{run.id}</span>
                <div className="flex items-center gap-2">
                  {typeof run.confidence === "number" && run.confidence > 0 && (
                    <span className="text-xs text-slate-400">
                      conf {(run.confidence * 100).toFixed(0)}%
                    </span>
                  )}
                  <Badge tone={STATUS_TONE[run.status] ?? "slate"}>{run.status}</Badge>
                </div>
              </div>
              <div className="flex flex-wrap items-center gap-1">
                {(run.steps ?? []).map((s, i) => (
                  <span key={i} className="flex items-center gap-1">
                    <span className="rounded bg-slate-700/40 px-2 py-0.5 text-xs">
                      {NODE_LABELS[s.node] ?? s.node}
                    </span>
                    {i < run.steps.length - 1 && (
                      <span className="text-slate-500">→</span>
                    )}
                  </span>
                ))}
              </div>
              {run.plan?.diagnosis && (
                <p className="mt-2 line-clamp-2 text-xs text-slate-300">
                  {run.plan.diagnosis}
                </p>
              )}
              <p className="mt-1 text-xs text-slate-500">
                {formatTimestamp(run.started_at)}
              </p>
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}
