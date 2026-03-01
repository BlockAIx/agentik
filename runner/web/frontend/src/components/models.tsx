import { ModelCombobox } from "@/components/model-combobox"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Separator } from "@/components/ui/separator"
import type { ModelConfig } from "@/lib/api"
import { api } from "@/lib/api"
import {
  Cpu,
  Loader2,
  Save,
} from "lucide-react"
import { useCallback, useEffect, useState } from "react"

export function Models({ projectName }: { projectName: string }) {
  const [models, setModels] = useState<ModelConfig[]>([]);
  const [edits, setEdits] = useState<Record<string, string>>({});
  const [saving, setSaving] = useState<Record<string, boolean>>({});
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [catalog, setCatalog] = useState<string[]>([]);
  const [catalogLoading, setCatalogLoading] = useState(true);

  const fetchModels = useCallback(async () => {
    try {
      const data = await api.getModels(projectName);
      setModels(data);
      const initial: Record<string, string> = {};
      for (const m of data) {
        initial[m.agent] = m.model;
      }
      setEdits(initial);
    } catch (e) {
      setError(String(e));
    }
  }, [projectName]);

  // Fetch model catalog once on mount.
  useEffect(() => {
    api.getModelsCatalog()
      .then(setCatalog)
      .catch(() => {
        // Catalog is optional — autocomplete just won't show suggestions.
      })
      .finally(() => setCatalogLoading(false));
  }, []);

  useEffect(() => {
    fetchModels();
  }, [fetchModels]);

  const handleSave = async (agent: string) => {
    const model = edits[agent];
    if (!model) return;
    setSaving((s) => ({ ...s, [agent]: true }));
    setError(null);
    setMessage(null);
    try {
      await api.updateModel(projectName, agent, model);
      setMessage(`Model for "${agent}" saved`);
      await fetchModels();
    } catch (e) {
      setError(String(e));
    } finally {
      setSaving((s) => ({ ...s, [agent]: false }));
    }
  };

  const isDirty = (agent: string) => {
    const original = models.find((m) => m.agent === agent);
    return original ? edits[agent] !== original.model : false;
  };

  // Group agents for display.
  const buildAgents = models.filter((m) =>
    ["build", "fix", "test"].includes(m.agent),
  );
  const supportAgents = models.filter((m) =>
    ["document", "explore", "plan", "architect", "milestone"].includes(m.agent),
  );

  return (
    <div className="space-y-4">
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

      <AgentGroup
        title="Build Agents"
        description="Core agents that write and fix code"
        agents={buildAgents}
        edits={edits}
        setEdits={setEdits}
        saving={saving}
        isDirty={isDirty}
        onSave={handleSave}
        catalog={catalog}
        loading={catalogLoading}
      />

      <AgentGroup
        title="Support Agents"
        description="Documentation, planning, architecture, and review"
        agents={supportAgents}
        edits={edits}
        setEdits={setEdits}
        saving={saving}
        isDirty={isDirty}
        onSave={handleSave}
        catalog={catalog}
        loading={catalogLoading}
      />

      <Card>
        <CardContent className="pt-4">
          <p className="text-xs text-muted-foreground">
            Models are stored in the project&apos;s{" "}
            <code className="bg-muted px-1 rounded">opencode.jsonc</code>.
            Use the format{" "}
            <code className="bg-muted px-1 rounded">provider/model-name</code>{" "}
            (e.g.{" "}
            <code className="bg-muted px-1 rounded">
              github-copilot/gemini-3.1-pro-preview
            </code>
            ). Model errors will surface when the pipeline runs — check task
            logs for details.
          </p>
        </CardContent>
      </Card>
    </div>
  );
}

function AgentGroup({
  title,
  description,
  agents,
  edits,
  setEdits,
  saving,
  isDirty,
  onSave,
  catalog,
  loading,
}: {
  title: string;
  description: string;
  agents: ModelConfig[];
  edits: Record<string, string>;
  setEdits: React.Dispatch<React.SetStateAction<Record<string, string>>>;
  saving: Record<string, boolean>;
  isDirty: (agent: string) => boolean;
  onSave: (agent: string) => void;
  catalog: string[];
  loading: boolean;
}) {
  if (agents.length === 0) return null;

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-sm flex items-center gap-2">
          <Cpu className="h-4 w-4" />
          {title}
        </CardTitle>
        <p className="text-xs text-muted-foreground">{description}</p>
      </CardHeader>
      <CardContent className="space-y-3">
        {agents.map((m, i) => (
            <div key={m.agent}>
              {i > 0 && <Separator className="my-3" />}
              <div className="flex items-center gap-3">
                <div className="w-24 shrink-0">
                  <Badge variant="outline" className="text-xs font-mono">
                    {m.agent}
                  </Badge>
                </div>
                <ModelCombobox
                  value={edits[m.agent] || ""}
                  onChange={(val) =>
                    setEdits((prev) => ({
                      ...prev,
                      [m.agent]: val,
                    }))
                  }
                  models={catalog}
                  loading={loading}
                  className="flex-1"
                />
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => onSave(m.agent)}
                  disabled={saving[m.agent] || !isDirty(m.agent)}
                  className="h-8 px-2"
                >
                  {saving[m.agent] ? (
                    <Loader2 className="h-3.5 w-3.5 animate-spin" />
                  ) : (
                    <Save className="h-3.5 w-3.5" />
                  )}
                </Button>
              </div>
            </div>
        ))}
      </CardContent>
    </Card>
  );
}
