export interface ProjectSummary {
  name: string
  path: string
  status: string
  detail: string
  tasks_total: number
  tasks_done: number
  total_tokens: number
  total_calls: number
}

export interface TaskInfo {
  id: number
  heading: string
  title: string
  status: "done" | "ready" | "blocked"
  agent: string
  tokens: number
  deps: string[]
}

export interface LayerInfo {
  index: number
  tasks: string[]
}

export interface BudgetSession {
  task: string
  phase: string
  tokens: number
  timestamp: string
}

export interface ProjectDetail {
  name: string
  ecosystem: string
  preamble: string
  tasks: TaskInfo[]
  layers: LayerInfo[]
  budget: {
    total_tokens: number
    total_calls: number
    sessions: BudgetSession[]
  }
  state: {
    current_task: string | null
    running_tasks: string[]
    attempt: number
    completed: number
    total: number
    failed: Array<{ task: string; reason?: string }>
  }
  min_coverage: number | null
  notify: { url: string; events: string[] } | null
}

export interface LogEntry {
  task_slug: string
  logs: Array<{ name: string; path: string; size: number }>
  failure_report: {
    task: string
    attempts: number
    last_error: string | null
    failing_test: string | null
    tokens_spent: number
    timestamp: string
  } | null
}

export interface GlobalBudget {
  monthly_limit: number
  spent_tokens: number
  remaining_tokens: number
  max_attempts: number
  max_parallel: number
}

export interface ModelConfig {
  agent: string
  model: string
  max_steps: number
}

export interface BudgetConfig {
  monthly_limit_tokens: number
  per_task_limit_tokens: number
  max_attempts_per_task: number
  max_parallel_agents: number
  token_prices_usd_per_million: {
    input: number
    output: number
    cache_read: number
    cache_write: number
  }
}

export interface ProjectBudget {
  project: string
  total_tokens: number
  total_calls: number
  sessions: BudgetSession[]
}

export interface ProviderInfo {
  name: string
  auth_type: string
  source: string
  connected: boolean
}

export interface AvailableModel {
  full_id: string
  provider: string
  model: string
}

const BASE = ""

/** Typed fetch wrapper — throws on non-2xx responses. */
async function fetchJson<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${url}`, init)
  if (!res.ok) {
    const text = await res.text()
    throw new Error(`API ${res.status}: ${text}`)
  }
  return res.json()
}

export const api = {
  /* ── Projects ── */

  listProjects: (signal?: AbortSignal) =>
    fetchJson<ProjectSummary[]>("/api/projects", { signal }),

  createProject: (name: string, ecosystem: string, preamble: string, git: boolean) =>
    fetchJson<{ created: boolean; name: string; path: string }>("/api/projects", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name, ecosystem, preamble, git }),
    }),

  getProject: (name: string, signal?: AbortSignal) =>
    fetchJson<ProjectDetail>(`/api/projects/${name}`, { signal }),

  getRoadmap: (name: string, signal?: AbortSignal) =>
    fetchJson<Record<string, unknown>>(`/api/projects/${name}/roadmap`, { signal }),

  updateRoadmap: (name: string, data: Record<string, unknown>) =>
    fetchJson<{ saved: boolean; valid: boolean }>(`/api/projects/${name}/roadmap`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    }),

  getLogs: (name: string, signal?: AbortSignal) =>
    fetchJson<LogEntry[]>(`/api/projects/${name}/logs`, { signal }),

  getLogContent: (name: string, taskSlug: string, logName: string, signal?: AbortSignal) =>
    fetchJson<{ content: string; name: string; task_slug: string }>(
      `/api/projects/${name}/logs/${taskSlug}/${logName}`,
      { signal },
    ),

  validateRoadmap: (name: string) =>
    fetchJson<{ valid: boolean }>(`/api/projects/${name}/validate`, { method: "POST" }),

  getProjectBudget: (name: string, signal?: AbortSignal) =>
    fetchJson<ProjectBudget>(`/api/projects/${name}/budget`, { signal }),

  updateProjectBudget: (name: string, data: Record<string, unknown>) =>
    fetchJson<{ saved: boolean }>(`/api/projects/${name}/budget`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    }),

  /* ── Pipeline ── */

  runPipeline: (name: string, verbose = false) =>
    fetchJson<{ started: boolean }>(`/api/projects/${name}/run`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ verbose }),
    }),

  getPipelineStatus: (signal?: AbortSignal) =>
    fetchJson<{ running: boolean; project: string | null }>("/api/pipeline/status", { signal }),

  stopPipeline: (name: string) =>
    fetchJson<{ stopped: boolean }>(`/api/projects/${name}/stop`, { method: "POST" }),

  /* ── Roadmap generation ── */

  generateRoadmap: (name: string, description: string, ecosystem: string) =>
    fetchJson<{ roadmap: Record<string, unknown> }>(`/api/projects/${name}/generate-roadmap`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ description, ecosystem }),
    }),

  /* ── Global config ── */

  getGlobalBudget: (signal?: AbortSignal) =>
    fetchJson<GlobalBudget>("/api/budget", { signal }),

  getBudgetConfig: (signal?: AbortSignal) =>
    fetchJson<BudgetConfig>("/api/config/budget", { signal }),

  updateBudgetConfig: (data: BudgetConfig) =>
    fetchJson<{ saved: boolean }>("/api/config/budget", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    }),

  /* ── Models ── */

  getModels: (name: string, signal?: AbortSignal) =>
    fetchJson<ModelConfig[]>(`/api/projects/${name}/models`, { signal }),

  updateModel: (name: string, agent: string, model: string) =>
    fetchJson<{ saved: boolean }>(`/api/projects/${name}/models/${agent}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ model }),
    }),

  /* ── Providers ── */

  getProviders: (signal?: AbortSignal) =>
    fetchJson<{ providers: ProviderInfo[]; raw: string }>("/api/providers", { signal }),

  getAvailableModels: (signal?: AbortSignal) =>
    fetchJson<AvailableModel[]>("/api/providers/models", { signal }),

  refreshAvailableModels: () =>
    fetchJson<{ count: number; models: AvailableModel[] }>(
      "/api/providers/models/refresh",
      { method: "POST" },
    ),

  providerLogin: (provider?: string) =>
    fetchJson<{
      success: boolean
      in_docker: boolean
      is_windows: boolean
      github_token_set: boolean
      login_command: string
      note: string
      steps: string[]
      alternatives: Array<{
        title: string
        description: string
        env_var: string
        docs_url: string
      }>
    }>("/api/providers/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ provider: provider ?? "" }),
    }),

  providerLogout: () =>
    fetchJson<{ output: string; success: boolean }>("/api/providers/logout", {
      method: "POST",
    }),
}
