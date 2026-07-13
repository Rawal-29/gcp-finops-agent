"use client";

import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { useEvals } from "@/lib/api";
import { Card, ErrorNote, LoadingRows } from "@/components/ui/Card";

export default function EvalScoreChart() {
  const { data, isLoading, error } = useEvals();

  const chartData = (data ?? [])
    .slice()
    .reverse()
    .map((e) => ({
      sha: e.git_sha.slice(0, 7),
      Faithfulness: e.faithfulness,
      "Answer Relevancy": e.answer_relevancy,
      "Context Recall": e.context_recall,
    }));

  return (
    <Card title="RAGAS Eval Scores" subtitle="Per-commit quality trend (BigQuery)">
      {isLoading && <LoadingRows />}
      {error != null && <ErrorNote error={error} />}
      {chartData.length > 0 && (
        <ResponsiveContainer width="100%" height={260}>
          <LineChart data={chartData} margin={{ top: 5, right: 10, bottom: 0, left: -20 }}>
            <CartesianGrid stroke="#1e2a44" strokeDasharray="3 3" />
            <XAxis dataKey="sha" stroke="#64748b" fontSize={11} />
            <YAxis domain={[0.5, 1]} stroke="#64748b" fontSize={11} />
            <Tooltip
              contentStyle={{ background: "#111a2e", border: "1px solid #1e2a44", fontSize: 12 }}
            />
            <Legend wrapperStyle={{ fontSize: 12 }} />
            <ReferenceLine y={0.85} stroke="#ef4444" strokeDasharray="4 4" label="" />
            <Line type="monotone" dataKey="Faithfulness" stroke="#34d399" dot={false} strokeWidth={2} />
            <Line type="monotone" dataKey="Answer Relevancy" stroke="#38bdf8" dot={false} strokeWidth={2} />
            <Line type="monotone" dataKey="Context Recall" stroke="#fbbf24" dot={false} strokeWidth={2} />
          </LineChart>
        </ResponsiveContainer>
      )}
      {data && data.length === 0 && (
        <p className="text-sm text-slate-400">No eval runs logged yet.</p>
      )}
    </Card>
  );
}
