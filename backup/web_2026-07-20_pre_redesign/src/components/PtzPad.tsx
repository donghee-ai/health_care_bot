import { ChevronDown, ChevronLeft, ChevronRight, ChevronUp, Crosshair } from 'lucide-react'

interface PtzPadProps {
  step: number
  onStep: (v: number) => void
  onMove: (axis: 'pan' | 'tilt', delta: number) => void
  onCenter: () => void
  autoTrack: boolean
  onAutoTrack: (v: boolean) => void
  disabled?: boolean
}

const STEPS = [2, 5, 10]

export function PtzPad({ step, onStep, onMove, onCenter, autoTrack, onAutoTrack, disabled }: PtzPadProps) {
  return (
    <div className={`hcb-ptz ${disabled ? 'is-disabled' : ''}`}>
      <div className="hcb-ptz__pad">
        <button className="hcb-ptz__btn hcb-ptz__btn--up" disabled={disabled} onClick={() => onMove('tilt', step)}>
          <ChevronUp size={22} />
        </button>
        <button className="hcb-ptz__btn hcb-ptz__btn--left" disabled={disabled} onClick={() => onMove('pan', step)}>
          <ChevronLeft size={22} />
        </button>
        <button className="hcb-ptz__btn hcb-ptz__btn--center" disabled={disabled} onClick={onCenter}>
          <Crosshair size={20} />
        </button>
        <button className="hcb-ptz__btn hcb-ptz__btn--right" disabled={disabled} onClick={() => onMove('pan', -step)}>
          <ChevronRight size={22} />
        </button>
        <button className="hcb-ptz__btn hcb-ptz__btn--down" disabled={disabled} onClick={() => onMove('tilt', -step)}>
          <ChevronDown size={22} />
        </button>
      </div>

      <div className="hcb-ptz__row">
        <span className="hcb-ptz__row-label">스텝 크기</span>
        <div className="hcb-segmented" style={{ maxWidth: 200 }}>
          {STEPS.map((s) => (
            <button key={s} className={s === step ? 'is-active' : ''} disabled={disabled} onClick={() => onStep(s)}>
              {s}°
            </button>
          ))}
        </div>
      </div>

      <div className="hcb-ptz__row">
        <span className="hcb-ptz__row-label">자동 추적</span>
        <button
          className={`hcb-toggle ${autoTrack ? 'is-on' : ''}`}
          disabled={disabled}
          onClick={() => onAutoTrack(!autoTrack)}
          aria-pressed={autoTrack}
        >
          <span className="hcb-toggle__knob" />
        </button>
      </div>

      <button className="hcb-btn hcb-btn--soft" disabled={disabled} onClick={onCenter} style={{ width: '100%' }}>
        중앙으로 복귀
      </button>
    </div>
  )
}
