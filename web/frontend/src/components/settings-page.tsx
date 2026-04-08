/** Global settings page — provider auth, budget limits, token prices. */

import { Settings2 } from 'lucide-react'
import { Layout } from '@/components/layout'
import { Providers } from '@/components/providers'
import { GlobalConfig } from '@/components/settings'

export function SettingsPage(): React.JSX.Element {
  return (
    <Layout
      historyBack
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
