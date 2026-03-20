import { useQuery } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { api } from "@/lib/api";

const STATE_COLORS: Record<string, string> = {
  healthy: "var(--state-healthy)",
  failed: "var(--state-failed)",
  running: "var(--state-running)",
  drifting: "var(--state-drifting)",
  stale: "var(--state-stale)",
};

export function Home() {
  const navigate = useNavigate();
  const { data, isLoading } = useQuery({
    queryKey: ["pipelines"],
    queryFn: api.pipelines,
    staleTime: 30_000,
  });

  if (isLoading) {
    return (
      <div className="flex flex-1 items-center justify-center">
        <div className="h-8 w-8 rounded-full border-2 border-muted-foreground border-t-transparent animate-spin" />
      </div>
    );
  }

  return (
    <div className="flex flex-1 flex-col p-8 max-w-3xl mx-auto w-full">
      <h1 className="text-2xl font-semibold mb-6">Pipelines</h1>
      <div className="grid gap-4">
        {data?.pipelines.map((p) => {
          const hasIssues = p.failed_count > 0 || p.drifting_count > 0;
          const overallState = p.running_count > 0
            ? "running"
            : p.failed_count > 0
            ? "failed"
            : p.drifting_count > 0
            ? "drifting"
            : p.stale_count > 0
            ? "stale"
            : "healthy";

          return (
            <button
              key={p.id}
              className="text-left rounded-lg border border-border bg-card p-5 hover:bg-accent transition-colors"
              onClick={() => navigate(`/graph?pipeline=${p.id}`)}
            >
              <div className="flex items-start justify-between gap-4">
                <div>
                  <div className="font-medium">{p.name}</div>
                  {p.description && (
                    <div className="text-sm text-muted-foreground mt-0.5">{p.description}</div>
                  )}
                </div>
                <span
                  className="text-xs font-semibold uppercase tracking-wider shrink-0"
                  style={{ color: STATE_COLORS[overallState] }}
                >
                  {overallState}
                </span>
              </div>

              <div className="flex gap-4 mt-3 text-xs text-muted-foreground">
                <span>{p.node_count} nodes</span>
                {p.healthy_count > 0 && (
                  <span style={{ color: STATE_COLORS.healthy }}>{p.healthy_count} healthy</span>
                )}
                {p.failed_count > 0 && (
                  <span style={{ color: STATE_COLORS.failed }}>{p.failed_count} failed</span>
                )}
                {p.drifting_count > 0 && (
                  <span style={{ color: STATE_COLORS.drifting }}>{p.drifting_count} drifting</span>
                )}
                {p.stale_count > 0 && (
                  <span style={{ color: STATE_COLORS.stale }}>{p.stale_count} stale</span>
                )}
              </div>

              {hasIssues && (
                <div
                  className="mt-3 h-1 rounded-full bg-muted overflow-hidden"
                  title="Health bar"
                >
                  <div
                    className="h-full rounded-full"
                    style={{
                      width: `${(p.healthy_count / p.node_count) * 100}%`,
                      background: STATE_COLORS.healthy,
                    }}
                  />
                </div>
              )}
            </button>
          );
        })}
      </div>
    </div>
  );
}
