"use client";

import { useAnomalies, type Anomaly } from "@/lib/api";
import { Badge, Card, ErrorNote, LoadingRows } from "@/components/ui/Card";

const STATUS_TONE: Record<Anomaly["status"], "amber" | "blue" | "green" | "slate"> = {
  detected: "amber",
  diagnosed: "blue",
  alerted: "blue",
  resolved: "green",
};

export default function AnomalyFeed() {
  const { data, isLoading, error } = useAnomalies();

  return (
    <Card title="Billing Anomalies" subtitle="Cost spikes vs 7-day baseline (BigQuery)">
      {isLoading && <LoadingRows />}
      {error != null && <ErrorNote error={error} />}
      {data && data.length === 0 && (
        <p className="text-sm text-slate-400">No anomalies detected. Costs nominal.</p>
      )}
      {data && data.length > 0 && (
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead className="text-xs uppercase text-slate-400">
              <tr>
                <th className="pb-2 pr-4">Resource</th>
                <th className="pb-2 pr-4">Service</th>
                <th className="pb-2 pr-4 text-right">Spike</th>
                <th className="pb-2 pr-4 text-right">$/day</th>
                <th className="pb-2">Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {data.map((a, i) => (
                <tr key={`${a.resource_name}-${i}`}>
                  <td className="max-w-[220px] truncate py-2 pr-4 font-mono text-xs" title={a.resource_name}>
                    {a.resource_name}
                  </td>
                  <td className="py-2 pr-4">{a.service}</td>
                  <td className="py-2 pr-4 text-right font-semibold text-red-400">
                    +{a.spike_pct}%
                  </td>
                  <td className="py-2 pr-4 text-right tabular-nums">
                    {a.baseline_cost.toFixed(0)} → {a.current_cost.toFixed(0)}
                  </td>
                  <td className="py-2">
                    <Badge tone={STATUS_TONE[a.status] ?? "slate"}>{a.status}</Badge>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Card>
  );
}
