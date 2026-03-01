import { Controls } from "@/components/controls"
import { Generator } from "@/components/generator"
import { Graph } from "@/components/graph"
import { Layout } from "@/components/layout"
import { Logs } from "@/components/logs"
import { Models } from "@/components/models"
import { Overview } from "@/components/overview"
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
  FileCode2,
  FileText,
  GitBranch,
  LayoutDashboard,
  ListChecks,
  Settings2,
  Sparkles,
} from "lucide-react"
import { useCallback, useEffect } from "react"
import { useNavigate, useParams } from "react-router-dom"

const VALID_TABS = [
  "overview",
  "graph",
  "tasks",
  "logs",
  "editor",
  "generator",
  "models",
  "controls",
] as const

type Tab = (typeof VALID_TABS)[number]

function isValidTab(v: string | undefined): v is Tab {
  return VALID_TABS.includes(v as Tab)
}

export function ProjectView(): React.JSX.Element {
  const { name, tab } = useParams<{ name: string; tab: string }>()
  const projectName = name ?? ""
  const navigate = useNavigate()
  const activeTab: Tab = isValidTab(tab) ? tab : "overview"

  const onTabChange = useCallback(
    (value: string) => {
      const next = value === "overview" ? "" : `/${value}`
      navigate(`/project/${projectName}${next}`, { replace: true })
    },
    [navigate, projectName],
  )

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
        <Tabs value={activeTab} onValueChange={onTabChange} className="space-y-4">
          <TabsList className="grid w-full grid-cols-8">
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
