import { Button } from "@/components/ui/button";
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogHeader,
    DialogTitle,
    DialogTrigger,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { api } from "@/lib/api";
import { FolderPlus, GitBranch, Loader2 } from "lucide-react";
import { useState } from "react";

const ECOSYSTEMS = ["python", "deno", "node", "go", "rust"] as const;

interface CreateProjectDialogProps {
  onCreated: (name: string) => void;
}

export function CreateProjectDialog({ onCreated }: CreateProjectDialogProps) {
  const [open, setOpen] = useState(false);
  const [name, setName] = useState("");
  const [ecosystem, setEcosystem] = useState("python");
  const [preamble, setPreamble] = useState("");
  const [git, setGit] = useState(true);
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleCreate = async () => {
    if (!name.trim()) {
      setError("Project name is required");
      return;
    }
    if (!/^[a-zA-Z0-9_-]+$/.test(name)) {
      setError("Name may only contain letters, numbers, hyphens, and underscores");
      return;
    }

    setCreating(true);
    setError(null);
    try {
      await api.createProject(name, ecosystem, preamble, git);
      setOpen(false);
      resetForm();
      onCreated(name);
    } catch (e) {
      setError(String(e));
    } finally {
      setCreating(false);
    }
  };

  const resetForm = () => {
    setName("");
    setEcosystem("python");
    setPreamble("");
    setGit(true);
    setError(null);
  };

  return (
    <Dialog open={open} onOpenChange={(v) => { setOpen(v); if (!v) resetForm(); }}>
      <DialogTrigger asChild>
        <Button variant="outline" size="sm" className="gap-1.5">
          <FolderPlus className="h-3.5 w-3.5" />
          New Project
        </Button>
      </DialogTrigger>
      <DialogContent className="sm:max-w-[480px]">
        <DialogHeader>
          <DialogTitle>Create New Project</DialogTitle>
          <DialogDescription>
            Set up a new project with a ROADMAP skeleton. You can edit the
            ROADMAP in the Editor tab after creation.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4 pt-2">
          {error && (
            <div className="p-3 bg-destructive/10 border border-destructive/20 rounded-md text-sm text-destructive">
              {error}
            </div>
          )}

          <div className="space-y-2">
            <Label htmlFor="project-name">Project Name</Label>
            <Input
              id="project-name"
              placeholder="my-project"
              value={name}
              onChange={(e) => setName(e.target.value)}
            />
            <p className="text-xs text-muted-foreground">
              Letters, numbers, hyphens, and underscores only.
            </p>
          </div>

          <div className="space-y-2">
            <Label htmlFor="ecosystem">Ecosystem</Label>
            <Select value={ecosystem} onValueChange={setEcosystem}>
              <SelectTrigger id="ecosystem">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {ECOSYSTEMS.map((eco) => (
                  <SelectItem key={eco} value={eco}>
                    {eco.charAt(0).toUpperCase() + eco.slice(1)}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="space-y-2">
            <Label htmlFor="preamble">Preamble (optional)</Label>
            <Textarea
              id="preamble"
              placeholder="Brief project description — injected into every build prompt as project context."
              value={preamble}
              onChange={(e) => setPreamble(e.target.value)}
              className="min-h-[80px] resize-y"
            />
          </div>

          <div className="flex items-center gap-3">
            <button
              type="button"
              role="switch"
              aria-checked={git}
              onClick={() => setGit(!git)}
              className={`relative inline-flex h-5 w-9 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors ${
                git ? "bg-primary" : "bg-muted"
              }`}
            >
              <span
                className={`pointer-events-none block h-4 w-4 rounded-full bg-background shadow-lg transition-transform ${
                  git ? "translate-x-4" : "translate-x-0"
                }`}
              />
            </button>
            <div className="flex items-center gap-1.5 text-sm">
              <GitBranch className="h-3.5 w-3.5" />
              Initialize git repository
            </div>
          </div>

          <Button
            className="w-full"
            onClick={handleCreate}
            disabled={creating}
          >
            {creating ? (
              <>
                <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                Creating...
              </>
            ) : (
              <>
                <FolderPlus className="h-4 w-4 mr-2" />
                Create Project
              </>
            )}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
