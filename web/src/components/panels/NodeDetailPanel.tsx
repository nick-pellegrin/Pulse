import { useQuery } from "@tanstack/react-query";
import { X } from "lucide-react";
import { api } from "@/lib/api";
import type { NodeResponse } from "@/types/pipeline";
import type { LiveNodeState } from "@/hooks/usePipelineSocket";
import { Button } from "@/components/ui/button";

interface NodeDetailPanelProps {
  node: NodeResponse | undefined;
  liveState: LiveNodeState | undefined;
  pipelineId: string;
  onClose: () => void;
}

const STATE_COLORS: Record<string, string> = {
  healthy: "var(--state-healthy)",
  failed: "var(--state-failed)",
  running: "var(--state-running)",
  drifting: "var(--state-drifting)",
  stale: "var(--state-stale)",
  skipped: "var(--state-skipped)",
};

function Sparkline({ points }: { points: { ts: string; value: number }[] }) {
  if (points.length < 2) return <span className="text-muted-foreground text-xs">No data</span>;

  const values = points.map((p) => p.value);
  const min = Math.min(...values);
  const max = Math.max(...values);
  const range = max - min || 1;
  const W = 160;
  const H = 36;
  const step = W / (points.length - 1);

  const d = points
    .map((p, i) => {
      const x = i * step;
      const y = H - ((p.value - min) / range) * H;
      return `${i === 0 ? "M" : "L"}${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(" ");

  return (
    <svg width={W} height={H} viewBox={`0 0 ${W} ${H}`} className="overflow-visible">
      <path d={d} fill="none" stroke="var(--state-running)" strokeWidth={1.5} />
    </svg>
  );
}

function MetricRow({ nodeId, metricName }: { nodeId: string; metricName: string }) {
  const { data, isLoading } = useQuery({
    queryKey: ["metrics", nodeId, metricName],
    queryFn: () => api.metrics(nodeId, metricName),
    staleTime: 60_000,
  });

  return (
    <div>
      <div className="text-xs text-muted-foreground mb-1">{metricName}</div>
      {isLoading ? (
        <div className="h-9 bg-muted rounded animate-pulse" />
      ) : data?.points.length ? (
        <Sparkline points={data.points} />
      ) : (
        <span className="text-xs text-muted-foreground">No data</span>
      )}
    </div>
  );
}

const METRIC_NAMES = ["row_count", "duration_ms", "null_rate"] as const;

export function NodeDetailPanel({ node, liveState, pipelineId, onClose }: NodeDetailPanelProps) {
  const state = liveState?.state ?? node?.state ?? "healthy";
  const anomalyCount = liveState?.anomaly_count ?? node?.anomaly_count ?? 0;
  const lastRunAt = liveState?.last_run_at ?? node?.last_run_at ?? null;
  const lastRunStatus = liveState?.last_run_status ?? node?.last_run_status ?? null;

  const { data: anomaliesData } = useQuery({
    queryKey: ["anomalies", pipelineId],
    queryFn: () => api.anomalies(pipelineId),
    enabled: !!pipelineId,
    staleTime: 30_000,
  });

  const nodeAnomalies = anomaliesData?.anomalies.filter((a) => a.node_id === node?.id) ?? [];

  if (!node) return null;

  return (
    <div
      className="absolute right-0 top-0 bottom-0 w-80 bg-card border-l border-border flex flex-col z-10 overflow-hidden"
      style={{ boxShadow: "-4px 0 20px rgba(0,0,0,0.3)" }}
    >
      {/* Header */}
      <div className="flex items-start justify-between p-4 border-b border-border">
        <div className="flex-1 min-w-0">
          <div
            className="text-xs font-semibold uppercase tracking-wider mb-1"
            style={{ color: STATE_COLORS[state] }}
          >
            {state}
          </div>
          <div className="font-medium text-sm truncate" title={node.name}>
            {node.name}
          </div>
          <div className="text-xs text-muted-foreground mt-0.5">{node.node_type}</div>
        </div>
        <Button variant="ghost" size="icon" className="h-7 w-7 ml-2 shrink-0" onClick={onClose}>
          <X className="h-4 w-4" />
        </Button>
      </div>

      <div className="flex-1 overflow-y-auto p-4 space-y-5">
        {/* Last run info */}
        <section>
          <h3 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-2">
            Last Run
          </h3>
          <div className="text-sm space-y-1">
            <div className="flex justify-between">
              <span className="text-muted-foreground">Status</span>
              <span>{lastRunStatus ?? "—"}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-muted-foreground">At</span>
              <span>
                {lastRunAt ? new Date(lastRunAt).toLocaleString() : "—"}
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-muted-foreground">Anomalies</span>
              <span style={anomalyCount > 0 ? { color: STATE_COLORS.failed } : {}}>
                {anomalyCount}
              </span>
            </div>
          </div>
        </section>

        {/* Metrics sparklines */}
        <section>
          <h3 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-3">
            Metrics (30d)
          </h3>
          <div className="space-y-4">
            {METRIC_NAMES.map((name) => (
              <MetricRow key={name} nodeId={node.id} metricName={name} />
            ))}
          </div>
        </section>

        {/* Anomalies */}
        {nodeAnomalies.length > 0 && (
          <section>
            <h3 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-2">
              Recent Anomalies
            </h3>
            <div className="space-y-2">
              {nodeAnomalies.slice(0, 5).map((a) => (
                <div
                  key={a.id}
                  className="text-xs rounded p-2 border border-border"
                  style={{ background: STATE_COLORS.failed + "15" }}
                >
                  <div className="font-medium">{a.metric_name}</div>
                  <div className="text-muted-foreground">
                    {a.description ?? `value ${a.value.toFixed(2)}`}
                  </div>
                  <div className="text-muted-foreground mt-0.5">
                    {new Date(a.detected_at).toLocaleString()}
                  </div>
                </div>
              ))}
            </div>
          </section>
        )}
      </div>
    </div>
  );
}
