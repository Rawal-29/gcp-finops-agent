"use client";

import { formatTimestamp, useAgentRuns } from "@/lib/api";
import { Badge, Card, ErrorNote, LoadingRows } from "@/components/ui/Card";

export default function AlertHistory() {
  const { data, isLoading, error } = useAgentRuns();
  const alerted = (data ?? []).filter((r) => r.alert_sent);

  return (
    <Card title="Alert History" subtitle="Slack alerts sent with remediation plans">
      {isLoading && <LoadingRows />}
      {error != null && <ErrorNote error={error} />}
      {data && alerted.length === 0 && (
        <p className="text-sm text-slate-400">No alerts sent yet.</p>
      )}
      {alerted.length > 0 && (
        <ul className="space-y-3">
          {alerted.map((run) => (
            <li key={run.id} className="rounded-lg border border-border p-3">
              <div className="flex items-center justify-between">
                <span className="text-sm font-medium">
                  {run.anomaly?.service ?? "?"} · {run.anomaly?.resource_name ?? "?"}
                </span>
                <Badge tone="green">sent</Badge>
              </div>
              {run.plan && (
                <>
                  <p className="mt-1 text-xs text-slate-300">{run.plan.diagnosis}</p>
                  <p className="mt-1 text-xs text-slate-400">
                    Est. savings ${run.plan.est_monthly_savings.toLocaleString()}/mo ·{" "}
                    {run.plan.remediation_steps.length} steps
                  </p>
                </>
              )}
              <p className="mt-1 text-xs text-slate-500">{formatTimestamp(run.started_at)}</p>
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}
