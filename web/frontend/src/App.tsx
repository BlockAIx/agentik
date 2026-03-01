import { ErrorBoundary } from "@/components/error-boundary"
import { TooltipProvider } from "@/components/ui/tooltip"
import { useWsStore } from "@/stores/ws-store"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import React, { Suspense, useEffect } from "react"
import { Route, Routes } from "react-router-dom"

const Dashboard = React.lazy(() =>
  import("@/components/dashboard").then((m) => ({ default: m.Dashboard })),
)
const ProjectView = React.lazy(() =>
  import("@/components/project-view").then((m) => ({ default: m.ProjectView })),
)
const SettingsPage = React.lazy(() =>
  import("@/components/settings-page").then((m) => ({ default: m.SettingsPage })),
)

const queryClient = new QueryClient({
  defaultOptions: { queries: { retry: 1, refetchOnWindowFocus: false } },
})

/** Opens the global WebSocket on mount. */
function WsConnector(): null {
  useEffect(() => useWsStore.getState()._init(), [])
  return null
}

function Loading(): React.JSX.Element {
  return (
    <div className="min-h-screen flex items-center justify-center bg-background">
      <div className="h-6 w-6 animate-spin rounded-full border-2 border-primary border-t-transparent" />
    </div>
  )
}

export default function App(): React.JSX.Element {
  return (
    <ErrorBoundary>
      <QueryClientProvider client={queryClient}>
        <TooltipProvider>
          <WsConnector />
          <Suspense fallback={<Loading />}>
            <Routes>
              <Route path="/" element={<Dashboard />} />
              <Route path="/project/:name/:tab?" element={<ProjectView />} />
              <Route path="/settings" element={<SettingsPage />} />
            </Routes>
          </Suspense>
        </TooltipProvider>
      </QueryClientProvider>
    </ErrorBoundary>
  )
}
