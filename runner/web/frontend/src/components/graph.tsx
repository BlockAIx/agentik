import { Badge } from "@/components/ui/badge"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import type { ProjectDetail, TaskInfo } from "@/lib/api"
import {
  Background,
  type Edge,
  type Node,
  ReactFlow,
  ReactFlowProvider,
} from "@xyflow/react"
import "@xyflow/react/dist/style.css"
import dagre from "dagre"
import { useMemo } from "react"

const NODE_WIDTH = 200;
const NODE_HEIGHT = 50;

const STATUS_COLORS: Record<string, { bg: string; border: string; text: string }> = {
  done: { bg: "#16a34a", border: "#15803d", text: "#ffffff" },
  ready: { bg: "#ca8a04", border: "#a16207", text: "#ffffff" },
  blocked: { bg: "#475569", border: "#334155", text: "#94a3b8" },
};

function buildLayout(tasks: TaskInfo[]): { nodes: Node[]; edges: Edge[] } {
  const g = new dagre.graphlib.Graph();
  g.setDefaultEdgeLabel(() => ({}));
  g.setGraph({ rankdir: "TB", nodesep: 40, ranksep: 60 });

  for (const task of tasks) {
    g.setNode(String(task.id), { width: NODE_WIDTH, height: NODE_HEIGHT });
  }

  const edges: Edge[] = [];
  for (const task of tasks) {
    for (const dep of task.deps) {
      // dep is a zero-padded string ("001") — normalise to match node IDs ("1").
      const sourceId = String(parseInt(dep, 10));
      const targetId = String(task.id);
      const edgeId = `e${sourceId}-${targetId}`;
      g.setEdge(sourceId, targetId);
      edges.push({
        id: edgeId,
        source: sourceId,
        target: targetId,
        style: { stroke: "#64748b", strokeWidth: 2 },
        animated: task.status === "ready",
      });
    }
  }

  dagre.layout(g);

  const nodes: Node[] = tasks.map((task) => {
    const pos = g.node(String(task.id));
    const colors = STATUS_COLORS[task.status] ?? STATUS_COLORS.blocked;
    return {
      id: String(task.id),
      position: { x: pos.x - NODE_WIDTH / 2, y: pos.y - NODE_HEIGHT / 2 },
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
    };
  });

  return { nodes, edges };
}

function GraphInner({ project }: { project: ProjectDetail }) {
  const { nodes, edges } = useMemo(
    () => buildLayout(project.tasks),
    [project.tasks],
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
          <div className="h-[500px] w-full">
            <ReactFlowProvider>
              <GraphInner project={project} />
            </ReactFlowProvider>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
