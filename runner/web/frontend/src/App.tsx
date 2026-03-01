import { Dashboard } from "@/components/dashboard"
import { ProjectView } from "@/components/project-view"
import { SettingsPage } from "@/components/settings-page"
import { TooltipProvider } from "@/components/ui/tooltip"
import { Route, Routes } from "react-router-dom"

export default function App(): React.JSX.Element {
  return (
    <TooltipProvider>
      <Routes>
        <Route path="/" element={<Dashboard />} />
        <Route path="/project/:name" element={<ProjectView />} />
        <Route path="/settings" element={<SettingsPage />} />
      </Routes>
    </TooltipProvider>
  )
}
