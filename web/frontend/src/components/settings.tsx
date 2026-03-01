import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Separator } from "@/components/ui/separator"
import { useBudgetConfig, useUpdateBudgetConfig } from "@/hooks/use-queries"
import type { BudgetConfig } from "@/lib/api"
import {
  CheckCircle2,
  Coins,
  Loader2,
  RotateCcw,
  Save,
  Settings2,
} from "lucide-react"
import { useState } from "react"

const DEFAULT_CONFIG: BudgetConfig = {
  monthly_limit_tokens: 2_000_000_000,
  per_task_limit_tokens: 2_000_000,
  max_attempts_per_task: 4,
  max_parallel_agents: 3,
  token_prices_usd_per_million: {
    input: 1.25,
    output: 5.0,
    cache_read: 0.31,
    cache_write: 1.25,
  },
}

export function GlobalConfig(): React.JSX.Element {
  const { data: original, isLoading } = useBudgetConfig()
  const [localConfig, setLocalConfig] = useState<BudgetConfig | null>(null)
  const [saved, setSaved] = useState(false)
  const mutation = useUpdateBudgetConfig()

  const config = localConfig ?? original ?? DEFAULT_CONFIG

  const handleSave = async () => {
    setSaved(false)
    try {
      await mutation.mutateAsync(config)
      setLocalConfig(null)
      setSaved(true)
    } catch {
      /* mutation state has error */
    }
  }

  const isDirty = localConfig !== null
  const error = mutation.error ? String(mutation.error) : null

  const updateField = <K extends keyof BudgetConfig>(
    key: K,
    value: BudgetConfig[K],
  ) => {
    setLocalConfig((prev) => ({ ...(prev ?? original ?? DEFAULT_CONFIG), [key]: value }))
    setSaved(false)
  }

  const updatePrice = (
    key: keyof BudgetConfig["token_prices_usd_per_million"],
    value: number,
  ) => {
    setLocalConfig((prev) => {
      const base = prev ?? original ?? DEFAULT_CONFIG
      return {
        ...base,
        token_prices_usd_per_million: {
          ...base.token_prices_usd_per_million,
          [key]: value,
        },
      }
    })
    setSaved(false)
  }

  if (isLoading) {
    return (
      <Card>
        <CardContent className="flex items-center justify-center py-8">
          <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
        </CardContent>
      </Card>
    )
  }

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between">
        <CardTitle className="text-sm flex items-center gap-2">
          <Settings2 className="h-4 w-4" />
          Global Configuration
          {isDirty && (
            <Badge variant="secondary" className="text-xs">
              Unsaved
            </Badge>
          )}
          {saved && !isDirty && (
            <Badge variant="default" className="bg-success text-success-foreground text-xs">
              <CheckCircle2 className="h-3 w-3 mr-1" />
              Saved
            </Badge>
          )}
        </CardTitle>
        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            disabled={!isDirty}
            onClick={() => {
              setLocalConfig(null)
              setSaved(false)
            }}
          >
            <RotateCcw className="h-3.5 w-3.5 mr-1" />
            Reset
          </Button>
          <Button
            size="sm"
            onClick={handleSave}
            disabled={mutation.isPending || !isDirty}
          >
            <Save className="h-3.5 w-3.5 mr-1" />
            {mutation.isPending ? "Saving..." : "Save"}
          </Button>
        </div>
      </CardHeader>
      <CardContent className="space-y-6">
        {error && (
          <div className="p-3 bg-destructive/10 border border-destructive/20 rounded-md text-sm text-destructive">
            {error}
          </div>
        )}

        {/* ── Budget limits ── */}
        <div className="space-y-4">
          <h3 className="text-xs font-medium text-muted-foreground uppercase tracking-wide flex items-center gap-2">
            <Coins className="h-3.5 w-3.5" />
            Budget Limits
          </h3>
          <div className="grid grid-cols-2 gap-4">
            <NumberField
              label="Monthly token limit"
              value={config.monthly_limit_tokens}
              onChange={(v) => updateField("monthly_limit_tokens", v)}
              hint="Total tokens allowed per month"
            />
            <NumberField
              label="Per-task token limit"
              value={config.per_task_limit_tokens}
              onChange={(v) => updateField("per_task_limit_tokens", v)}
              hint="Max tokens per single task"
            />
            <NumberField
              label="Max attempts per task"
              value={config.max_attempts_per_task}
              onChange={(v) => updateField("max_attempts_per_task", v)}
              hint="Retry limit before abandoning"
              step={1}
            />
            <NumberField
              label="Max parallel agents"
              value={config.max_parallel_agents}
              onChange={(v) => updateField("max_parallel_agents", v)}
              hint="Concurrent task builds"
              step={1}
            />
          </div>
        </div>

        <Separator />

        {/* ── Token prices ── */}
        <div className="space-y-4">
          <h3 className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
            Token Prices (USD / million)
          </h3>
          <div className="grid grid-cols-2 gap-4">
            <NumberField
              label="Input"
              value={config.token_prices_usd_per_million.input}
              onChange={(v) => updatePrice("input", v)}
              step={0.01}
            />
            <NumberField
              label="Output"
              value={config.token_prices_usd_per_million.output}
              onChange={(v) => updatePrice("output", v)}
              step={0.01}
            />
            <NumberField
              label="Cache read"
              value={config.token_prices_usd_per_million.cache_read}
              onChange={(v) => updatePrice("cache_read", v)}
              step={0.01}
            />
            <NumberField
              label="Cache write"
              value={config.token_prices_usd_per_million.cache_write}
              onChange={(v) => updatePrice("cache_write", v)}
              step={0.01}
            />
          </div>
        </div>

        <p className="text-xs text-muted-foreground">
          Changes to global configuration take effect on the next pipeline run.
        </p>
      </CardContent>
    </Card>
  )
}

/* ── Reusable number field ── */

function NumberField({
  label,
  value,
  onChange,
  hint,
  step = 1,
}: {
  label: string
  value: number
  onChange: (v: number) => void
  hint?: string
  step?: number
}): React.JSX.Element {
  return (
    <div className="space-y-1.5">
      <Label className="text-xs">{label}</Label>
      <Input
        type="number"
        value={value}
        step={step}
        onChange={(e) => onChange(Number(e.target.value))}
        className="font-mono text-xs h-8"
      />
      {hint && <p className="text-xs text-muted-foreground">{hint}</p>}
    </div>
  )
}
