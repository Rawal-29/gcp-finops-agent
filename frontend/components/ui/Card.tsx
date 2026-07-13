import { clsx } from "clsx";

export function Card({
  title,
  subtitle,
  children,
  className,
}: {
  title: string;
  subtitle?: string;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <section
      className={clsx(
        "rounded-xl border border-border bg-card p-5 shadow-lg",
        className
      )}
    >
      <div className="mb-4">
        <h2 className="text-base font-semibold text-slate-100">{title}</h2>
        {subtitle && <p className="text-xs text-slate-400">{subtitle}</p>}
      </div>
      {children}
    </section>
  );
}

export function Badge({
  tone,
  children,
}: {
  tone: "green" | "amber" | "red" | "slate" | "blue";
  children: React.ReactNode;
}) {
  const tones: Record<string, string> = {
    green: "bg-emerald-500/15 text-emerald-400",
    amber: "bg-amber-500/15 text-amber-400",
    red: "bg-red-500/15 text-red-400",
    slate: "bg-slate-500/15 text-slate-300",
    blue: "bg-sky-500/15 text-sky-400",
  };
  return (
    <span className={clsx("rounded-full px-2 py-0.5 text-xs font-medium", tones[tone])}>
      {children}
    </span>
  );
}

export function LoadingRows() {
  return (
    <div className="space-y-2">
      {[...Array(4)].map((_, i) => (
        <div key={i} className="h-8 animate-pulse rounded bg-slate-700/30" />
      ))}
    </div>
  );
}

export function ErrorNote({ error }: { error: unknown }) {
  return (
    <p className="rounded border border-red-500/30 bg-red-500/10 p-3 text-sm text-red-300">
      Failed to load: {error instanceof Error ? error.message : String(error)}
    </p>
  );
}
