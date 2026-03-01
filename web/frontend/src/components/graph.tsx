import { Badge } from "@/components/ui/badge"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import type { LayerInfo, ProjectDetail, TaskInfo } from "@/lib/api"
import {
  Background,
  ReactFlow,
  ReactFlowProvider,
  type Edge,
  type Node,
  type ReactFlowInstance,
} from "@xyflow/react"
import "@xyflow/react/dist/style.css"
import { useCallback, useMemo, useRef } from "react"

const NODE_WIDTH = 200;
const NODE_GAP_X = 40;
const LAYER_HEIGHT = 120;

const STATUS_COLORS: Record<string, { bg: string; border: string; text: string }> = {
  done: {
    bg: "var(--success)",
    border: "color-mix(in oklch, var(--success) 80%, black)",
    text: "var(--success-foreground)",
  },
  ready: {
    bg: "var(--warning)",
    border: "color-mix(in oklch, var(--warning) 80%, black)",
    text: "var(--warning-foreground)",
  },
  blocked: {
    bg: "color-mix(in oklch, var(--muted-foreground) 50%, var(--background))",
    border: "color-mix(in oklch, var(--muted-foreground) 35%, var(--background))",
    text: "var(--muted-foreground)",
  },
};

function getNodeColors(task: TaskInfo) {
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
      const isMilestone = task.agent === "milestone";
      nodes.push({
        id,
        position: {
          x: startX + i * (NODE_WIDTH + NODE_GAP_X),
          y: layer.index * LAYER_HEIGHT,
        },
        data: { label: isMilestone ? `◆ ${task.title}` : `${task.id}. ${task.title}` },
        style: {
          background: colors.bg,
          border: `2px ${isMilestone ? "dashed" : "solid"} ${colors.border}`,
          color: colors.text,
          borderRadius: isMilestone ? 12 : 8,
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
        style: { stroke: "var(--muted-foreground)", strokeWidth: 2 },
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

  const rfRef = useRef<ReactFlowInstance | null>(null);

  /** After the instance initialises (or data changes), fit the viewport so the
   *  top of the graph is always visible first. */
  const onInit = useCallback(
    (instance: ReactFlowInstance) => {
      rfRef.current = instance;
      // Small delay lets React Flow finish its internal layout pass.
      requestAnimationFrame(() => {
        instance.fitView({ padding: 0.12 });
        // After fitting, nudge the viewport so the top-left is visible rather
        // than the default centred view (important for tall graphs).
        const vp = instance.getViewport();
        instance.setViewport({ x: vp.x, y: 10, zoom: vp.zoom });
      });
    },
    [],
  );

  return (
    <ReactFlow
      nodes={nodes}
      edges={edges}
      fitView
      fitViewOptions={{ padding: 0.12 }}
      minZoom={0.3}
      maxZoom={2}
      onInit={onInit}
      proOptions={{ hideAttribution: true }}
      nodesDraggable
      nodesConnectable={false}
      elementsSelectable={false}
    >
      <Background color="color-mix(in oklch, var(--muted-foreground) 35%, var(--background))" gap={20} />
    </ReactFlow>
  );
}

export function Graph({ project }: { project: ProjectDetail }) {
  const done = project.tasks.filter((t) => t.status === "done").length;
  const ready = project.tasks.filter((t) => t.status === "ready").length;
  const blocked = project.tasks.filter((t) => t.status === "blocked").length;

  const milestones = project.tasks.filter((t) => t.agent === "milestone").length;

  /* Build a fingerprint so the ReactFlowProvider remounts (and re-fits) when
   * the task data changes — e.g. when navigating back to the graph tab. */
  const dataKey = useMemo(
    () => project.tasks.map((t) => `${t.id}:${t.status}`).join(","),
    [project.tasks],
  );

  /* Scale container height with the number of layers so tall graphs are not
   * squashed into a tiny viewport.  Minimum 500 px, grows at ~120 px/layer. */
  const containerHeight = Math.max(500, project.layers.length * LAYER_HEIGHT + 80);

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-3 flex-wrap">
        <Badge variant="default" className="bg-success text-success-foreground">
          {done} Done
        </Badge>
        <Badge variant="secondary" className="bg-warning text-warning-foreground">
          {ready} Ready
        </Badge>
        <Badge variant="outline">{blocked} Blocked</Badge>
        {milestones > 0 && (
          <span className="inline-flex items-center gap-1 text-xs text-muted-foreground border border-dashed border-muted-foreground/40 rounded-sm px-1.5 py-0.5">
            ◆ {milestones} milestone{milestones > 1 ? "s" : ""}
          </span>
        )}
        <span className="text-sm text-muted-foreground">
          {project.layers.length} layers
        </span>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-sm">Dependency Graph</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="w-full" style={{ height: containerHeight }}>
            <ReactFlowProvider key={dataKey}>
              <GraphInner project={project} />
            </ReactFlowProvider>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
