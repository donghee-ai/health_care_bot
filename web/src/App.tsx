import { lazy, Suspense, useCallback, useEffect, useMemo, useState } from 'react'
import { useStats } from './hooks/useStats'
import { useVersion } from './hooks/useVersion'
import { VersionPicker } from './shell/VersionPicker'
import { VERSIONS, type VersionProps } from './versions/registry'
import type { Role } from './types'
import './base.css'
import './shell/picker.css'

// 시안별로 CSS까지 통째로 갈리기 때문에 lazy로 나눈다. 지금은 후보가
// CALM 하나뿐이지만, 시안이 여러 개일 때 서로의 CSS가 한꺼번에 들어와
// 덮어쓰는 사고를 막던 구조를 그대로 유지한다 — 후보를 다시 늘릴 때
// 바로 쓰기 위함이다.
const Calm = lazy(() => import('./versions/calm/Calm'))
const Rehab = lazy(() => import('./versions/rehab/Rehab'))
const LiveSession = lazy(() => import('./versions/session/LiveSession'))
const Pulse = lazy(() => import('./versions/pulse/Pulse'))
const Aurora = lazy(() => import('./versions/aurora/Aurora'))
const Core = lazy(() => import('./versions/core/Core'))

function resolveRole(): Role {
  return new URLSearchParams(window.location.search).get('role') === 'operator'
    ? 'operator'
    : 'viewer'
}

export default function App() {
  const role = useMemo(resolveRole, [])
  const { stats, connection, demo } = useStats()
  const { version, setVersion } = useVersion()
  const [pickerOpen, setPickerOpen] = useState(false)

  // 시안 전환 단축키. 지금은 후보가 하나라 숫자 키 1만 유효하지만,
  // 후보를 다시 늘리면 VERSIONS 순서대로 2·3·4가 자동으로 붙는다.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.metaKey || e.ctrlKey || e.altKey) return
      const target = e.target as HTMLElement | null
      if (target && /^(INPUT|TEXTAREA)$/.test(target.tagName)) return
      const idx = Number(e.key) - 1
      if (idx >= 0 && idx < VERSIONS.length) setVersion(VERSIONS[idx].id)
      if (e.key.toLowerCase() === 'v') setPickerOpen((o) => !o)
      if (e.key === 'Escape') setPickerOpen(false)
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [setVersion])

  const openPicker = useCallback(() => setPickerOpen(true), [])

  const props: VersionProps = { stats, connection, role, demo }

  return (
    <>
      <Suspense fallback={<Booting />}>
        {version === 'calm' && <Calm {...props} onOpenPicker={openPicker} />}
        {version === 'pulse' && <Pulse {...props} onOpenPicker={openPicker} />}
        {version === 'aurora' && <Aurora {...props} onOpenPicker={openPicker} />}
        {version === 'core' && <Core {...props} onOpenPicker={openPicker} />}
        {version === 'rehab' && <Rehab {...props} onOpenPicker={openPicker} />}
        {version === 'session' && <LiveSession {...props} onOpenPicker={openPicker} />}
      </Suspense>

      <VersionPicker
        open={pickerOpen}
        current={version}
        onSelect={(v) => {
          setVersion(v)
          setPickerOpen(false)
        }}
        onClose={() => setPickerOpen(false)}
      />
    </>
  )
}

/** 시안 청크를 받아오는 짧은 순간. 배경색이 시안마다 달라서
    흰 화면이 번쩍이지 않도록 중립 무채색으로 덮는다. */
function Booting() {
  return <div style={{ height: '100%', background: '#111', color: '#666' }} />
}
