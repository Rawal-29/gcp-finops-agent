import AnomalyFeed from "@/components/AnomalyFeed";
import AgentRunLog from "@/components/AgentRunLog";
import EvalScoreChart from "@/components/EvalScoreChart";
import AlertHistory from "@/components/AlertHistory";

export default function DashboardPage() {
  return (
    <main className="mx-auto max-w-7xl space-y-6 p-6">
      <header className="flex items-baseline justify-between">
        <h1 className="text-2xl font-semibold tracking-tight">
          FinOps Intelligence
        </h1>
        <span className="text-sm text-slate-400">
          GCP cost anomalies · autonomous remediation
        </span>
      </header>

      <div className="grid grid-cols-1 gap-6 xl:grid-cols-2">
        <AnomalyFeed />
        <EvalScoreChart />
      </div>
      <div className="grid grid-cols-1 gap-6 xl:grid-cols-2">
        <AgentRunLog />
        <AlertHistory />
      </div>
    </main>
  );
}
