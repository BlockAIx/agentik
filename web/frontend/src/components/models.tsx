import { ModelCombobox } from '@/components/model-combobox'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Separator } from '@/components/ui/separator'
import { Switch } from '@/components/ui/switch'
import {
  useAvailableModels,
  useModels,
  useSkills,
  useUpdateAgentSkills,
  useUpdateModel,
} from '@/hooks/use-queries'
import type { AvailableModel, ModelConfig, SkillInfo } from '@/lib/api'
import { AlertTriangle, BookOpen, Cpu, Loader2 } from 'lucide-react'
import { useCallback } from 'react'

export function Models({
  projectName,
}: {
  projectName: string
}): React.JSX.Element {
  const { data: models = [], error: fetchError } = useModels(projectName)
  const { data: catalog = [] } = useAvailableModels()
  const { data: availableSkills = [] } = useSkills()
  const modelMutation = useUpdateModel(projectName)
  const skillsMutation = useUpdateAgentSkills(projectName)

  const handleSaveModel = useCallback(
    async (agent: string, model: string) => {
      if (!model) return
      try {
        await modelMutation.mutateAsync({ agent, model })
      } catch {
        /* mutation state has error */
      }
    },
    [modelMutation],
  )

  const handleToggleSkill = useCallback(
    async (agent: string, currentSkills: string[], slug: string, enabled: boolean) => {
      const next = enabled
        ? [...currentSkills, slug]
        : currentSkills.filter((s) => s !== slug)
      try {
        await skillsMutation.mutateAsync({ agent, skills: next })
      } catch {
        /* mutation state has error */
      }
    },
    [skillsMutation],
  )

  const isInvalid = (value: string) =>
    catalog.length > 0 && !!value && !catalog.find((c) => c.full_id === value)

  const values: Record<string, string> = {}
  const agentSkills: Record<string, string[]> = {}
  for (const m of models) {
    values[m.agent] = m.model
    agentSkills[m.agent] = m.skills ?? []
  }

  const buildAgents = models.filter((m) => ['build', 'fix'].includes(m.agent))
  const supportAgents = models.filter((m) =>
    ['architect', 'milestone'].includes(m.agent),
  )

  const error = fetchError ?? modelMutation.error ?? skillsMutation.error

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
        agentSkills={agentSkills}
        availableSkills={availableSkills}
        savingModel={modelMutation.isPending ? modelMutation.variables?.agent : undefined}
        savingSkills={skillsMutation.isPending ? skillsMutation.variables?.agent : undefined}
        isInvalid={isInvalid}
        onSaveModel={handleSaveModel}
        onToggleSkill={handleToggleSkill}
        catalog={catalog}
      />

      <AgentGroup
        title="Support Agents"
        description="Architecture (also used by the create roadmap tool) and milestone agents"
        agents={supportAgents}
        values={values}
        agentSkills={agentSkills}
        availableSkills={availableSkills}
        savingModel={modelMutation.isPending ? modelMutation.variables?.agent : undefined}
        savingSkills={skillsMutation.isPending ? skillsMutation.variables?.agent : undefined}
        isInvalid={isInvalid}
        onSaveModel={handleSaveModel}
        onToggleSkill={handleToggleSkill}
        catalog={catalog}
      />

      <Card>
        <CardContent>
          <p className="text-xs text-muted-foreground">
            Models are stored in the project&apos;s{' '}
            <code className="bg-muted px-1 rounded">opencode.jsonc</code>. Use
            the format{' '}
            <code className="bg-muted px-1 rounded">provider/model-name</code>{' '}
            (e.g.{' '}
            <code className="bg-muted px-1 rounded">
              github-copilot/claude-sonnet-4-5
            </code>
            ). Skills are loaded from the workspace{' '}
            <code className="bg-muted px-1 rounded">skills/</code> directory
            and injected into agent prompts when enabled.
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
  agentSkills,
  availableSkills,
  savingModel,
  savingSkills,
  isInvalid,
  onSaveModel,
  onToggleSkill,
  catalog,
}: {
  title: string
  description: string
  agents: ModelConfig[]
  values: Record<string, string>
  agentSkills: Record<string, string[]>
  availableSkills: SkillInfo[]
  savingModel?: string
  savingSkills?: string
  isInvalid: (value: string) => boolean
  onSaveModel: (agent: string, model: string) => void
  onToggleSkill: (agent: string, current: string[], slug: string, enabled: boolean) => void
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
          const val = values[m.agent] || ''
          const invalid = isInvalid(val)
          const skills = agentSkills[m.agent] ?? []
          return (
            <div key={m.agent}>
              {i > 0 && <Separator className="my-3" />}
              <div className="flex items-center gap-3">
                <div className="w-24 shrink-0">
                  <Badge
                    variant="outline"
                    className={`text-xs font-mono ${invalid ? 'border-destructive text-destructive' : ''}`}
                  >
                    {m.agent}
                  </Badge>
                </div>
                <ModelCombobox
                  value={val}
                  onChange={(newVal) => onSaveModel(m.agent, newVal)}
                  models={catalog}
                  invalid={invalid}
                  className="flex-1"
                />
                {savingModel === m.agent ? (
                  <Loader2 className="h-3.5 w-3.5 animate-spin text-muted-foreground shrink-0" />
                ) : invalid ? (
                  <AlertTriangle className="h-3.5 w-3.5 text-destructive shrink-0" />
                ) : (
                  <div className="w-3.5 shrink-0" />
                )}
              </div>
              {availableSkills.length > 0 && (
                <div className="mt-2 ml-27 space-y-1.5">
                  <p className="text-xs text-muted-foreground flex items-center gap-1">
                    <BookOpen className="h-3 w-3" />
                    Skills
                    {savingSkills === m.agent && (
                      <Loader2 className="h-3 w-3 animate-spin" />
                    )}
                  </p>
                  {availableSkills.map((sk) => (
                    <label
                      key={sk.slug}
                      className="flex items-center gap-2 text-xs cursor-pointer"
                    >
                      <Switch
                        size="sm"
                        checked={skills.includes(sk.slug)}
                        onCheckedChange={(checked: boolean) =>
                          onToggleSkill(m.agent, skills, sk.slug, checked)
                        }
                      />
                      <span className="font-mono">{sk.name}</span>
                      {sk.description && (
                        <span className="text-muted-foreground truncate">
                          — {sk.description}
                        </span>
                      )}
                    </label>
                  ))}
                </div>
              )}
            </div>
          )
        })}
      </CardContent>
    </Card>
  )
}
