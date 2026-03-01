import { Badge } from "@/components/ui/badge"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Separator } from "@/components/ui/separator"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import type { GlobalBudget, ProjectDetail } from "@/lib/api"
import {
  Activity,
  CheckCircle2,
  Clock,
  Coins,
  Layers,
  Zap,
} from "lucide-react"

function fmt(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`;
  return String(n);
}

function fmtDate(iso: string): string {
  try {
    const d = new Date(iso);
    return d.toLocaleDateString(undefined, { month: "short", day: "numeric" })
      + " " + d.toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" });
  } catch {
    return iso;
  }
}

interface OverviewProps {
  project: ProjectDetail;
  budget: GlobalBudget | null;
}

export function Overview({ project, budget }: OverviewProps) {
  const { state, tasks } = project;
  const done = tasks.filter((t) => t.status === "done").length;
  const ready = tasks.filter((t) => t.status === "ready").length;
  const blocked = tasks.filter((t) => t.status === "blocked").length;
  const pct = tasks.length > 0 ? Math.round((done / tasks.length) * 100) : 0;

  const agentCounts: Record<string, number> = {};
  for (const t of tasks) {
    agentCounts[t.agent] = (agentCounts[t.agent] || 0) + 1;
  }

  // Aggregate tokens per task from sessions.
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
      {/* Stats cards */}
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
          <CardContent>
            <div className="flex items-center gap-3">
              <Badge variant="default" className="bg-green-600">
                {done} done
              </Badge>
              <Badge variant="secondary" className="bg-yellow-600">
                {ready} ready
              </Badge>
              <Badge variant="outline">{blocked} blocked</Badge>
            </div>
            {state.current_task && (
              <p className="mt-2 text-xs text-muted-foreground truncate">
                Current: {state.current_task.replace(/^## \d{3} - /, "")}
              </p>
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
            <p className="text-xs text-muted-foreground">
              Attempt {state.attempt} on current task
            </p>
          </CardContent>
        </Card>
      </div>

      {/* Project info */}
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
            {project.review_enabled && (
              <Badge variant="secondary">Review enabled</Badge>
            )}
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

      {/* Global budget */}
      {budget && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-sm">
              <Clock className="h-4 w-4" />
              Global Budget
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 text-sm">
              <div>
                <span className="text-muted-foreground">Monthly limit:</span>
                <div className="font-medium">{fmt(budget.monthly_limit)}</div>
              </div>
              <div>
                <span className="text-muted-foreground">Spent:</span>
                <div className="font-medium">{fmt(budget.spent_tokens)}</div>
              </div>
              <div>
                <span className="text-muted-foreground">Remaining:</span>
                <div className="font-medium">{fmt(budget.remaining_tokens)}</div>
              </div>
              <div>
                <span className="text-muted-foreground">Max parallel:</span>
                <div className="font-medium">{budget.max_parallel}</div>
              </div>
            </div>
            <div className="mt-3 h-2 rounded-full bg-secondary overflow-hidden">
              <div
                className="h-full bg-chart-1 rounded-full transition-all"
                style={{
                  width: `${Math.min(100, (budget.spent_tokens / budget.monthly_limit) * 100)}%`,
                }}
              />
            </div>
          </CardContent>
        </Card>
      )}

      {/* Token usage by task — clear table */}
      {taskUsage.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-sm flex items-center gap-2">
              <Coins className="h-4 w-4" />
              Token Usage by Task
            </CardTitle>
          </CardHeader>
          <CardContent className="p-0">
            <ScrollArea className="max-h-[350px]">
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
                        <TableCell className="text-xs font-medium truncate max-w-[200px]">
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
            </ScrollArea>
          </CardContent>
        </Card>
      )}

      {/* Recent sessions log */}
      {project.budget.sessions.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-sm">Recent API Sessions</CardTitle>
          </CardHeader>
          <CardContent className="p-0">
            <ScrollArea className="max-h-[250px]">
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
                      <TableCell className="text-xs font-medium truncate max-w-[180px]">
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
            </ScrollArea>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
