import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import type { WsMessage } from "@/hooks/use-websocket";
import { useWebSocket } from "@/hooks/use-websocket";
import type { ProjectDetail } from "@/lib/api";
import { api } from "@/lib/api";
import {
    Loader2,
    Play,
    RefreshCw,
    Square,
    Trash2,
} from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";

const MAX_LOG_LINES = 2000;

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
  const [pipelineActive, setPipelineActive] = useState(false);
  const [statusChecked, setStatusChecked] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [logs, setLogs] = useState<string[]>([]);
  const [verbose, setVerbose] = useState(false);
  const logEndRef = useRef<HTMLDivElement>(null);

  // Subscribe to pipeline WebSocket events for live output.
  const handleWsMessage = useCallback(
    (msg: WsMessage) => {
      if (msg.event === "pipeline_started") {
        if (msg.project === projectName) {
          setLogs([]);
          setPipelineActive(true);
        }
      } else if (msg.event === "pipeline_stopped") {
        if (msg.project === projectName) {
          setPipelineActive(false);
          onRefresh();
        }
      } else if (msg.event === "log_line") {
        if (msg.project === projectName) {
          setLogs((prev) => {
            const next = [...prev, msg.line as string];
            return next.length > MAX_LOG_LINES ? next.slice(-MAX_LOG_LINES) : next;
          });
        }
      }
    },
    [projectName, onRefresh],
  );

  useWebSocket(handleWsMessage);

  // Check real pipeline status on mount / project change so Stop is enabled
  // even if we missed the pipeline_started WebSocket event.
  useEffect(() => {
    setStatusChecked(false);
    api.getPipelineStatus().then(({ running: r }) => {
      setPipelineActive(r);
    }).catch(() => {}).finally(() => setStatusChecked(true));
  }, [projectName]);

  // Auto-scroll to the bottom of the log panel whenever new lines arrive.
  useEffect(() => {
    logEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [logs]);

  const handleRun = async () => {
    setRunning(true);
    setError(null);
    setMessage(null);
    try {
      const res = await api.runPipeline(projectName, verbose);
      if (!res.started) setMessage("Pipeline already running");
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
      setMessage(res.stopped ? "Stop signal sent" : "Pipeline was not running");
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
          <div className="flex items-center gap-3 flex-wrap">
            <Button onClick={handleRun} disabled={running || pipelineActive || !statusChecked}>
              {running ? (
                <Loader2 className="h-3.5 w-3.5 mr-1 animate-spin" />
              ) : (
                <Play className="h-3.5 w-3.5 mr-1" />
              )}
              Run Pipeline
            </Button>
            <Button
              variant="destructive"
              onClick={handleStop}
              disabled={stopping || !pipelineActive || !statusChecked}
            >
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
            <label className="flex items-center gap-1.5 text-sm text-muted-foreground cursor-pointer select-none">
              <input
                type="checkbox"
                checked={verbose}
                onChange={(e) => setVerbose(e.target.checked)}
                className="rounded"
              />
              Verbose
            </label>
            {pipelineActive && (
              <Badge
                variant="outline"
                className="gap-1 text-green-500 border-green-500/30 animate-pulse"
              >
                <Loader2 className="h-3 w-3 animate-spin" />
                Running
              </Badge>
            )}
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

      {/* Live log output panel */}
      <Card>
        <CardHeader className="flex flex-row items-center justify-between py-3">
          <CardTitle className="text-sm">Live Pipeline Output</CardTitle>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setLogs([])}
            className="h-6 px-2 text-xs"
          >
            <Trash2 className="h-3 w-3 mr-1" />
            Clear
          </Button>
        </CardHeader>
        <CardContent className="p-0">
          <div className="bg-zinc-950 rounded-b-lg font-mono text-xs text-green-400 h-[460px] overflow-y-auto p-3 border-t border-border">
            {logs.length === 0 ? (
              <span className="text-zinc-500">
                {pipelineActive
                  ? "Starting pipeline..."
                  : "No output yet — click Run Pipeline to start."}
              </span>
            ) : (
              logs.map((line, i) => (
                <div key={i} className="leading-5 whitespace-pre-wrap break-all">
                  {line}
                </div>
              ))
            )}
            <div ref={logEndRef} />
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
