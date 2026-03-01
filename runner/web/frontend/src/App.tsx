import { Controls } from "@/components/controls"
import { Generator } from "@/components/generator"
import { Graph } from "@/components/graph"
import { Logs } from "@/components/logs"
import { Models } from "@/components/models"
import { Overview } from "@/components/overview"
import { Review } from "@/components/review"
import { RoadmapEditor } from "@/components/roadmap-editor"
import { Tasks } from "@/components/tasks"
import { Badge } from "@/components/ui/badge"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { Separator } from "@/components/ui/separator"
import {
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
} from "@/components/ui/tabs"
import { TooltipProvider } from "@/components/ui/tooltip"
import { useWebSocket } from "@/hooks/use-websocket"
import type { GlobalBudget, ProjectDetail, ProjectSummary } from "@/lib/api"
import { api } from "@/lib/api"
import {
  Cpu,
  Eye,
  FileCode2,
  FileText,
  GitBranch,
  LayoutDashboard,
  ListChecks,
  Settings2,
  Sparkles,
  Wifi,
  WifiOff,
} from "lucide-react"
import { useCallback, useEffect, useState } from "react"

export default function App(): React.JSX.Element {
  const [projects, setProjects] = useState<ProjectSummary[]>([]);
  const [selected, setSelected] = useState<string>("");
  const [detail, setDetail] = useState<ProjectDetail | null>(null);
  const [budget, setBudget] = useState<GlobalBudget | null>(null);
  const [loading, setLoading] = useState(true);
  const [wsRefresh, setWsRefresh] = useState(0);

  const { connected } = useWebSocket(() => {
    // Re-fetch detail on every WebSocket event.
    setWsRefresh((n) => n + 1);
  });

  // Load project list on mount.
  useEffect(() => {
    api
      .listProjects()
      .then((list) => {
        setProjects(list);
        if (list.length > 0 && !selected) {
          setSelected(list[0].name);
        }
      })
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  // Load detail when selection changes or WS events arrive.
  const fetchDetail = useCallback(async () => {
    if (!selected) return;
    try {
      const [d, b] = await Promise.all([
        api.getProject(selected),
        api.getGlobalBudget().catch(() => null),
      ]);
      setDetail(d);
      setBudget(b);
    } catch (e) {
      console.error("Failed to load project detail:", e);
    }
  }, [selected]);

  useEffect(() => {
    fetchDetail();
  }, [fetchDetail, wsRefresh]);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-screen text-muted-foreground">
        Loading...
      </div>
    );
  }

  return (
    <TooltipProvider>
      <div className="min-h-screen bg-background text-foreground">
        {/* Header */}
        <header className="border-b border-border">
          <div className="max-w-7xl mx-auto px-4 py-3 flex items-center justify-between">
            <div className="flex items-center gap-3">
              <h1 className="text-lg font-semibold tracking-tight">
                agentik
              </h1>
              <Separator orientation="vertical" className="h-5" />
              <Select value={selected} onValueChange={setSelected}>
                <SelectTrigger className="w-[220px] h-8 text-sm">
                  <SelectValue placeholder="Select project" />
                </SelectTrigger>
                <SelectContent>
                  {projects.map((p) => (
                    <SelectItem key={p.name} value={p.name}>
                      <span className="flex items-center gap-2">
                        {p.name}
                        <Badge variant="outline" className="text-xs ml-1">
                          {p.tasks_done}/{p.tasks_total}
                        </Badge>
                      </span>
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="flex items-center gap-2 text-xs text-muted-foreground">
              {connected ? (
                <Badge variant="outline" className="gap-1 text-green-500 border-green-500/30">
                  <Wifi className="h-3 w-3" />
                  Live
                </Badge>
              ) : (
                <Badge variant="outline" className="gap-1 text-muted-foreground">
                  <WifiOff className="h-3 w-3" />
                  Offline
                </Badge>
              )}
            </div>
          </div>
        </header>

        {/* Main content */}
        <main className="max-w-7xl mx-auto px-4 py-4">
          {!selected || !detail ? (
            <div className="flex items-center justify-center h-[60vh] text-muted-foreground">
              {projects.length === 0
                ? "No projects found. Create a ROADMAP.json in projects/ to get started."
                : "Select a project to get started."}
            </div>
          ) : (
            <Tabs defaultValue="overview" className="space-y-4">
              <TabsList className="grid w-full grid-cols-9">
                <TabsTrigger value="overview" className="gap-1 text-xs">
                  <LayoutDashboard className="h-3.5 w-3.5" />
                  Overview
                </TabsTrigger>
                <TabsTrigger value="graph" className="gap-1 text-xs">
                  <GitBranch className="h-3.5 w-3.5" />
                  Graph
                </TabsTrigger>
                <TabsTrigger value="tasks" className="gap-1 text-xs">
                  <ListChecks className="h-3.5 w-3.5" />
                  Tasks
                </TabsTrigger>
                <TabsTrigger value="logs" className="gap-1 text-xs">
                  <FileText className="h-3.5 w-3.5" />
                  Logs
                </TabsTrigger>
                <TabsTrigger value="editor" className="gap-1 text-xs">
                  <FileCode2 className="h-3.5 w-3.5" />
                  Editor
                </TabsTrigger>
                <TabsTrigger value="generator" className="gap-1 text-xs">
                  <Sparkles className="h-3.5 w-3.5" />
                  Generate
                </TabsTrigger>
                <TabsTrigger value="models" className="gap-1 text-xs">
                  <Cpu className="h-3.5 w-3.5" />
                  Models
                </TabsTrigger>
                <TabsTrigger value="review" className="gap-1 text-xs">
                  <Eye className="h-3.5 w-3.5" />
                  Review
                </TabsTrigger>
                <TabsTrigger value="controls" className="gap-1 text-xs">
                  <Settings2 className="h-3.5 w-3.5" />
                  Controls
                </TabsTrigger>
              </TabsList>

              <TabsContent value="overview">
                <Overview project={detail} budget={budget} />
              </TabsContent>
              <TabsContent value="graph">
                <Graph project={detail} />
              </TabsContent>
              <TabsContent value="tasks">
                <Tasks project={detail} />
              </TabsContent>
              <TabsContent value="logs">
                <Logs projectName={selected} />
              </TabsContent>
              <TabsContent value="editor">
                <RoadmapEditor projectName={selected} />
              </TabsContent>
              <TabsContent value="generator">
                <Generator projectName={selected} />
              </TabsContent>
              <TabsContent value="models">
                <Models projectName={selected} />
              </TabsContent>
              <TabsContent value="review">
                <Review projectName={selected} detail={detail} />
              </TabsContent>
              <TabsContent value="controls">
                <Controls
                  projectName={selected}
                  detail={detail}
                  onRefresh={fetchDetail}
                />
              </TabsContent>
            </Tabs>
          )}
        </main>
      </div>
    </TooltipProvider>
  );
}
