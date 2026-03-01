import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import type { ProjectDetail } from "@/lib/api";
import { api } from "@/lib/api";
import {
    Loader2,
    Play,
    RefreshCw,
    Square,
} from "lucide-react";
import { useState } from "react";

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

  const { state } = detail;

  return (
    <div className="space-y-4">
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
                  <span className="text-muted-foreground">&mdash;</span>
                )}
              </div>
            </div>
            <div>
              <span className="text-muted-foreground">Attempt</span>
              <div className="mt-1 font-medium">{state.attempt || "\u2014"}</div>
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
    </div>
  );
}
