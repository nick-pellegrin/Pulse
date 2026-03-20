// ── REST API types ─────────────────────────────────────────────────────────────

export interface PipelineSummary {
  id: string;
  name: string;
  slug: string;
  description: string | null;
  node_count: number;
  edge_count: number;
  healthy_count: number;
  failed_count: number;
  drifting_count: number;
  stale_count: number;
  running_count: number;
}

export interface PipelineListResponse {
  pipelines: PipelineSummary[];
}

export type NodeState = "healthy" | "failed" | "running" | "drifting" | "stale";

export interface NodeResponse {
  id: string;
  external_id: string;
  name: string;
  node_type: string;
  state: NodeState;
  position_x: number | null;
  position_y: number | null;
  last_run_at: string | null;
  last_run_status: string | null;
  anomaly_count: number;
}

export interface EdgeResponse {
  id: string;
  source_node_id: string;
  target_node_id: string;
}

export interface GraphResponse {
  pipeline_id: string;
  pipeline_name: string;
  nodes: NodeResponse[];
  edges: EdgeResponse[];
}

export interface PipelineRunResponse {
  id: string;
  pipeline_id: string;
  started_at: string;
  completed_at: string | null;
  status: string;
  triggered_by: string | null;
}

export interface RunListResponse {
  runs: PipelineRunResponse[];
}

export interface MetricPoint {
  ts: string;
  value: number;
}

export interface MetricSeriesResponse {
  node_id: string;
  metric_name: string;
  points: MetricPoint[];
}

export interface AnomalyResponse {
  id: string;
  node_id: string;
  node_name: string;
  pipeline_id: string;
  pipeline_name: string;
  metric_name: string;
  detected_at: string;
  severity: string;
  value: number;
  expected_value: number | null;
  description: string | null;
}

export interface AnomalyListResponse {
  anomalies: AnomalyResponse[];
  total: number;
}

// ── WebSocket message types ────────────────────────────────────────────────────

export interface WsNodeUpdate {
  id: string;
  state: NodeState | "skipped";
  last_run_at: string | null;
  last_run_status: string | null;
  anomaly_count: number;
}

export interface WsGraphSnapshot {
  type: "graph_snapshot";
  pipeline_id: string;
  pipeline_name: string;
  timestamp: string;
  nodes: NodeResponse[];
  edges: EdgeResponse[];
}

export interface WsGraphUpdate {
  type: "graph_update";
  pipeline_id: string;
  timestamp: string;
  nodes: WsNodeUpdate[];
}

export interface WsError {
  type: "error";
  detail: string;
}

export type WsMessage = WsGraphSnapshot | WsGraphUpdate | WsError;
