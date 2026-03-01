import { Layout } from "@/components/layout"
import { Badge } from "@/components/ui/badge"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"
import {
    useGlobalBudget,
    useInvalidateProject,
    usePipelineStatus,
    useProjects,
} from "@/hooks/use-queries"
import type { ProjectSummary } from "@/lib/api"
import { fmt } from "@/lib/format"
import { useWsStore } from "@/stores/ws-store"
import {
    Activity,
    ArrowRight,
    Coins,
    FolderOpen,
    Layers,
    Loader2,
    Play,
    Zap,
} from "lucide-react"
import { useEffect } from "react"
import { Link, useNavigate } from "react-router-dom"

export function Dashboard(): React.JSX.Element {
  const navigate = useNavigate()
  const { data: projects = [], isLoading } = useProjects()
  const { data: budget } = useGlobalBudget()
  const { data: pipeStatus } = usePipelineStatus()
  const invalidate = useInvalidateProject()
  const pipelineProject = pipeStatus?.running ? pipeStatus.project : null

  /* WS-driven invalidation */
  useEffect(() => {
    return useWsStore.getState().subscribe((msg) => {
      if (msg.event === "pipeline_started" || msg.event === "pipeline_stopped") {
        invalidate()
      }
    })
  }, [invalidate])

  const handleProjectCreated = (name: string) => navigate(`/project/${name}`)

  const totalTokens = projects.reduce((s, p) => s + p.total_tokens, 0)
  const totalTasks = projects.reduce((s, p) => s + p.tasks_total, 0)
  const totalDone = projects.reduce((s, p) => s + p.tasks_done, 0)

  if (isLoading) {
    return (
      <Layout>
        <div className="space-y-6">
          <div className="grid grid-cols-4 gap-4">
            {[...Array(4)].map((_, i) => (
              <Skeleton key={i} className="h-28" />
            ))}
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {[...Array(3)].map((_, i) => (
              <Skeleton key={i} className="h-48" />
            ))}
          </div>
        </div>
      </Layout>
    )
  }

  return (
    <Layout onCreated={handleProjectCreated}>
      <div className="space-y-6">
        {/* ── KPI cards ── */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <KpiCard
            title="Projects"
            value={String(projects.length)}
            icon={<FolderOpen className="h-4 w-4" />}
            detail={`${projects.filter((p) => p.status !== "complete").length} active`}
          />
          <KpiCard
            title="Tasks"
            value={`${totalDone}/${totalTasks}`}
            icon={<Layers className="h-4 w-4" />}
            detail={
              totalTasks > 0
                ? `${Math.round((totalDone / totalTasks) * 100)}% complete`
                : "No tasks"
            }
          />
          <KpiCard
            title="Tokens Used"
            value={fmt(totalTokens)}
            icon={<Zap className="h-4 w-4" />}
            detail={budget ? `${fmt(budget.remaining_tokens)} remaining` : ""}
          />
          <KpiCard
            title="Pipeline"
            value={pipelineProject ? "Running" : "Idle"}
            icon={
              pipelineProject ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Activity className="h-4 w-4" />
              )
            }
            detail={pipelineProject ?? "No active pipeline"}
            variant={pipelineProject ? "active" : "default"}
          />
        </div>

        {/* ── Budget bar ── */}
        {budget && (
          <Card>
            <CardContent className="pt-4 pb-3">
              <div className="flex items-center justify-between mb-2">
                <span className="text-xs text-muted-foreground flex items-center gap-1.5">
                  <Coins className="h-3.5 w-3.5" />
                  Monthly Budget
                </span>
                <span className="text-xs font-mono text-muted-foreground">
                  {fmt(budget.spent_tokens)} / {fmt(budget.monthly_limit)}
                </span>
              </div>
              <div className="h-2 rounded-full bg-secondary overflow-hidden">
                <div
                  className="h-full bg-primary rounded-full transition-all"
                  style={{
                    width: `${Math.min(100, (budget.spent_tokens / budget.monthly_limit) * 100)}%`,
                  }}
                />
              </div>
            </CardContent>
          </Card>
        )}

        {/* ── Project cards ── */}
        {projects.length === 0 ? (
          <Card>
            <CardContent className="flex flex-col items-center justify-center py-16 text-muted-foreground">
              <FolderOpen className="h-10 w-10 mb-3 opacity-40" />
              <p className="text-sm">No projects yet</p>
              <p className="text-xs mt-1">
                Create a ROADMAP.json in{" "}
                <code className="bg-muted px-1 rounded">projects/</code> or use
                the button above.
              </p>
            </CardContent>
          </Card>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {projects.map((p) => (
              <ProjectCard
                key={p.name}
                project={p}
                isRunning={pipelineProject === p.name}
              />
            ))}
          </div>
        )}
      </div>
    </Layout>
  )
}

