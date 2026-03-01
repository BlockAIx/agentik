import { ModelCombobox } from "@/components/model-combobox"
import { Badge } from "@/components/ui/badge"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Separator } from "@/components/ui/separator"
import { useAvailableModels, useModels, useUpdateModel } from "@/hooks/use-queries"
import type { AvailableModel, ModelConfig } from "@/lib/api"
import { AlertTriangle, Cpu, Loader2 } from "lucide-react"
import { useCallback } from "react"

export function Models({
  projectName,
}: {
  projectName: string
}): React.JSX.Element {
  const { data: models = [], error: fetchError } = useModels(projectName)
  const { data: catalog = [] } = useAvailableModels()
  const mutation = useUpdateModel(projectName)

  /** Auto-save on combobox selection. */
  const handleSave = useCallback(
    async (agent: string, model: string) => {
      if (!model) return
      try {
        await mutation.mutateAsync({ agent, model })
      } catch {
        /* mutation state has error */
      }
    },
    [mutation],
  )

  /** True when configured model is absent from connected catalog. */
  const isInvalid = (value: string) =>
    catalog.length > 0 && !!value && !catalog.find((c) => c.full_id === value)

  const values: Record<string, string> = {}
  for (const m of models) values[m.agent] = m.model

  const buildAgents = models.filter((m) =>
    ["build", "fix", "test"].includes(m.agent),
  )
  const supportAgents = models.filter((m) =>
    ["document", "explore", "plan", "architect", "milestone"].includes(m.agent),
  )

  const error = fetchError ?? mutation.error

  return (
    <div className="space-y-4">
      {error && (
        <div className="p-3 bg-destructive/10 border border-destructive/20 rounded-md text-sm text-destructive">
          {String(error)}
        </div>
      )}

      <AgentGroup
        title="Build Agents"
        description="Core agents that write and fix code"
        agents={buildAgents}
        values={values}
        saving={mutation.isPending ? mutation.variables?.agent : undefined}
        isInvalid={isInvalid}
        onSave={handleSave}
        catalog={catalog}
      />

      <AgentGroup
        title="Support Agents"
        description="Documentation, planning, architecture, and review"
        agents={supportAgents}
        values={values}
        saving={mutation.isPending ? mutation.variables?.agent : undefined}
        isInvalid={isInvalid}
        onSave={handleSave}
        catalog={catalog}
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
              github-copilot/claude-sonnet-4-5
            </code>
            ). Selections are saved immediately. Models shown in{" "}
            <span className="text-destructive">red</span> are not available
            through your connected providers.
          </p>
        </CardContent>
      </Card>
    </div>
  )
}

/* ── Agent Group ── */

function AgentGroup({
  title,
  description,
  agents,
  values,
  saving,
  isInvalid,
  onSave,
  catalog,
}: {
  title: string
  description: string
  agents: ModelConfig[]
  values: Record<string, string>
  saving?: string
  isInvalid: (value: string) => boolean
  onSave: (agent: string, model: string) => void
  catalog: AvailableModel[]
}): React.JSX.Element | null {
  if (agents.length === 0) return null

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
        {agents.map((m, i) => {
          const val = values[m.agent] || ""
          const invalid = isInvalid(val)
          return (
            <div key={m.agent}>
              {i > 0 && <Separator className="my-3" />}
              <div className="flex items-center gap-3">
                <div className="w-24 shrink-0">
                  <Badge
                    variant="outline"
                    className={`text-xs font-mono ${invalid ? "border-destructive text-destructive" : ""}`}
                  >
                    {m.agent}
                  </Badge>
                </div>
                <ModelCombobox
                  value={val}
                  onChange={(newVal) => onSave(m.agent, newVal)}
                  models={catalog}
                  invalid={invalid}
                  className="flex-1"
                />
                {saving === m.agent ? (
                  <Loader2 className="h-3.5 w-3.5 animate-spin text-muted-foreground shrink-0" />
                ) : invalid ? (
                  <AlertTriangle className="h-3.5 w-3.5 text-destructive shrink-0" />
                ) : (
                  <div className="w-3.5 shrink-0" />
                )}
              </div>
            </div>
          )
        })}
      </CardContent>
    </Card>
  )
}
