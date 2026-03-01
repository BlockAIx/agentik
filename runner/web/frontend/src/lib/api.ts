// API types matching the FastAPI backend responses.

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
    attempt: number
    completed: number
    total: number
    failed: Array<{ task: string; reason?: string }>
  }
  review_enabled: boolean
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

export interface ModelTestResult {
  agent: string
  model: string
  ok: boolean
  error: string | null
  latency_ms: number | null
}

const BASE = ""

async function fetchJson<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${url}`, init)
  if (!res.ok) {
    const text = await res.text()
    throw new Error(`API ${res.status}: ${text}`)
  }
  return res.json()
}

export const api = {
  listProjects: () => fetchJson<ProjectSummary[]>("/api/projects"),

  getProject: (name: string) => fetchJson<ProjectDetail>(`/api/projects/${name}`),

  getRoadmap: (name: string) => fetchJson<Record<string, unknown>>(`/api/projects/${name}/roadmap`),

  updateRoadmap: (name: string, data: Record<string, unknown>) =>
    fetchJson<{ saved: boolean; valid: boolean }>(`/api/projects/${name}/roadmap`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    }),

  getLogs: (name: string) => fetchJson<LogEntry[]>(`/api/projects/${name}/logs`),

  getLogContent: (name: string, taskSlug: string, logName: string) =>
    fetchJson<{ content: string; name: string; task_slug: string }>(
      `/api/projects/${name}/logs/${taskSlug}/${logName}`,
    ),

  validateRoadmap: (name: string) =>
    fetchJson<{ valid: boolean }>(`/api/projects/${name}/validate`, { method: "POST" }),

  runPipeline: (name: string) =>
    fetchJson<{ started: boolean }>(`/api/projects/${name}/run`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({}),
    }),

  stopPipeline: (name: string) =>
    fetchJson<{ stopped: boolean }>(`/api/projects/${name}/stop`, { method: "POST" }),

  generateRoadmap: (name: string, description: string, ecosystem: string) =>
    fetchJson<{ roadmap: Record<string, unknown> }>(`/api/projects/${name}/generate-roadmap`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ description, ecosystem }),
    }),

  handleReview: (name: string, action: "approve" | "reject") =>
    fetchJson<{ action: string; acknowledged: boolean }>(
      `/api/projects/${name}/review/${action}`,
      { method: "POST" },
    ),

  getDiff: (name: string) => fetchJson<{ diff: string; status: string }>(`/api/projects/${name}/diff`),

  getGlobalBudget: () => fetchJson<GlobalBudget>("/api/budget"),

  getModels: (name: string) =>
    fetchJson<ModelConfig[]>(`/api/projects/${name}/models`),

  updateModel: (name: string, agent: string, model: string) =>
    fetchJson<{ saved: boolean }>(`/api/projects/${name}/models/${agent}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ model }),
    }),

  testModel: (name: string, agent: string) =>
    fetchJson<ModelTestResult>(`/api/projects/${name}/models/${agent}/test`, {
      method: "POST",
    }),
}
