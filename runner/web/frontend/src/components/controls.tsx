import { useState, useEffect } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import {
  Play,
  Square,
  Gauge,
  Loader2,
  Clock,
  Coins,
  Zap,
  RefreshCw,
} from "lucide-react";
import { api } from "@/lib/api";
import type { ProjectDetail, DryRunResult } from "@/lib/api";

export function Controls({
  projectName,
  detail,
  onRefresh,
}: {
  projectName: string;
  detail: ProjectDetail;
  onRefresh: () => void;
}) {
  const [running, setRunning] = useState(false);
  const [stopping, setStopping] = useState(false);
  const [dryRun, setDryRun] = useState<DryRunResult | null>(null);
  const [loadingDry, setLoadingDry] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  const handleRun = async () => {
    setRunning(true);
    setError(null);
    setMessage(null);
    try {
      const res = await api.runPipeline(projectName);
      setMessage(res.started ? "Pipeline started" : "Pipeline already running");
    } catch (e) {
      setError(String(e));
    } finally {
      setRunning(false);
    }
  };

  const handleStop = async () => {
    setStopping(true);
    setError(null);
    setMessage(null);
    try {
      const res = await api.stopPipeline(projectName);
      setMessage(res.stopped ? "Pipeline stopped" : "Pipeline was not running");
    } catch (e) {
      setError(String(e));
    } finally {
      setStopping(false);
    }
  };

  const fetchDryRun = async () => {
    setLoadingDry(true);
    setError(null);
    try {
      const data = await api.getDryRun(projectName);
      setDryRun(data);
    } catch (e) {
      setError(String(e));
    } finally {
      setLoadingDry(false);
    }
  };

  useEffect(() => {
    fetchDryRun();
  }, [projectName]);

  const formatTime = (sec: number): string => {
    if (sec < 60) return `${sec}s`;
    const m = Math.floor(sec / 60);
    const s = sec % 60;
    return `${m}m ${s}s`;
  };

  const { state } = detail;

  return (
    <div className="space-y-4">
      {/* Pipeline Controls */}
      <Card>
        <CardHeader>
          <CardTitle className="text-sm">Pipeline Controls</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex items-center gap-3">
            <Button onClick={handleRun} disabled={running}>
              {running ? (
                <Loader2 className="h-3.5 w-3.5 mr-1 animate-spin" />
              ) : (
                <Play className="h-3.5 w-3.5 mr-1" />
              )}
              Run Pipeline
            </Button>
            <Button variant="destructive" onClick={handleStop} disabled={stopping}>
              {stopping ? (
                <Loader2 className="h-3.5 w-3.5 mr-1 animate-spin" />
              ) : (
                <Square className="h-3.5 w-3.5 mr-1" />
              )}
              Stop
            </Button>
            <Button variant="outline" onClick={onRefresh}>
              <RefreshCw className="h-3.5 w-3.5 mr-1" />
              Refresh
            </Button>
          </div>

          {error && (
            <div className="p-3 bg-destructive/10 border border-destructive/20 rounded-md text-sm text-destructive">
              {error}
            </div>
          )}
          {message && (
            <div className="p-3 bg-green-500/10 border border-green-500/20 rounded-md text-sm text-green-400">
              {message}
            </div>
          )}

          <Separator />

          <div className="grid grid-cols-4 gap-4 text-sm">
            <div>
              <span className="text-muted-foreground">Current Task</span>
              <div className="mt-1 font-medium">
                {state.current_task ? (
                  <Badge variant="outline">{state.current_task}</Badge>
                ) : (
                  <span className="text-muted-foreground">—</span>
                )}
              </div>
            </div>
            <div>
              <span className="text-muted-foreground">Attempt</span>
              <div className="mt-1 font-medium">{state.attempt || "—"}</div>
            </div>
            <div>
              <span className="text-muted-foreground">Progress</span>
              <div className="mt-1 font-medium">
                {state.completed} / {state.total}
              </div>
            </div>
            <div>
              <span className="text-muted-foreground">Failures</span>
              <div className="mt-1 font-medium">
                {state.failed.length > 0 ? (
                  <Badge variant="destructive">{state.failed.length}</Badge>
                ) : (
                  <Badge variant="secondary">0</Badge>
                )}
              </div>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Dry Run / Cost Estimate */}
      <Card>
        <CardHeader className="flex flex-row items-center justify-between">
          <CardTitle className="text-sm flex items-center gap-2">
            <Gauge className="h-4 w-4" />
            Dry Run Estimate
          </CardTitle>
          <Button
            variant="outline"
            size="sm"
            onClick={fetchDryRun}
            disabled={loadingDry}
          >
            {loadingDry ? (
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
            ) : (
              "Refresh"
            )}
          </Button>
        </CardHeader>
        <CardContent>
          {dryRun ? (
            <div className="space-y-4">
              <div className="grid grid-cols-3 gap-4">
                <Card>
                  <CardContent className="pt-4 flex items-center gap-3">
                    <Zap className="h-8 w-8 text-yellow-500" />
                    <div>
                      <div className="text-2xl font-bold">
                        {(dryRun.estimated_tokens / 1_000_000).toFixed(1)}M
                      </div>
                      <div className="text-xs text-muted-foreground">
                        Est. tokens
                      </div>
                    </div>
                  </CardContent>
                </Card>
                <Card>
                  <CardContent className="pt-4 flex items-center gap-3">
                    <Coins className="h-8 w-8 text-green-500" />
                    <div>
                      <div className="text-2xl font-bold">
                        ${dryRun.estimated_usd.toFixed(2)}
                      </div>
                      <div className="text-xs text-muted-foreground">
                        Est. cost
                      </div>
                    </div>
                  </CardContent>
                </Card>
                <Card>
                  <CardContent className="pt-4 flex items-center gap-3">
                    <Clock className="h-8 w-8 text-blue-500" />
                    <div>
                      <div className="text-2xl font-bold">
                        {formatTime(dryRun.estimated_time_sec)}
                      </div>
                      <div className="text-xs text-muted-foreground">
                        Est. time
                      </div>
                    </div>
                  </CardContent>
                </Card>
              </div>

              <div className="text-sm text-muted-foreground">
                {dryRun.remaining_tasks} of {dryRun.total_tasks} tasks remaining
                ({dryRun.completed_tasks} completed)
              </div>

              {dryRun.task_breakdown.length > 0 && (
                <div className="border rounded-md overflow-hidden">
                  <table className="w-full text-xs">
                    <thead className="bg-muted/50">
                      <tr>
                        <th className="text-left p-2 font-medium">Task</th>
                        <th className="text-left p-2 font-medium">Type</th>
                        <th className="text-right p-2 font-medium">Tokens</th>
                        <th className="text-right p-2 font-medium">Cost</th>
                      </tr>
                    </thead>
                    <tbody>
                      {dryRun.task_breakdown.map((t, i) => (
                        <tr key={i} className="border-t border-border/50">
                          <td className="p-2 font-mono">{t.task}</td>
                          <td className="p-2">
                            <Badge variant="outline" className="text-xs">
                              {t.type}
                            </Badge>
                          </td>
                          <td className="p-2 text-right font-mono">
                            {(t.tokens / 1000).toFixed(0)}k
                          </td>
                          <td className="p-2 text-right font-mono">
                            ${t.usd.toFixed(3)}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          ) : loadingDry ? (
            <div className="flex items-center justify-center p-8 text-muted-foreground">
              <Loader2 className="h-5 w-5 mr-2 animate-spin" />
              Loading estimates...
            </div>
          ) : (
            <div className="text-sm text-muted-foreground p-4 text-center">
              No estimate available.
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
