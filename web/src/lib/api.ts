import type {
  AnomalyListResponse,
  GraphResponse,
  MetricSeriesResponse,
  PipelineListResponse,
  RunListResponse,
} from "@/types/pipeline";

const BASE = "/api";

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`);
  if (!res.ok) throw new Error(`API ${res.status}: ${path}`);
  return res.json() as Promise<T>;
}

export const api = {
  pipelines: () => get<PipelineListResponse>("/pipelines"),
  graph: (id: string) => get<GraphResponse>(`/pipelines/${id}/graph`),
  runs: (id: string) => get<RunListResponse>(`/pipelines/${id}/runs`),
  metrics: (nodeId: string, metric: string) =>
    get<MetricSeriesResponse>(`/nodes/${nodeId}/metrics?metric_name=${metric}`),
  anomalies: (pipelineId: string) =>
    get<AnomalyListResponse>(`/pipelines/${pipelineId}/anomalies`),
};

export function graphWsUrl(pipelineId: string): string {
  return `ws://localhost:8000/ws/pipelines/${pipelineId}/graph`;
}
