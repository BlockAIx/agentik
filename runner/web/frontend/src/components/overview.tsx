import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import type { GlobalBudget, ProjectDetail } from "@/lib/api";
import {
    Activity,
    CheckCircle2,
    Clock,
    Coins,
    Layers,
    Zap,
} from "lucide-react";

function formatTokens(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`;
  return String(n);
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

  // Per-agent breakdown.
  const agentCounts: Record<string, number> = {};
  for (const t of tasks) {
    agentCounts[t.agent] = (agentCounts[t.agent] || 0) + 1;
  }

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
              {formatTokens(project.budget.total_tokens)}
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
                Coverage ≥ {project.min_coverage}%
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
                <div className="font-medium">
                  {formatTokens(budget.monthly_limit)}
                </div>
              </div>
              <div>
                <span className="text-muted-foreground">Spent:</span>
                <div className="font-medium">
                  {formatTokens(budget.spent_tokens)}
                </div>
              </div>
              <div>
                <span className="text-muted-foreground">Remaining:</span>
                <div className="font-medium">
                  {formatTokens(budget.remaining_tokens)}
                </div>
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

      {/* Token usage per session (last 20) */}
      {project.budget.sessions.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-sm">Recent Token Usage</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex items-end gap-1 h-32">
              {project.budget.sessions.slice(-30).map((s, i) => {
                const max = Math.max(
                  ...project.budget.sessions.slice(-30).map((x) => x.tokens),
                );
                const h = max > 0 ? (s.tokens / max) * 100 : 0;
                return (
                  <div
                    key={i}
                    className="flex-1 bg-chart-1 rounded-t-sm min-w-1 hover:bg-chart-2 transition-colors"
                    style={{ height: `${h}%` }}
                    title={`${s.task}: ${formatTokens(s.tokens)} (${s.phase})`}
                  />
                );
              })}
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
