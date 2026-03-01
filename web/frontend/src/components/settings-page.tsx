/** Global settings page — provider auth, budget limits, token prices. */
import { Layout } from "@/components/layout"
import { Providers } from "@/components/providers"
import { GlobalConfig } from "@/components/settings"
import { Settings2 } from "lucide-react"

export function SettingsPage(): React.JSX.Element {
  return (
    <Layout
      backTo="/"
      backLabel="Dashboard"
      title="Global Settings"
      badge={<Settings2 className="h-5 w-5 text-muted-foreground" />}
    >
      <div className="space-y-6">
        <Providers />
        <GlobalConfig />
      </div>
    </Layout>
  )
}
