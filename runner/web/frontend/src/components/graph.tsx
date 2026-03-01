import { Badge } from "@/components/ui/badge"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import type { LayerInfo, ProjectDetail, TaskInfo } from "@/lib/api"
import {
  Background,
  type Edge,
  type Node,
  ReactFlow,
  ReactFlowProvider,
} from "@xyflow/react"
import "@xyflow/react/dist/style.css"
import { useMemo } from "react"

const NODE_WIDTH = 200;
const NODE_GAP_X = 40;
const LAYER_HEIGHT = 120;

const STATUS_COLORS: Record<string, { bg: string; border: string; text: string }> = {
  done: { bg: "#16a34a", border: "#15803d", text: "#ffffff" },
  ready: { bg: "#ca8a04", border: "#a16207", text: "#ffffff" },
  blocked: { bg: "#475569", border: "#334155", text: "#94a3b8" },
};

function getNodeColors(task: TaskInfo) {
  if (task.agent === "milestone") {
    if (task.status === "done") return { bg: "#7e22ce", border: "#6b21a8", text: "#ffffff" };
    if (task.status === "ready") return { bg: "#a855f7", border: "#9333ea", text: "#ffffff" };
    return { bg: "#3b0764", border: "#2e1065", text: "#e9d5ff" };
  }
  return STATUS_COLORS[task.status] ?? STATUS_COLORS.blocked;
}

/**
 * Build node positions directly from the authoritative layer data returned by
 * the Python backend (`get_task_layers`).  Layer index maps 1:1 to Y position
 * so the visual order always matches the topological order — no auto-layout
 * library is involved, which eliminates any risk of rank mis-ordering.
 *
 * Within each layer, tasks are distributed evenly and centred horizontally.
 */
function buildLayout(tasks: TaskInfo[], layers: LayerInfo[]): { nodes: Node[]; edges: Edge[] } {
  const taskById = new Map(tasks.map((t) => [String(t.id), t]));

  const nodes: Node[] = [];
  for (const layer of layers) {
    // Normalise the zero-padded IDs coming from the API ("001" → "1").
    const ids = layer.tasks.map((s) => String(parseInt(s, 10)));
    const count = ids.length;
    const totalWidth = count * NODE_WIDTH + (count - 1) * NODE_GAP_X;
    const startX = -totalWidth / 2;

    ids.forEach((id, i) => {
      const task = taskById.get(id);
      if (!task) return;
      const colors = getNodeColors(task);
      nodes.push({
        id,
        position: {
          x: startX + i * (NODE_WIDTH + NODE_GAP_X),
          y: layer.index * LAYER_HEIGHT,
        },
        data: { label: `${task.id}. ${task.title}` },
        style: {
          background: colors.bg,
          border: `2px solid ${colors.border}`,
          color: colors.text,
          borderRadius: 8,
          padding: "8px 12px",
          fontSize: 13,
          fontWeight: 500,
          width: NODE_WIDTH,
          textAlign: "center" as const,
        },
        draggable: true,
      });
    });
  }

  const edges: Edge[] = [];
  for (const task of tasks) {
    for (const dep of task.deps) {
      const sourceId = String(parseInt(dep, 10));
      const targetId = String(task.id);
      edges.push({
        id: `e${sourceId}-${targetId}`,
        source: sourceId,
        target: targetId,
        style: { stroke: "#64748b", strokeWidth: 2 },
        animated: task.status === "ready",
      });
    }
  }

  return { nodes, edges };
}

function GraphInner({ project }: { project: ProjectDetail }) {
  const { nodes, edges } = useMemo(
    () => buildLayout(project.tasks, project.layers),
    [project.tasks, project.layers],
  );

  return (
    <ReactFlow
      nodes={nodes}
      edges={edges}
      fitView
      minZoom={0.3}
      maxZoom={2}
      proOptions={{ hideAttribution: true }}
      nodesDraggable
      nodesConnectable={false}
      elementsSelectable={false}
    >
      <Background color="#334155" gap={20} />
    </ReactFlow>
  );
}

export function Graph({ project }: { project: ProjectDetail }) {
  const done = project.tasks.filter((t) => t.status === "done").length;
  const ready = project.tasks.filter((t) => t.status === "ready").length;
  const blocked = project.tasks.filter((t) => t.status === "blocked").length;

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-3">
        <Badge variant="default" className="bg-green-600">
          {done} Done
        </Badge>
        <Badge variant="secondary" className="bg-yellow-600">
          {ready} Ready
        </Badge>
        <Badge variant="outline">{blocked} Blocked</Badge>
        <span className="text-sm text-muted-foreground">
          {project.layers.length} layers
        </span>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-sm">Dependency Graph</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="h-125 w-full">
            <ReactFlowProvider>
              <GraphInner project={project} />
            </ReactFlowProvider>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
