import type { LucideIcon } from 'lucide-react'
import { Dumbbell, Gamepad2, MoreHorizontal, Video } from 'lucide-react'
import type { Role } from '../types'

export type TabKey = 'live' | 'exercise' | 'control' | 'more'

interface Tab {
  key: TabKey
  label: string
  icon: LucideIcon
  operatorOnly?: boolean
}

const TABS: Tab[] = [
  { key: 'live', label: '라이브', icon: Video },
  { key: 'exercise', label: '운동', icon: Dumbbell },
  { key: 'control', label: '제어', icon: Gamepad2, operatorOnly: true },
  { key: 'more', label: '더보기', icon: MoreHorizontal },
]

interface NavProps {
  active: TabKey
  onSelect: (k: TabKey) => void
  role: Role
}

export function BottomNav({ active, onSelect, role }: NavProps) {
  const tabs = TABS.filter((t) => !t.operatorOnly || role === 'operator')
  return (
    <nav className="hcb-bottomnav">
      {tabs.map((t) => (
        <button
          key={t.key}
          className={`hcb-bottomnav__item ${active === t.key ? 'is-active' : ''}`}
          onClick={() => onSelect(t.key)}
        >
          <t.icon size={20} strokeWidth={active === t.key ? 2.4 : 1.9} />
          <span>{t.label}</span>
        </button>
      ))}
    </nav>
  )
}

export function SideNav({ active, onSelect, role }: NavProps) {
  const tabs = TABS.filter((t) => !t.operatorOnly || role === 'operator')
  return (
    <nav className="hcb-sidenav">
      <div className="hcb-sidenav__logo">
        <div className="hcb-sidenav__logo-mark">Q</div>
      </div>
      <div className="hcb-sidenav__items">
        {tabs.map((t) => (
          <button
            key={t.key}
            className={`hcb-sidenav__item ${active === t.key ? 'is-active' : ''}`}
            onClick={() => onSelect(t.key)}
            title={t.label}
          >
            <t.icon size={20} strokeWidth={active === t.key ? 2.4 : 1.9} />
            <span>{t.label}</span>
          </button>
        ))}
      </div>
      <div className="hcb-sidenav__footer">
        <span className="hcb-sidenav__role">{role === 'operator' ? '운영자' : '관람객'}</span>
      </div>
    </nav>
  )
}
