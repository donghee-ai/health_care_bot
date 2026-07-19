import { useState } from 'react'
import { ShieldCheck, ShieldAlert } from 'lucide-react'
import { LiveCamera } from '../components/LiveCamera'
import { PtzPad } from '../components/PtzPad'
import { PinModal } from '../components/PinModal'
import { useOperatorControl } from '../hooks/useOperatorControl'
import * as api from '../api'
import type { ConnectionState } from '../hooks/useStats'
import type { Role, Stats } from '../types'

export function CameraControlScreen({
  stats,
  connection,
  role,
}: {
  stats: Stats | null
  connection: ConnectionState
  role: Role
}) {
  const control = useOperatorControl(role, stats?.app.control)
  const [step, setStep] = useState(5)
  const autoTrack = stats?.ptz.auto_track_enabled ?? true

  const guarded = async (fn: () => Promise<unknown>) => {
    const ok = await control.requestControl()
    if (ok) await fn()
  }

  const onMove = (axis: 'pan' | 'tilt', delta: number) =>
    guarded(() => api.sendPtz(axis, { delta_deg: delta }))
  const onCenter = () => guarded(() => api.sendPtz('center'))
  const onAutoTrack = (v: boolean) => guarded(() => api.sendPtz('auto_track', { enabled: v }))

  return (
    <div className="hcb-screen hcb-control">
      <div className="hcb-control__cam">
        <div className="hcb-control__banner">
          {control.iAmHolder ? (
            <span className="hcb-badge hcb-badge--success">
              <ShieldCheck size={13} /> 운영자 모드
            </span>
          ) : control.lockedByOther ? (
            <span className="hcb-badge hcb-badge--warning">
              <ShieldAlert size={13} /> 다른 기기가 제어 중
            </span>
          ) : (
            <span className="hcb-badge hcb-badge--neutral">
              <ShieldAlert size={13} /> 제어권 없음 — 조작 시 PIN 필요
            </span>
          )}
        </div>

        <LiveCamera connection={connection} showGuide aspect="4 / 3" />
      </div>

      <div className="hcb-card hcb-control__panel">
        <PtzPad
          step={step}
          onStep={setStep}
          onMove={onMove}
          onCenter={onCenter}
          autoTrack={autoTrack}
          onAutoTrack={onAutoTrack}
          disabled={control.lockedByOther}
        />
      </div>

      <PinModal
        open={control.pinModalOpen}
        busy={control.pinBusy}
        error={control.pinError}
        onSubmit={control.submitPin}
        onCancel={control.cancelPinModal}
      />
    </div>
  )
}
