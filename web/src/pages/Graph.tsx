import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useSearchParams } from "react-router-dom";
import { api } from "@/lib/api";
import { usePipelineSocket } from "@/hooks/usePipelineSocket";
import { useGraphStore } from "@/store/graphStore";
import { PipelineGraph } from "@/components/graph/PipelineGraph";
import { NodeDetailPanel } from "@/components/panels/NodeDetailPanel";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

const STATUS_DOT: Record<string, string> = {
  open: "bg-green-500",
  connecting: "bg-yellow-500 animate-pulse",
  closed: "bg-muted-foreground",
  error: "bg-red-500",
};

export function Graph() {
  const [searchParams] = useSearchParams();
  const [selectedPipelineId, setSelectedPipelineId] = useState<string | null>(
    searchParams.get("pipeline")
  );

  const { data: pipelineList, isLoading: pipelinesLoading } = useQuery({
    queryKey: ["pipelines"],
    queryFn: api.pipelines,
    staleTime: 60_000,
  });

  // Fetch graph via REST (primary data source)
  const { data: graphData, isLoading: graphLoading } = useQuery({
    queryKey: ["graph", selectedPipelineId],
    queryFn: () => api.graph(selectedPipelineId!),
    enabled: !!selectedPipelineId,
    staleTime: 30_000,
  });

  // WebSocket for live updates (optional — graph loads without it)
  const { liveStates, status: wsStatus } = usePipelineSocket(selectedPipelineId);

  const { selectedNodeId, isPanelOpen, closePanel } = useGraphStore();

  const nodes = graphData?.nodes ?? [];
  const edges = graphData?.edges ?? [];

  const selectedNode = nodes.find((n) => n.id === selectedNodeId);
  const liveSelectedState = selectedNodeId ? liveStates[selectedNodeId] : undefined;

  function handlePipelineChange(id: string) {
    closePanel();
    setSelectedPipelineId(id);
  }

  return (
    <div className="flex flex-col h-full w-full">
      {/* Toolbar */}
      <div className="flex items-center gap-4 px-4 py-3 border-b border-border shrink-0">
        <div className="w-64">
          {pipelinesLoading ? (
            <div className="h-9 rounded-md bg-muted animate-pulse" />
          ) : (
            <Select
              value={selectedPipelineId ?? ""}
              onValueChange={handlePipelineChange}
            >
              <SelectTrigger>
                <SelectValue placeholder="Select a pipeline..." />
              </SelectTrigger>
              <SelectContent>
                {pipelineList?.pipelines.map((p) => (
                  <SelectItem key={p.id} value={p.id}>
                    {p.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          )}
        </div>

        {selectedPipelineId && (
          <div className="flex items-center gap-2 text-xs text-muted-foreground">
            <span className={`h-2 w-2 rounded-full ${STATUS_DOT[wsStatus] ?? "bg-gray-500"}`} />
            <span>Live {wsStatus === "open" ? "connected" : wsStatus}</span>
          </div>
        )}

        {selectedPipelineId && nodes.length > 0 && (
          <div className="flex gap-3 text-xs text-muted-foreground ml-auto">
            {(["healthy", "failed", "running", "drifting", "stale"] as const).map((s) => {
              const count = nodes.filter((n) => {
                const live = liveStates[n.id];
                return (live?.state ?? n.state) === s;
              }).length;
              if (count === 0) return null;
              const colors: Record<string, string> = {
                healthy: "var(--state-healthy)",
                failed: "var(--state-failed)",
                running: "var(--state-running)",
                drifting: "var(--state-drifting)",
                stale: "var(--state-stale)",
              };
              return (
                <span key={s} style={{ color: colors[s] }}>
                  {count} {s}
                </span>
              );
            })}
          </div>
        )}
      </div>

      {/* Graph canvas */}
      <div className="flex-1 relative overflow-hidden">
        {!selectedPipelineId ? (
          <div className="flex items-center justify-center h-full text-muted-foreground">
            Select a pipeline to view the graph
          </div>
        ) : graphLoading ? (
          <div className="flex items-center justify-center h-full text-muted-foreground">
            <div className="h-8 w-8 rounded-full border-2 border-current border-t-transparent animate-spin mr-3" />
            Loading...
          </div>
        ) : nodes.length > 0 ? (
          <PipelineGraph apiNodes={nodes} apiEdges={edges} liveStates={liveStates} />
        ) : (
          <div className="flex items-center justify-center h-full text-muted-foreground">
            No nodes in this pipeline
          </div>
        )}

        {isPanelOpen && selectedNode && selectedPipelineId && (
          <NodeDetailPanel
            node={selectedNode}
            liveState={liveSelectedState}
            pipelineId={selectedPipelineId}
            onClose={closePanel}
          />
        )}
      </div>
    </div>
  );
}