/* ── KPI Card ── */

function KpiCard({
  title,
  value,
  icon,
  detail,
  variant = "default",
}: {
  title: string
  value: string
  icon: React.ReactNode
  detail?: string
  variant?: "default" | "active"
}): React.JSX.Element {
  return (
    <Card className={variant === "active" ? "border-green-500/30" : ""}>
      <CardHeader className="flex flex-row items-center justify-between pb-2">
        <CardTitle className="text-sm font-medium text-muted-foreground">
          {title}
        </CardTitle>
        <span className="text-muted-foreground">{icon}</span>
      </CardHeader>
      <CardContent>
        <div className="text-2xl font-bold">{value}</div>
        {detail && (
          <p className="text-xs text-muted-foreground mt-1">{detail}</p>
        )}
      </CardContent>
    </Card>
  )
}

/* ── Project Card ── */

function ProjectCard({
  project,
  isRunning,
}: {
  project: ProjectSummary
  isRunning: boolean
}): React.JSX.Element {
  const pct =
    project.tasks_total > 0
      ? Math.round((project.tasks_done / project.tasks_total) * 100)
      : 0

  return (
    <Link to={`/project/${project.name}`} className="block group">
      <Card className="h-full transition-colors group-hover:border-primary/40">
        <CardHeader className="pb-3">
          <div className="flex items-center justify-between">
            <CardTitle className="text-sm font-medium flex items-center gap-2">
              {project.name}
              {isRunning && (
                <Badge
                  variant="outline"
                  className="gap-1 text-green-500 border-green-500/30 text-xs animate-pulse"
                >
                  <Play className="h-2.5 w-2.5 fill-current" />
                  Running
                </Badge>
              )}
            </CardTitle>
            <ArrowRight className="h-4 w-4 text-muted-foreground opacity-0 group-hover:opacity-100 transition" />
          </div>
          <p className="text-xs text-muted-foreground truncate">
            {project.detail}
          </p>
        </CardHeader>
        <CardContent className="space-y-3">
          <div>
            <div className="flex justify-between text-xs mb-1">
              <span className="text-muted-foreground">Progress</span>
              <span className="font-mono">
                {project.tasks_done}/{project.tasks_total}
              </span>
            </div>
            <div className="h-1.5 rounded-full bg-secondary overflow-hidden">
              <div
                className="h-full bg-primary rounded-full transition-all"
                style={{ width: `${pct}%` }}
              />
            </div>
          </div>
          <div className="flex items-center justify-between text-xs text-muted-foreground">
            <span className="flex items-center gap-1">
              <Zap className="h-3 w-3" />
              {fmt(project.total_tokens)} tokens
            </span>
            <span className="flex items-center gap-1">
              <Activity className="h-3 w-3" />
              {project.total_calls} calls
            </span>
            <Badge variant="outline" className="text-xs">
              {isRunning ? "running" : project.status}
            </Badge>
          </div>
        </CardContent>
      </Card>
    </Link>
  )
}
