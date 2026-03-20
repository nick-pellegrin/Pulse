import { memo } from "react";
import { Handle, Position, type NodeProps } from "@xyflow/react";
import type { NodeState } from "@/types/pipeline";

export interface PipelineNodeData extends Record<string, unknown> {
  name: string;
  node_type: string;
  state: NodeState | "skipped";
  anomaly_count: number;
  last_run_at: string | null;
}

const STATE_LABELS: Record<string, string> = {
  healthy: "Healthy",
  failed: "Failed",
  running: "Running",
  drifting: "Drifting",
  stale: "Stale",
  skipped: "Skipped",
};

function formatRelativeTime(iso: string | null): string {
  if (!iso) return "never";
  const diff = Date.now() - new Date(iso).getTime();
  const m = Math.floor(diff / 60_000);
  if (m < 1) return "just now";
  if (m < 60) return `${m}m ago`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h}h ago`;
  return `${Math.floor(h / 24)}d ago`;
}

export const PipelineNode = memo(function PipelineNode({
  data,
  selected,
}: NodeProps) {
  const d = data as unknown as PipelineNodeData;
  return (
    <div
      className={`pipeline-node${selected ? " selected" : ""}`}
      data-state={d.state}
    >
      <Handle type="target" position={Position.Left} />
      <div className="pipeline-node__label">{STATE_LABELS[d.state] ?? d.state}</div>
      <div className="pipeline-node__name" title={d.name}>
        {d.name}
      </div>
      <div className="pipeline-node__meta">
        <span>{d.node_type}</span>
        <span>{formatRelativeTime(d.last_run_at)}</span>
        {d.anomaly_count > 0 && (
          <span className="pipeline-node__anomaly-badge">{d.anomaly_count}</span>
        )}
      </div>
      <Handle type="source" position={Position.Right} />
    </div>
  );
});
