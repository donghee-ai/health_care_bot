import { useEffect, useMemo, useState } from 'react'
import { Users } from 'lucide-react'
import { BottomNav, SideNav, type TabKey } from './components/NavBar'
import { ConnectionBadge } from './components/ConnectionBadge'
import { ThemeToggle } from './components/ThemeToggle'
import { LiveScreen } from './screens/LiveScreen'
import { ExerciseScreen } from './screens/ExerciseScreen'
import { CameraControlScreen } from './screens/CameraControlScreen'
import { MoreScreen } from './screens/MoreScreen'
import { useStats } from './hooks/useStats'
import { useIsDesktop } from './hooks/useMediaQuery'
import { useTheme } from './hooks/useTheme'
import type { Role } from './types'

function resolveRole(): Role {
  const params = new URLSearchParams(window.location.search)
  return params.get('role') === 'operator' ? 'operator' : 'viewer'
}

export default function App() {
  const role = useMemo(resolveRole, [])
  const isDesktop = useIsDesktop()
  const [tab, setTab] = useState<TabKey>('live')
  const { stats, connection } = useStats()
  const { theme, setTheme } = useTheme()

  useEffect(() => {
    if (role !== 'operator' && tab === 'control') setTab('live')
  }, [role, tab])

  const screen = (() => {
    switch (tab) {
      case 'live':
        return <LiveScreen stats={stats} connection={connection} />
      case 'exercise':
        return <ExerciseScreen stats={stats} role={role} />
      case 'control':
        return role === 'operator' ? (
          <CameraControlScreen stats={stats} connection={connection} role={role} />
        ) : (
          <LiveScreen stats={stats} connection={connection} />
        )
      case 'more':
        return <MoreScreen stats={stats} connection={connection} role={role} />
    }
  })()

  return (
    <div className={`hcb-app ${isDesktop ? 'is-desktop' : 'is-mobile'}`}>
      {isDesktop && <SideNav active={tab} onSelect={setTab} role={role} />}

      <div className="hcb-app__main">
        <header className="hcb-header">
          <div className="hcb-header__brand">
            <span className="hcb-header__mark">Q</span>
            Health Care Bot
          </div>
          <div className="hcb-header__right">
            <ThemeToggle theme={theme} onChange={setTheme} />
            {stats && (
              <span className="hcb-badge hcb-badge--neutral">
                <Users size={12} /> {stats.app.viewer_count}
              </span>
            )}
            <ConnectionBadge state={connection} />
          </div>
        </header>

        <main className="hcb-app__content hcb-scrollbar-none">{screen}</main>
      </div>

      {!isDesktop && <BottomNav active={tab} onSelect={setTab} role={role} />}
    </div>
  )
}
