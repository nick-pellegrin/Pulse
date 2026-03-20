import "@xyflow/react/dist/style.css";
import { useCallback, useEffect, useMemo } from "react";
import {
  Background,
  Controls,
  MiniMap,
  ReactFlow,
  addEdge,
  useEdgesState,
  useNodesState,
  type Node,
  type Edge,
  type Connection,
  MarkerType,
} from "@xyflow/react";
import dagre from "@dagrejs/dagre";
import type { EdgeResponse, NodeResponse } from "@/types/pipeline";
import type { LiveNodeState } from "@/hooks/usePipelineSocket";
import { type PipelineNodeData, PipelineNode } from "./nodes/PipelineNode";
import { useGraphStore } from "@/store/graphStore";

const NODE_WIDTH = 180;
const NODE_HEIGHT = 70;

const nodeTypes = { pipelineNode: PipelineNode };

function buildLayout(
  apiNodes: NodeResponse[],
  apiEdges: EdgeResponse[],
  liveStates: Record<string, LiveNodeState>
): { nodes: Node[]; edges: Edge[] } {
  const g = new dagre.graphlib.Graph();
  g.setDefaultEdgeLabel(() => ({}));
  g.setGraph({ rankdir: "LR", nodesep: 40, ranksep: 60 });

  for (const n of apiNodes) {
    g.setNode(n.id, { width: NODE_WIDTH, height: NODE_HEIGHT });
  }
  for (const e of apiEdges) {
    g.setEdge(e.source_node_id, e.target_node_id);
  }
  dagre.layout(g);

  const nodes: Node[] = apiNodes.map((n) => {
    const live = liveStates[n.id];
    const pos = g.node(n.id);
    const data: PipelineNodeData = {
      name: n.name,
      node_type: n.node_type,
      state: live?.state ?? n.state,
      anomaly_count: live?.anomaly_count ?? n.anomaly_count,
      last_run_at: live?.last_run_at ?? n.last_run_at,
    };
    return {
      id: n.id,
      type: "pipelineNode",
      position: { x: pos.x - NODE_WIDTH / 2, y: pos.y - NODE_HEIGHT / 2 },
      data,
    };
  });

  const edges: Edge[] = apiEdges.map((e) => ({
    id: e.id,
    source: e.source_node_id,
    target: e.target_node_id,
    type: "smoothstep",
    animated: true,
    markerEnd: { type: MarkerType.ArrowClosed },
  }));

  return { nodes, edges };
}

interface PipelineGraphProps {
  apiNodes: NodeResponse[];
  apiEdges: EdgeResponse[];
  liveStates: Record<string, LiveNodeState>;
}

export function PipelineGraph({ apiNodes, apiEdges, liveStates }: PipelineGraphProps) {
  const setSelectedNode = useGraphStore((s) => s.setSelectedNode);

  const { nodes: layoutNodes, edges: layoutEdges } = useMemo(
    () => buildLayout(apiNodes, apiEdges, liveStates),
    [apiNodes, apiEdges, liveStates]
  );

  const [nodes, setNodes, onNodesChange] = useNodesState(layoutNodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(layoutEdges);

  // Sync layout changes (live state updates) without resetting positions
  useEffect(() => {
    setNodes((prev) => {
      const posMap: Record<string, { x: number; y: number }> = {};
      for (const n of prev) posMap[n.id] = n.position;

      return layoutNodes.map((n) => ({
        ...n,
        position: posMap[n.id] ?? n.position,
      }));
    });
    setEdges(layoutEdges);
  }, [layoutNodes, layoutEdges, setNodes, setEdges]);

  const onConnect = useCallback(
    (connection: Connection) => setEdges((eds) => addEdge(connection, eds)),
    [setEdges]
  );

  const onNodeClick = useCallback(
    (_: React.MouseEvent, node: Node) => {
      setSelectedNode(node.id);
    },
    [setSelectedNode]
  );

  return (
    <div style={{ width: "100%", height: "100%" }}>
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onConnect={onConnect}
        onNodeClick={onNodeClick}
        nodeTypes={nodeTypes}
        fitView
        fitViewOptions={{ padding: 0.2 }}
        minZoom={0.2}
        maxZoom={2}
        colorMode="dark"
      >
        <Background gap={20} size={1} />
        <Controls />
        <MiniMap nodeColor={(n) => {
          const state = (n.data as unknown as PipelineNodeData).state;
          const colorMap: Record<string, string> = {
            healthy: "#788c5d",
            failed: "#bf4d43",
            running: "#6a9bcc",
            drifting: "#d4a27f",
            stale: "#b0aea5",
            skipped: "#888",
          };
          return colorMap[state] ?? "#555";
        }} />
      </ReactFlow>
    </div>
  );
}
