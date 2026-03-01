/** TanStack Query hooks — all data fetching and mutations. */
import type { BudgetConfig } from "@/lib/api"
import { api } from "@/lib/api"
import {
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query"

/* ── Query Keys ── */

const keys = {
  projects: ["projects"] as const,
  project: (name: string) => ["project", name] as const,
  globalBudget: ["globalBudget"] as const,
  pipelineStatus: ["pipelineStatus"] as const,
  logs: (name: string) => ["logs", name] as const,
  logContent: (name: string, slug: string, log: string) =>
    ["logContent", name, slug, log] as const,
  models: (name: string) => ["models", name] as const,
  availableModels: ["availableModels"] as const,
  providers: ["providers"] as const,
  budgetConfig: ["budgetConfig"] as const,
  roadmap: (name: string) => ["roadmap", name] as const,
}

/* ── Queries ── */

export function useProjects() {
  return useQuery({
    queryKey: keys.projects,
    queryFn: ({ signal }) => api.listProjects(signal),
  })
}

export function useProject(name: string, pipelineActive?: boolean) {
  return useQuery({
    queryKey: keys.project(name),
    queryFn: ({ signal }) => api.getProject(name, signal),
    enabled: !!name,
    refetchOnMount: "always",
    // Poll every 3 s while the pipeline is running so the overview banner,
    // progress bar and task statuses stay current even between WS log events.
    refetchInterval: pipelineActive ? 3_000 : false,
  })
}

export function useGlobalBudget() {
  return useQuery({
    queryKey: keys.globalBudget,
    queryFn: ({ signal }) => api.getGlobalBudget(signal),
  })
}

export function usePipelineStatus() {
  return useQuery({
    queryKey: keys.pipelineStatus,
    queryFn: ({ signal }) => api.getPipelineStatus(signal),
    refetchInterval: 5_000,
  })
}

export function useLogs(name: string) {
  return useQuery({
    queryKey: keys.logs(name),
    queryFn: ({ signal }) => api.getLogs(name, signal),
    enabled: !!name,
  })
}

export function useLogContent(
  name: string,
  slug: string,
  logName: string,
) {
  return useQuery({
    queryKey: keys.logContent(name, slug, logName),
    queryFn: ({ signal }) => api.getLogContent(name, slug, logName, signal),
    enabled: !!name && !!slug && !!logName,
  })
}

export function useModels(name: string) {
  return useQuery({
    queryKey: keys.models(name),
    queryFn: ({ signal }) => api.getModels(name, signal),
    enabled: !!name,
  })
}

export function useAvailableModels() {
  return useQuery({
    queryKey: keys.availableModels,
    queryFn: ({ signal }) => api.getAvailableModels(signal),
  })
}

export function useProviders() {
  return useQuery({
    queryKey: keys.providers,
    queryFn: ({ signal }) => api.getProviders(signal),
  })
}

export function useBudgetConfig() {
  return useQuery({
    queryKey: keys.budgetConfig,
    queryFn: ({ signal }) => api.getBudgetConfig(signal),
  })
}

export function useRoadmap(name: string) {
  return useQuery({
    queryKey: keys.roadmap(name),
    queryFn: ({ signal }) => api.getRoadmap(name, signal),
    enabled: !!name,
  })
}

/* ── Mutations ── */

export function useCreateProject() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (v: { name: string; ecosystem: string; preamble: string; git: boolean }) =>
      api.createProject(v.name, v.ecosystem, v.preamble, v.git),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: keys.projects })
    },
  })
}

export function useRunPipeline() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (v: { name: string; verbose?: boolean }) =>
      api.runPipeline(v.name, v.verbose),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: keys.pipelineStatus })
    },
  })
}

export function useStopPipeline() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (name: string) => api.stopPipeline(name),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: keys.pipelineStatus })
    },
  })
}

export function useUpdateRoadmap() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (v: { name: string; data: Record<string, unknown> }) =>
      api.updateRoadmap(v.name, v.data),
    onSuccess: (_d, v) => {
      qc.invalidateQueries({ queryKey: keys.roadmap(v.name) })
    },
  })
}

export function useValidateRoadmap() {
  return useMutation({
    mutationFn: (name: string) => api.validateRoadmap(name),
  })
}

export function useGenerateRoadmap() {
  return useMutation({
    mutationFn: (v: { name: string; description: string; ecosystem: string }) =>
      api.generateRoadmap(v.name, v.description, v.ecosystem),
  })
}

export function useUpdateModel(name: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (v: { agent: string; model: string }) =>
      api.updateModel(name, v.agent, v.model),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: keys.models(name) })
      qc.invalidateQueries({ queryKey: keys.availableModels })
    },
  })
}

export function useUpdateBudgetConfig() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (data: BudgetConfig) => api.updateBudgetConfig(data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: keys.budgetConfig })
    },
  })
}

export function useRefreshModels() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: () => api.refreshAvailableModels(),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: keys.availableModels })
    },
  })
}

export function useProviderLogin() {
  return useMutation({
    mutationFn: (provider?: string) => api.providerLogin(provider),
  })
}

export function useProviderLogout() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: () => api.providerLogout(),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: keys.providers })
      qc.setQueryData(keys.availableModels, [])
    },
  })
}

export function useUpdateProjectBudget() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (v: { name: string; data: Record<string, unknown> }) =>
      api.updateProjectBudget(v.name, v.data),
    onSuccess: (_d, v) => {
      qc.invalidateQueries({ queryKey: keys.project(v.name) })
    },
  })
}

/** Invalidation helper for WS-triggered refreshes. */
export function useInvalidateProject() {
  const qc = useQueryClient()
  return (name?: string) => {
    qc.invalidateQueries({ queryKey: keys.projects })
    qc.invalidateQueries({ queryKey: keys.pipelineStatus })
    if (name) {
      qc.invalidateQueries({ queryKey: keys.project(name) })
      qc.invalidateQueries({ queryKey: keys.logs(name) })
    }
  }
}
