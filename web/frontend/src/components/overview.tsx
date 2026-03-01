import { Badge } from "@/components/ui/badge"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Separator } from "@/components/ui/separator"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { Tile } from "@/components/ui/tile"
import type { ProjectDetail } from "@/lib/api"
import { fmt, fmtDate } from "@/lib/format"
import {
  Activity,
  AlertTriangle,
  CheckCircle2,
  Coins,
  Flag,
  Layers,
  Zap,
} from "lucide-react"

interface OverviewProps {
  project: ProjectDetail;
  invalidModels?: Array<{ agent: string; model: string }>;
}

export function Overview({ project, invalidModels }: OverviewProps) {
  const { state, tasks } = project;
  const done = tasks.filter((t) => t.status === "done").length;
  const ready = tasks.filter((t) => t.status === "ready").length;
  const blocked = tasks.filter((t) => t.status === "blocked").length;
  const pct = tasks.length > 0 ? Math.round((done / tasks.length) * 100) : 0;

  const donePct = tasks.length > 0 ? (done / tasks.length) * 100 : 0;
  const readyPct = tasks.length > 0 ? (ready / tasks.length) * 100 : 0;

  const currentTaskInfo = state.current_task
    ? tasks.find((t) => t.heading === state.current_task)
    : null;

  // For parallel builds, resolve all concurrently-running task infos.
  const runningTaskInfos = (state.running_tasks ?? [])
    .map((h) => tasks.find((t) => t.heading === h))
    .filter((t): t is NonNullable<typeof t> => t !== undefined);
  const isParallel = runningTaskInfos.length > 1;
  const nextMilestone = tasks.find(
    (t) => t.agent === "milestone" && t.status !== "done",
  );

  const agentCounts: Record<string, number> = {};
  for (const t of tasks) {
    agentCounts[t.agent] = (agentCounts[t.agent] || 0) + 1;
  }

  const perTask: Record<string, { tokens: number; calls: number }> = {};
  for (const s of project.budget.sessions) {
    const key = s.task || "unknown";
    if (!perTask[key]) perTask[key] = { tokens: 0, calls: 0 };
    perTask[key].tokens += s.tokens;
    perTask[key].calls += 1;
  }
  const taskUsage = Object.entries(perTask)
    .sort(([, a], [, b]) => b.tokens - a.tokens);

  return (
    <div className="space-y-6">
      {invalidModels && invalidModels.length > 0 && (
        <div className="p-3 bg-destructive/10 border border-destructive/20 rounded-md flex items-start gap-2 text-sm text-destructive">
          <AlertTriangle className="h-4 w-4 shrink-0 mt-0.5" />
          <div>
            <span className="font-medium">
              {invalidModels.length} model{invalidModels.length > 1 ? "s" : ""} not available:
            </span>{" "}
            {invalidModels.map((m) => m.agent).join(", ")} — go to the{" "}
            <strong>Models tab</strong> to fix before running the pipeline.
          </div>
        </div>
      )}

      {/* Parallel batch banner */}
      {isParallel && (
        <div className="p-3 border border-success/20 bg-success/5 rounded-md space-y-2 text-sm">
          <div className="flex items-center gap-3">
            <span className="relative flex h-2.5 w-2.5 shrink-0">
              <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-success opacity-75" />
              <span className="relative inline-flex h-2.5 w-2.5 rounded-full bg-success" />
            </span>
            <span className="text-xs font-medium text-success">Running</span>
            <span className="text-xs text-muted-foreground">{runningTaskInfos.length} tasks in parallel</span>
          </div>
          <div className="flex flex-wrap gap-2 pl-5">
            {runningTaskInfos.map((t) => (
              <div key={t.id} className="flex items-center gap-1.5 px-2 py-1 bg-muted rounded-md text-xs">
                <span className="font-mono text-muted-foreground">#{t.id}</span>
                <span className="font-medium">{t.title}</span>
                <Badge variant="outline" className="text-[10px] h-4 px-1.5">
                  {t.agent}
                </Badge>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Single task banner */}
      {!isParallel && currentTaskInfo && (
        <div className="p-3 border border-success/20 bg-success/5 rounded-md flex items-center gap-3 text-sm">
          <span className="relative flex h-2.5 w-2.5 shrink-0">
            <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-success opacity-75" />
            <span className="relative inline-flex h-2.5 w-2.5 rounded-full bg-success" />
          </span>
          <span className="text-xs font-medium text-success shrink-0">Running</span>
          <span className="font-mono text-xs text-muted-foreground shrink-0">#{currentTaskInfo.id}</span>
          <span className="font-medium truncate">{currentTaskInfo.title}</span>
          <Badge variant="outline" className="text-[10px] h-4 px-1.5 shrink-0">
            {currentTaskInfo.agent}
          </Badge>
          {state.attempt > 1 && (
            <span className="text-xs text-warning shrink-0">attempt {state.attempt}</span>
          )}
        </div>
      )}

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Progress
            </CardTitle>
            <CheckCircle2 className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{pct}%</div>
            <p className="text-xs text-muted-foreground">
              {done} / {tasks.length} tasks complete
            </p>
            <div className="mt-2 h-2 rounded-full bg-secondary overflow-hidden">
              <div
                className="h-full bg-primary rounded-full transition-all"
                style={{ width: `${pct}%` }}
              />
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Task Status
            </CardTitle>
            <Layers className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent className="space-y-3">
            {/* Segmented progress bar */}
            <div className="flex h-2 rounded-full bg-muted overflow-hidden">
              {done > 0 && (
                <div
                  className="h-full bg-success transition-all"
                  style={{ width: `${donePct}%` }}
                />
              )}
              {ready > 0 && (
                <div
                  className="h-full bg-warning transition-all"
                  style={{ width: `${readyPct}%` }}
                />
              )}
            </div>

            {/* Legend */}
            <div className="flex items-center gap-3 text-xs text-muted-foreground">
              <span className="flex items-center gap-1">
                <span className="h-2 w-2 rounded-full bg-success" />
                {done} done
              </span>
              <span className="flex items-center gap-1">
                <span className="h-2 w-2 rounded-full bg-warning" />
                {ready} ready
              </span>
              <span className="flex items-center gap-1">
                <span className="h-2 w-2 rounded-full bg-muted-foreground/40" />
                {blocked} blocked
              </span>
            </div>

            {/* Next milestone */}
            {nextMilestone && (
              <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
                <Flag className="h-3 w-3 shrink-0" />
                <span className="shrink-0">Next milestone:</span>
                <span className="font-medium text-foreground truncate">
                  {nextMilestone.title}
                </span>
              </div>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Tokens Used
            </CardTitle>
            <Coins className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {fmt(project.budget.total_tokens)}
            </div>
            <p className="text-xs text-muted-foreground">
              {project.budget.total_calls} API calls
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Failures
            </CardTitle>
            <Activity className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{state.failed.length}</div>
            <p className="text-xs text-muted-foreground truncate">
              {state.failed.length > 0
                ? state.failed[state.failed.length - 1].task.replace(
                    /^## \d{3} - /,
                    "",
                  )
                : "No failed tasks"}
            </p>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Zap className="h-5 w-5" />
            {project.name}
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="flex items-center gap-4 text-sm">
            <span className="text-muted-foreground">Ecosystem:</span>
            <Badge variant="outline">{project.ecosystem}</Badge>
            {project.min_coverage && (
              <Badge variant="secondary">
                Coverage &ge; {project.min_coverage}%
              </Badge>
            )}
          </div>
          {project.preamble && (
            <p className="text-sm text-muted-foreground">{project.preamble}</p>
          )}

          <Separator />

          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 text-sm">
            {Object.entries(agentCounts).map(([agent, count]) => (
              <div key={agent}>
                <span className="text-muted-foreground">{agent}:</span>{" "}
                <span className="font-medium">{count}</span>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>

      {taskUsage.length > 0 && (
        <Tile
          title={<><Coins className="h-4 w-4" />Token Usage by Task</>}
          flush
          maxH="350px"
        >
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Task</TableHead>
                <TableHead className="text-right w-28">Tokens</TableHead>
                <TableHead className="text-right w-20">Calls</TableHead>
                <TableHead className="w-48">Share</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {taskUsage.map(([task, usage]) => {
                const share = project.budget.total_tokens > 0
                  ? (usage.tokens / project.budget.total_tokens) * 100
                  : 0;
                return (
                  <TableRow key={task}>
                    <TableCell className="text-xs font-medium max-w-50 truncate">
                      {task.replace(/^## \d{3} - /, "")}
                    </TableCell>
                    <TableCell className="text-right font-mono text-xs">
                      {fmt(usage.tokens)}
                    </TableCell>
                    <TableCell className="text-right font-mono text-xs">
                      {usage.calls}
                    </TableCell>
                    <TableCell>
                      <div className="flex items-center gap-2">
                        <div className="flex-1 h-2 rounded-full bg-secondary overflow-hidden">
                          <div
                            className="h-full bg-chart-2 rounded-full transition-all"
                            style={{ width: `${share}%` }}
                          />
                        </div>
                        <span className="text-xs text-muted-foreground w-10 text-right">
                          {share.toFixed(0)}%
                        </span>
                      </div>
                    </TableCell>
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
        </Tile>
      )}

      {project.budget.sessions.length > 0 && (
        <Tile title="Recent API Sessions" flush maxH="260px">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Time</TableHead>
                <TableHead>Task</TableHead>
                <TableHead>Phase</TableHead>
                <TableHead className="text-right">Tokens</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {[...project.budget.sessions].reverse().slice(0, 30).map((s, i) => (
                <TableRow key={i}>
                  <TableCell className="text-xs text-muted-foreground whitespace-nowrap">
                    {fmtDate(s.timestamp)}
                  </TableCell>
                  <TableCell className="text-xs font-medium truncate max-w-45">
                    {(s.task || "\u2014").replace(/^## \d{3} - /, "")}
                  </TableCell>
                  <TableCell>
                    <Badge variant="outline" className="text-xs">
                      {s.phase}
                    </Badge>
                  </TableCell>
                  <TableCell className="text-right font-mono text-xs">
                    {fmt(s.tokens)}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </Tile>
      )}
    </div>
  );
}
