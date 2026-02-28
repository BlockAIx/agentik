import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { ProjectDetail } from "@/lib/api";
import { useEffect, useRef } from "react";

declare global {
  interface Window {
    mermaid: {
      initialize: (config: Record<string, unknown>) => void;
      run: (config?: { nodes?: HTMLElement[] }) => Promise<void>;
    };
  }
}

function buildMermaidDef(project: ProjectDetail): string {
  const lines = ["graph TD"];

  for (const task of project.tasks) {
    const nodeId = `T${String(task.id).padStart(3, "0")}`;
    const label = `${task.id}. ${task.title}`;

    let style = "";
    if (task.status === "done") {
      style = `style ${nodeId} fill:#16a34a,stroke:#15803d,color:#fff`;
    } else if (task.status === "ready") {
      style = `style ${nodeId} fill:#ca8a04,stroke:#a16207,color:#fff`;
    } else {
      style = `style ${nodeId} fill:#475569,stroke:#334155,color:#94a3b8`;
    }

    lines.push(`    ${nodeId}["${label}"]`);
    if (style) lines.push(`    ${style}`);
  }

  // Edges.
  for (const task of project.tasks) {
    const nodeId = `T${String(task.id).padStart(3, "0")}`;
    for (const dep of task.deps) {
      const depId = `T${dep.padStart(3, "0")}`;
      lines.push(`    ${depId} --> ${nodeId}`);
    }
  }

  return lines.join("\n");
}

export function Graph({ project }: { project: ProjectDetail }) {
  const containerRef = useRef<HTMLDivElement>(null);
  const scriptLoaded = useRef(false);

  useEffect(() => {
    const loadAndRender = async () => {
      if (!scriptLoaded.current) {
        await new Promise<void>((resolve) => {
          if (window.mermaid) {
            resolve();
            return;
          }
          const script = document.createElement("script");
          script.src =
            "https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.min.js";
          script.onload = () => resolve();
          document.head.appendChild(script);
        });
        scriptLoaded.current = true;
        window.mermaid.initialize({
          startOnLoad: false,
          theme: "dark",
          flowchart: { curve: "monotoneX", padding: 20 },
        });
      }

      if (containerRef.current) {
        const def = buildMermaidDef(project);
        containerRef.current.innerHTML = `<pre class="mermaid">${def}</pre>`;
        await window.mermaid.run({
          nodes: [containerRef.current.querySelector(".mermaid")!],
        });
      }
    };

    loadAndRender();
  }, [project]);

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
          <div
            ref={containerRef}
            className="overflow-auto min-h-[300px] flex items-center justify-center"
          />
        </CardContent>
      </Card>
    </div>
  );
}
