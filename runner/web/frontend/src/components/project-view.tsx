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
import { Button } from "@/components/ui/button"
import { Separator } from "@/components/ui/separator"
import { Skeleton } from "@/components/ui/skeleton"
import {
    Tabs,
    TabsContent,
    TabsList,
    TabsTrigger,
} from "@/components/ui/tabs"
import { useWebSocket } from "@/hooks/use-websocket"
import type { ProjectDetail } from "@/lib/api"
import { api } from "@/lib/api"
import {
    ArrowLeft,
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
import { Link, useParams } from "react-router-dom"

export function ProjectView(): React.JSX.Element {
  const { name } = useParams<{ name: string }>()
  const projectName = name ?? ""

  const [detail, setDetail] = useState<ProjectDetail | null>(null)
  const [loading, setLoading] = useState(true)
  const [wsRefresh, setWsRefresh] = useState(0)

  const { connected } = useWebSocket(() => {
    setWsRefresh((n) => n + 1)
  })

  const fetchDetail = useCallback(async () => {
    if (!projectName) return
    try {
      const d = await api.getProject(projectName)
      setDetail(d)
    } catch (e) {
      console.error("Failed to load project:", e)
    } finally {
      setLoading(false)
    }
  }, [projectName])

  useEffect(() => {
    fetchDetail()
  }, [fetchDetail, wsRefresh])

  return (
    <div className="min-h-screen bg-background text-foreground">
      {/* Header */}
      <header className="border-b border-border">
        <div className="max-w-7xl mx-auto px-4 py-3 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Link to="/">
              <Button variant="ghost" size="sm" className="h-8 px-2 gap-1.5 text-xs">
                <ArrowLeft className="h-3.5 w-3.5" />
                Dashboard
              </Button>
            </Link>
            <Separator orientation="vertical" className="h-5" />
            <h1 className="text-lg font-semibold tracking-tight">
              {projectName}
            </h1>
            {detail && (
              <Badge variant="outline" className="text-xs">
                {detail.ecosystem}
              </Badge>
            )}
          </div>
          <div className="flex items-center gap-2">
            <Link to="/settings">
              <Button variant="ghost" size="sm" className="h-8 px-2 text-xs gap-1.5">
                <Settings2 className="h-3.5 w-3.5" />
              </Button>
            </Link>
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

      {/* Main */}
      <main className="max-w-7xl mx-auto px-4 py-4">
        {loading ? (
          <div className="space-y-4">
            <Skeleton className="h-10 w-full" />
            <div className="grid grid-cols-3 gap-4">
              <Skeleton className="h-32" />
              <Skeleton className="h-32" />
              <Skeleton className="h-32" />
            </div>
            <Skeleton className="h-64 w-full" />
          </div>
        ) : !detail ? (
          <div className="flex flex-col items-center justify-center h-[60vh] text-muted-foreground gap-3">
            <p>Project &ldquo;{projectName}&rdquo; not found.</p>
            <Link to="/">
              <Button variant="outline" size="sm">
                <ArrowLeft className="h-3.5 w-3.5 mr-1" />
                Back to dashboard
              </Button>
            </Link>
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
              <Overview project={detail} />
            </TabsContent>
            <TabsContent value="graph">
              <Graph project={detail} />
            </TabsContent>
            <TabsContent value="tasks">
              <Tasks project={detail} />
            </TabsContent>
            <TabsContent value="logs">
              <Logs projectName={projectName} />
            </TabsContent>
            <TabsContent value="editor">
              <RoadmapEditor projectName={projectName} />
            </TabsContent>
            <TabsContent value="generator">
              <Generator projectName={projectName} />
            </TabsContent>
            <TabsContent value="models">
              <Models projectName={projectName} />
            </TabsContent>
            <TabsContent value="review">
              <Review projectName={projectName} detail={detail} />
            </TabsContent>
            <TabsContent value="controls">
              <Controls
                projectName={projectName}
                detail={detail}
                onRefresh={fetchDetail}
              />
            </TabsContent>
          </Tabs>
        )}
      </main>
    </div>
  )
}
