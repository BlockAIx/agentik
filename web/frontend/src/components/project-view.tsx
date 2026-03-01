import { Controls } from "@/components/controls"
import { Generator } from "@/components/generator"
import { Graph } from "@/components/graph"
import { Layout } from "@/components/layout"
import { Logs } from "@/components/logs"
import { Models } from "@/components/models"
import { Overview } from "@/components/overview"
import { Review } from "@/components/review"
import { RoadmapEditor } from "@/components/roadmap-editor"
import { Tasks } from "@/components/tasks"
import { Badge } from "@/components/ui/badge"
import { Skeleton } from "@/components/ui/skeleton"
import {
    Tabs,
    TabsContent,
    TabsList,
    TabsTrigger,
} from "@/components/ui/tabs"
import {
    useAvailableModels,
    useInvalidateProject,
    useModels,
    useProject,
} from "@/hooks/use-queries"
import { useWsStore } from "@/stores/ws-store"
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
} from "lucide-react"
import { useEffect } from "react"
import { useParams } from "react-router-dom"

export function ProjectView(): React.JSX.Element {
  const { name } = useParams<{ name: string }>()
  const projectName = name ?? ""

  const { data: detail, isLoading } = useProject(projectName)
  const { data: availableModels = [] } = useAvailableModels()
  const { data: projectModels = [] } = useModels(projectName)
  const invalidate = useInvalidateProject()

  /* WS-driven invalidation */
  useEffect(() => {
    return useWsStore.getState().subscribe(() => {
      invalidate(projectName)
    })
  }, [invalidate, projectName])

  const invalidModels =
    availableModels.length > 0
      ? projectModels.filter(
          (m) => !availableModels.find((a) => a.full_id === m.model),
        )
      : []

  return (
    <Layout
      backTo="/"
      backLabel="Dashboard"
      title={projectName}
      badge={
        detail ? (
          <Badge variant="outline" className="text-xs">
            {detail.ecosystem}
          </Badge>
        ) : undefined
      }
    >
      {isLoading ? (
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
            <Overview project={detail} invalidModels={invalidModels} />
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
              invalidModels={invalidModels}
            />
          </TabsContent>
        </Tabs>
      )}
    </Layout>
  )
}
