import { useState } from 'react'
import { Minus, Pause, Play, Plus, RotateCcw, Square } from 'lucide-react'
import { ProgressRing } from '../components/ProgressRing'
import { PinModal } from '../components/PinModal'
import { QrPanel } from '../components/QrPanel'
import { useOperatorControl } from '../hooks/useOperatorControl'
import { poseFeedback } from '../lib/feedback'
import * as api from '../api'
import type { ExerciseMode, Role, Stats } from '../types'

const MODES: { key: ExerciseMode; label: string }[] = [
  { key: 'auto', label: 'Auto' },
  { key: 'squat', label: 'Squat' },
  { key: 'pushup', label: 'Push-up' },
]

function fmtTime(ms: number) {
  const s = Math.floor(ms / 1000)
  const mm = String(Math.floor(s / 60)).padStart(2, '0')
  const ss = String(s % 60).padStart(2, '0')
  return `${mm}:${ss}`
}

export function ExerciseScreen({ stats, role }: { stats: Stats | null; role: Role }) {
  const control = useOperatorControl(role, stats?.app.control)
  const [target, setTarget] = useState(20)
  const [confirmReset, setConfirmReset] = useState(false)
  const canOperate = role === 'operator'

  const session = stats?.app.session
  const status = session?.status ?? 'idle'
  const mode = session?.mode ?? 'auto'
  const reps = (stats?.squat.reps ?? 0) + (stats?.pushup.reps ?? 0)
  const targetReps = session?.target_reps ?? target
  const fb = poseFeedback(stats)

  const guarded = async (fn: () => Promise<unknown>) => {
    const ok = await control.requestControl()
    if (ok) await fn()
  }

  const handleMode = (m: ExerciseMode) => guarded(() => api.setMode(m))
  const handleStart = () => guarded(() => api.sessionStart(target))
  const handlePause = () => guarded(() => api.sessionPause())
  const handleResume = () => guarded(() => api.sessionResume())
  const handleFinish = () => guarded(() => api.sessionFinish())
  const handleReset = () => guarded(() => api.sessionReset()).then(() => setConfirmReset(false))

  return (
    <div className="hcb-screen hcb-exercise">
      <div className="hcb-segmented">
        {MODES.map((m) => (
          <button
            key={m.key}
            className={mode === m.key ? 'is-active' : ''}
            disabled={!canOperate || status === 'running'}
            onClick={() => handleMode(m.key)}
          >
            {m.label}
          </button>
        ))}
      </div>

      {status === 'idle' && (
        <div className="hcb-card hcb-exercise__setup">
          <div className="hcb-exercise__setup-label">목표 횟수</div>
          <div className="hcb-exercise__stepper">
            <button className="hcb-btn hcb-btn--soft" disabled={!canOperate} onClick={() => setTarget((t) => Math.max(5, t - 5))}>
              <Minus size={16} />
            </button>
            <span>{target}회</span>
            <button className="hcb-btn hcb-btn--soft" disabled={!canOperate} onClick={() => setTarget((t) => t + 5)}>
              <Plus size={16} />
            </button>
          </div>
          {canOperate ? (
            <button className="hcb-btn hcb-btn--primary" style={{ width: '100%' }} onClick={handleStart}>
              <Play size={16} /> 세션 시작
            </button>
          ) : (
            <p className="hcb-muted">운영자가 세션을 시작하면 여기에 진행 상황이 표시됩니다.</p>
          )}
        </div>
      )}

      {(status === 'running' || status === 'paused') && (
        <>
          <div className="hcb-card hcb-exercise__progress">
            <ProgressRing value={reps} target={targetReps} label={status === 'paused' ? '일시정지' : '진행 중'} />
            <div className="hcb-exercise__meta">
              <div>
                <span className="hcb-muted">시간</span>
                <strong>{fmtTime(session?.elapsed_ms ?? 0)}</strong>
              </div>
              <div>
                <span className="hcb-muted">각도</span>
                <strong>{stats?.angle_deg.used != null ? `${Math.round(stats.angle_deg.used)}°` : '—'}</strong>
              </div>
            </div>
          </div>

          <div className={`hcb-feedback hcb-card hcb-feedback--${fb.tone}`}>{fb.text}</div>

          {canOperate && (
            <div className="hcb-exercise__actions">
              {status === 'running' ? (
                <button className="hcb-btn hcb-btn--soft" onClick={handlePause}>
                  <Pause size={16} /> 일시정지
                </button>
              ) : (
                <button className="hcb-btn hcb-btn--soft" onClick={handleResume}>
                  <Play size={16} /> 재개
                </button>
              )}
              <button className="hcb-btn hcb-btn--warning" onClick={handleFinish}>
                <Square size={16} /> 종료
              </button>
            </div>
          )}
        </>
      )}

      {status === 'finished' && session?.last_finished && (
        <div className="hcb-card hcb-result">
          <h3>세션 결과</h3>
          <div className="hcb-result__grid">
            <div>
              <span className="hcb-muted">총 시간</span>
              <strong>{fmtTime(session.last_finished.elapsed_ms)}</strong>
            </div>
            <div>
              <span className="hcb-muted">Squat</span>
              <strong>{session.last_finished.squat_reps}회</strong>
            </div>
            <div>
              <span className="hcb-muted">Pushup</span>
              <strong>{session.last_finished.pushup_reps}회</strong>
            </div>
            <div>
              <span className="hcb-muted">평균 FPS</span>
              <strong>{session.last_finished.avg_fps ?? '—'}</strong>
            </div>
          </div>
          {canOperate && (
            <button className="hcb-btn hcb-btn--primary" style={{ width: '100%' }} onClick={handleStart}>
              <RotateCcw size={16} /> 다시 시작
            </button>
          )}
          <QrPanel isOperator={false} />
        </div>
      )}

      {canOperate && status !== 'idle' && (
        <button className="hcb-link-danger" onClick={() => setConfirmReset(true)}>
          카운트 리셋
        </button>
      )}

      {confirmReset && (
        <div className="hcb-modal-backdrop" onClick={() => setConfirmReset(false)}>
          <div className="hcb-modal" onClick={(e) => e.stopPropagation()}>
            <h3>카운트를 리셋할까요?</h3>
            <p>현재 진행 중인 세션의 횟수가 모두 초기화됩니다.</p>
            <div className="hcb-modal__actions">
              <button className="hcb-btn hcb-btn--soft" onClick={() => setConfirmReset(false)}>
                취소
              </button>
              <button className="hcb-btn hcb-btn--danger" onClick={handleReset}>
                리셋
              </button>
            </div>
          </div>
        </div>
      )}

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
