import { DemoPose } from '../../components/DemoPose'
import { OperatorPinModal } from '../../components/OperatorPinModal'
import { useMjpeg } from '../../hooks/useMjpeg'
import { useOperatorControl } from '../../hooks/useOperatorControl'
import { usePressRepeat } from '../../hooks/usePressRepeat'
import { useRepPulse } from '../../hooks/useRepPulse'
import { fmtClock, fmtNum } from '../../lib/format'
import { poseFeedback } from '../../lib/feedback'
import * as api from '../../api'
import type { VersionScreenProps } from '../registry'
import './live-session.css'

export default function LiveSession({
  stats,
  connection,
  role,
  demo,
  onOpenPicker,
}: VersionScreenProps) {
  const cam = useMjpeg(connection, demo)
  const control = useOperatorControl(role, stats?.app.control)
  const session = stats?.app.session
  const isOperator = role === 'operator'

  const activeKind = stats?.exercise_active === 'pushup' ? 'pushup' : 'squat'
  const counter = activeKind === 'pushup' ? stats?.pushup : stats?.squat
  const exerciseLabel = activeKind === 'pushup' ? '푸시업' : '스쿼트'
  const reps = counter?.reps ?? 0
  const target = session?.target_reps ?? 20
  const remaining = Math.max(0, target - reps)
  const progress = target > 0 ? Math.min(1, reps / target) : 0
  const angle = stats?.angle_deg.used ?? null
  const threshold = counter?.thresholds_deg.down ?? (activeKind === 'pushup' ? 90 : 100)
  const deepEnough = angle != null && angle <= threshold
  const feedback = poseFeedback(stats)
  const { pulsing } = useRepPulse(reps)

  const trackingText =
    stats?.ptz.state === 'in_frame' ? '자세 추적'
    : stats?.ptz.state === 'edge' ? '위치 조정 중'
    : '사람 찾는 중'

  const cue =
    deepEnough ? '좋아요, 그대로 올라오세요'
    : counter?.state === 'DOWN' ? '호흡하며 조금 더 내려가세요'
    : reps >= target ? '오늘 목표를 모두 마쳤어요'
    : reps > 0 ? '좋은 리듬이에요, 그대로 이어가세요'
    : feedback.text

  const cueDetail =
    angle == null ? '카메라가 자세를 인식하면 안내를 시작합니다'
    : deepEnough ? `현재 ${Math.round(angle)}° · 목표 깊이에 도달했어요`
    : `현재 ${Math.round(angle)}° · 목표 ${threshold}° 이하`

  const guarded = async (fn: () => Promise<unknown>) => {
    if (await control.requestControl()) await fn()
  }

  const runPrimaryAction = () => {
    if (session?.status === 'running') return guarded(api.sessionPause)
    if (session?.status === 'paused') return guarded(api.sessionResume)
    return guarded(() => api.sessionStart(target))
  }

  const primaryLabel =
    session?.status === 'running' ? '일시정지'
    : session?.status === 'paused' ? '운동 계속하기'
    : session?.status === 'finished' ? '한 번 더 시작'
    : '운동 시작'

  return (
    <div className="ls">
      <header className="ls__header">
        <button className="ls__brand" onClick={onOpenPicker}>
          <span>UNO</span>
          <b>LIVE</b>
        </button>
        <div className="ls__workout">
          <span>{exerciseLabel}</span>
          <i />
          <span>세트 1</span>
        </div>
        <div className="ls__header-actions">
          {demo && <span className="ls__demo">DEMO</span>}
          <span className={`ls__online ls__online--${connection}`}>
            <i />
            {connection === 'online' ? '연결됨' : connection === 'offline' ? '오프라인' : '연결 중'}
          </span>
          <button className="ls__design" onClick={onOpenPicker}>디자인</button>
        </div>
      </header>

      <main className="ls__main">
        <section className="ls__stage" ref={cam.containerRef}>
          {cam.src && cam.live ? (
            <img className="ls__stage-img" src={cam.src} alt="실시간 운동 카메라" />
          ) : demo ? (
            <DemoPose
              className="ls__pose"
              angle={angle}
              sway={stats?.ptz.pan_deg != null ? stats.ptz.pan_deg / 24 : 0}
              skeleton="rgba(239,246,241,.76)"
              joint="#f7faf8"
              hot="#b9ff35"
              hotActive={deepEnough}
            />
          ) : (
            <div className="ls__stage-empty">
              <div className="ls__stage-empty-mark"><i /><i /><i /></div>
              <b>카메라를 준비하고 있어요</b>
              <span>사람이 보이면 자세 추적을 시작합니다</span>
            </div>
          )}

          <div className="ls__vignette" />

          <div className="ls__live-badge">
            <i />
            LIVE · {trackingText}
          </div>

          <button className="ls__fullscreen" onClick={cam.toggleFullscreen} aria-label="전체 화면">
            <i /><i />
          </button>

          <div className={`ls__count${pulsing ? ' is-pulse' : ''}`}>
            <strong className="hcb-tnum">{reps}</strong>
            <span>/ {target}회</span>
          </div>

          <div className="ls__stage-metrics">
            <span>각도 <b className="hcb-tnum">{angle == null ? '—' : `${Math.round(angle)}°`}</b></span>
            <span>남은 횟수 <b className="hcb-tnum">{remaining}</b></span>
          </div>
        </section>

        <aside className="ls__panel">
          <section className="ls__cue">
            <span className={`ls__cue-label${deepEnough ? ' is-good' : ''}`}>
              {deepEnough ? '목표 범위 도달' : '실시간 코칭'}
            </span>
            <h1>{cue}</h1>
            <p>{cueDetail}</p>
          </section>

          <section className="ls__progress-card">
            <div className="ls__progress-head">
              <span>세트 진행률</span>
              <b className="hcb-tnum">{Math.round(progress * 100)}%</b>
            </div>
            <div className="ls__progress">
              <i style={{ width: `${progress * 100}%` }} />
            </div>
            <div className="ls__numbers">
              <div><span>시간</span><b className="hcb-tnum">{fmtClock(session?.elapsed_ms ?? 0)}</b></div>
              <div><span>정확도</span><b>{deepEnough ? '좋음' : '추적 중'}</b></div>
              <div><span>남은 수</span><b className="hcb-tnum">{remaining}</b></div>
            </div>
          </section>

          {isOperator ? (
            <div className="ls__actions">
              <button
                className={`ls__primary${session?.status === 'running' ? ' ls__primary--pause' : ''}`}
                onClick={runPrimaryAction}
              >
                <span>{session?.status === 'running' ? 'Ⅱ' : '▶'}</span>
                {primaryLabel}
              </button>
              {session?.status !== 'idle' && (
                <button className="ls__finish" onClick={() => guarded(api.sessionFinish)}>세션 종료</button>
              )}
            </div>
          ) : (
            <div className="ls__viewer">
              <i />
              {session?.status === 'running' ? '운동 세션이 진행 중입니다' : '운영자가 세션을 준비하고 있습니다'}
            </div>
          )}

          <details className="ls__details">
            <summary>
              <span>기기 및 카메라 제어</span>
              <i />
            </summary>
            <div className="ls__telemetry">
              <div><span>처리</span><b className="hcb-tnum">{fmtNum(stats?.fps, 1)} fps</b></div>
              <div><span>CPU</span><b className="hcb-tnum">{fmtNum(stats?.cpu_percent, 0)}%</b></div>
              <div><span>온도</span><b className="hcb-tnum">{fmtNum(stats?.cpu_temp_c, 0)}°C</b></div>
            </div>

            {isOperator && (
              <>
                <div className="ls__auto">
                  <div>
                    <span>자동 추적</span>
                    <small>카메라가 사용자를 따라갑니다</small>
                  </div>
                  <button
                    className={`ls__toggle${stats?.ptz.auto_track_enabled ? ' is-on' : ''}`}
                    role="switch"
                    aria-checked={!!stats?.ptz.auto_track_enabled}
                    onClick={() => guarded(() => api.sendPtz('auto_track', { enabled: !stats?.ptz.auto_track_enabled }))}
                  >
                    <i />
                  </button>
                </div>
                <div className="ls__pad">
                  <Pad label="위" className="ls__pad-up" onFire={() => guarded(() => api.sendPtz('tilt', { delta_deg: -2 }))}>↑</Pad>
                  <Pad label="왼쪽" className="ls__pad-left" onFire={() => guarded(() => api.sendPtz('pan', { delta_deg: -2 }))}>←</Pad>
                  <button className="ls__pad-center" onClick={() => guarded(() => api.sendPtz('center'))}>●</button>
                  <Pad label="오른쪽" className="ls__pad-right" onFire={() => guarded(() => api.sendPtz('pan', { delta_deg: 2 }))}>→</Pad>
                  <Pad label="아래" className="ls__pad-down" onFire={() => guarded(() => api.sendPtz('tilt', { delta_deg: 2 }))}>↓</Pad>
                </div>
              </>
            )}
          </details>

          <p className="ls__safety">통증이나 어지럼증이 느껴지면 즉시 운동을 멈추세요.</p>
        </aside>
      </main>

      {control.pinModalOpen && (
        <OperatorPinModal
          busy={control.pinBusy}
          error={control.pinError}
          tone="dark"
          onSubmit={control.submitPin}
          onCancel={control.cancelPinModal}
        />
      )}
    </div>
  )
}

function Pad({
  label,
  className,
  children,
  onFire,
}: {
  label: string
  className: string
  children: string
  onFire: () => void
}) {
  const press = usePressRepeat(onFire)
  return <button className={className} aria-label={label} {...press}>{children}</button>
}
