import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import type { ProjectDetail } from "@/lib/api";

function formatTokens(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`;
  return String(n);
}

function statusBadge(status: string) {
  switch (status) {
    case "done":
      return (
        <Badge variant="default" className="bg-green-600">
          Done
        </Badge>
      );
    case "ready":
      return (
        <Badge variant="secondary" className="bg-yellow-600">
          Ready
        </Badge>
      );
    default:
      return <Badge variant="outline">Blocked</Badge>;
  }
}

export function Tasks({ project }: { project: ProjectDetail }) {
  return (
    <div className="rounded-md border">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead className="w-12">#</TableHead>
            <TableHead>Title</TableHead>
            <TableHead className="w-24">Status</TableHead>
            <TableHead className="w-24">Agent</TableHead>
            <TableHead className="w-24 text-right">Tokens</TableHead>
            <TableHead>Dependencies</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {project.tasks.map((task) => (
            <TableRow
              key={task.id}
              className={
                task.status === "done" ? "opacity-60" : ""
              }
            >
              <TableCell className="font-mono text-muted-foreground">
                {String(task.id).padStart(3, "0")}
              </TableCell>
              <TableCell className="font-medium">{task.title}</TableCell>
              <TableCell>{statusBadge(task.status)}</TableCell>
              <TableCell>
                <Badge variant="outline" className="text-xs">
                  {task.agent}
                </Badge>
              </TableCell>
              <TableCell className="text-right font-mono text-sm">
                {task.tokens > 0 ? formatTokens(task.tokens) : "—"}
              </TableCell>
              <TableCell className="text-xs text-muted-foreground">
                {task.deps.length > 0
                  ? task.deps.map((d) => `#${d}`).join(", ")
                  : "—"}
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}
