import { useCallback, useEffect, useRef, useState } from "react";
import type { NodeState, WsMessage } from "@/types/pipeline";
import { graphWsUrl } from "@/lib/api";

export type WsStatus = "connecting" | "open" | "closed" | "error";

export interface LiveNodeState {
  state: NodeState | "skipped";
  last_run_at: string | null;
  last_run_status: string | null;
  anomaly_count: number;
}

interface SocketResult {
  liveStates: Record<string, LiveNodeState>;
  status: WsStatus;
}

const INITIAL_BACKOFF_MS = 1_000;
const MAX_BACKOFF_MS = 30_000;

export function usePipelineSocket(pipelineId: string | null): SocketResult {
  const [liveStates, setLiveStates] = useState<Record<string, LiveNodeState>>({});
  const [status, setStatus] = useState<WsStatus>("closed");

  const wsRef = useRef<WebSocket | null>(null);
  const backoffRef = useRef(INITIAL_BACKOFF_MS);
  const retryTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const mountedRef = useRef(true);

  const connect = useCallback(() => {
    if (!pipelineId || !mountedRef.current) return;

    const ws = new WebSocket(graphWsUrl(pipelineId));
    wsRef.current = ws;
    setStatus("connecting");

    ws.onopen = () => {
      if (!mountedRef.current) return;
      backoffRef.current = INITIAL_BACKOFF_MS;
      setStatus("open");
    };

    ws.onmessage = (event: MessageEvent) => {
      if (!mountedRef.current) return;
      const msg = JSON.parse(event.data as string) as WsMessage;

      if (msg.type === "graph_update") {
        setLiveStates((prev) => {
          const next = { ...prev };
          for (const n of msg.nodes) {
            next[n.id] = {
              state: n.state,
              last_run_at: n.last_run_at,
              last_run_status: n.last_run_status,
              anomaly_count: n.anomaly_count,
            };
          }
          return next;
        });
      }
      // graph_snapshot from WS is ignored — REST provides initial data
    };

    ws.onerror = () => {
      if (!mountedRef.current) return;
      setStatus("error");
    };

    ws.onclose = () => {
      if (!mountedRef.current) return;
      setStatus("closed");
      retryTimerRef.current = setTimeout(() => {
        backoffRef.current = Math.min(backoffRef.current * 2, MAX_BACKOFF_MS);
        connect();
      }, backoffRef.current);
    };
  }, [pipelineId]);

  useEffect(() => {
    mountedRef.current = true;
    setLiveStates({});
    connect();

    return () => {
      mountedRef.current = false;
      if (retryTimerRef.current) clearTimeout(retryTimerRef.current);
      wsRef.current?.close();
    };
  }, [connect]);

  return { liveStates, status };
}
