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
import './rehab.css'

export default function Rehab({
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
  const reps = counter?.reps ?? 0
  const target = session?.target_reps ?? 20
  const remain = Math.max(0, target - reps)
  const progress = target > 0 ? Math.min(1, reps / target) : 0
  const angle = stats?.angle_deg.used ?? null
  const threshold = counter?.thresholds_deg.down ?? (activeKind === 'pushup' ? 90 : 100)
  const deepEnough = angle != null && angle <= threshold
  const feedback = poseFeedback(stats)
  const { pulsing } = useRepPulse(reps)

  const connLabel =
    connection === 'online' ? '연결됨'
    : connection === 'offline' ? '연결 끊김'
    : connection === 'reconnecting' ? '다시 연결 중'
    : '연결 중'

  const trackLabel =
    stats?.ptz.state === 'in_frame' ? '자세 추적 중'
    : stats?.ptz.state === 'edge' ? '화면 가장자리'
    : '사람을 찾는 중'

  const exerciseLabel = activeKind === 'pushup' ? '푸시업' : '스쿼트'
  const coachDetail =
    deepEnough ? '목표 깊이에 도달했어요. 천천히 올라오세요.'
    : counter?.state === 'DOWN' ? `조금만 더 내려가면 ${threshold}° 목표에 도달해요.`
    : reps > 0 ? `${reps}회를 안정적으로 마쳤어요. 같은 속도를 유지해 보세요.`
    : '몸이 준비되면 첫 동작을 천천히 시작해 보세요.'

  const deviceLabel =
    connection === 'offline' ? '로봇과 연결이 끊겼어요'
    : (stats?.cpu_temp_c ?? 0) >= 78 || (stats?.cpu_percent ?? 0) >= 92
      ? '로봇이 잠시 열을 식히는 중이에요'
      : '로봇이 안정적으로 작동하고 있어요'

  const guarded = async (fn: () => Promise<unknown>) => {
    if (await control.requestControl()) await fn()
  }

  const runPrimaryAction = () => {
    if (session?.status === 'running') return guarded(api.sessionPause)
    if (session?.status === 'paused') return guarded(api.sessionResume)
    return guarded(() => api.sessionStart(target))
  }

  const primaryLabel =
    session?.status === 'running' ? '잠시 멈추기'
    : session?.status === 'paused' ? '운동 이어하기'
    : session?.status === 'finished' ? '한 번 더 시작하기'
    : '오늘 운동 시작하기'

  return (
    <div className="rh">
      <header className="rh__header">
        <button className="rh__brand" onClick={onOpenPicker} aria-label="디자인 선택">
          <span className="rh__brand-mark">U</span>
          <span>UNO <b>CARE</b></span>
        </button>
        <div className="rh__header-right">
          {demo && <span className="rh__demo">둘러보기</span>}
          <span className={`rh__connection rh__connection--${connection}`}>
            <i />
            {connLabel}
          </span>
          <button className="rh__switch" onClick={onOpenPicker}>디자인</button>
        </div>
      </header>

      <main className="rh__main">
        <section className="rh__coach">
          <div className="rh__coach-copy">
            <span className="rh__eyebrow">UNO 코치</span>
            <h1>{feedback.text}</h1>
            <p>{coachDetail}</p>
          </div>
          <div className="rh__coach-state">
            <span>오늘의 맞춤 운동</span>
            <b>{exerciseLabel} · {target}회</b>
          </div>
        </section>

        <section className="rh__layout">
          <div className="rh__camera-card">
            <div className="rh__camera-head">
              <div>
                <span className="rh__section-kicker">실시간 자세</span>
                <h2>내 움직임 확인하기</h2>
              </div>
              <span className={`rh__track rh__track--${stats?.ptz.state ?? 'lost'}`}>
                <i />
                {trackLabel}
              </span>
            </div>

            <div className="rh__camera" ref={cam.containerRef}>
              {cam.src && cam.live ? (
                <img className="rh__camera-img" src={cam.src} alt="실시간 카메라" />
              ) : demo ? (
                <DemoPose
                  className="rh__pose"
                  angle={angle}
                  sway={stats?.ptz.pan_deg != null ? stats.ptz.pan_deg / 24 : 0}
                  skeleton="rgba(19,88,66,.33)"
                  joint="#135842"
                  hot="#e26e3e"
                  hotActive={deepEnough}
                />
              ) : (
                <div className="rh__camera-empty">
                  <span />
                  카메라 화면을 준비하고 있어요
                </div>
              )}
              <div className="rh__camera-shade" />
              <div className="rh__angle">
                <span>무릎 각도</span>
                <b className="hcb-tnum">{angle == null ? '—' : `${Math.round(angle)}°`}</b>
              </div>
              <span className={`rh__quality${deepEnough ? ' is-good' : ''}`}>
                {deepEnough ? '목표 깊이 도달' : '동작 인식 중'}
              </span>
              <button className="rh__fullscreen" onClick={cam.toggleFullscreen} aria-label="전체 화면">
                <span /><span />
              </button>
            </div>

            <div className="rh__depth">
              <div className="rh__depth-copy">
                <span>동작 깊이</span>
                <b>{deepEnough ? '충분해요' : '천천히 내려가세요'}</b>
              </div>
              <div className="rh__depth-track">
                <i style={{ width: `${Math.max(4, Math.min(100, ((170 - (angle ?? 170)) / (170 - threshold)) * 100))}%` }} />
                <span style={{ left: '84%' }} />
              </div>
              <small>표시는 권장 범위이며 통증이 느껴지면 즉시 멈추세요.</small>
            </div>
          </div>

          <aside className="rh__side">
            <section className="rh__next">
              <span className="rh__section-kicker">
                {session?.status === 'running' ? '운동 진행 중' : '다음 운동'}
              </span>
              <div className="rh__next-title">
                <div>
                  <h2>{exerciseLabel}</h2>
                  <p>{session?.status === 'running' ? `${remain}회 남았어요` : '내 몸에 맞춘 가벼운 루틴'}</p>
                </div>
                <div className={`rh__rep${pulsing ? ' is-pulse' : ''}`}>
                  <strong className="hcb-tnum">{reps}</strong>
                  <span>/ {target}회</span>
                </div>
              </div>

              <div className="rh__progress" aria-label={`진행률 ${Math.round(progress * 100)}퍼센트`}>
                <i style={{ width: `${progress * 100}%` }} />
              </div>

              {isOperator ? (
                <button
                  className={`rh__primary${session?.status === 'running' ? ' rh__primary--pause' : ''}`}
                  onClick={runPrimaryAction}
                >
                  <span>{session?.status === 'running' ? 'Ⅱ' : '▶'}</span>
                  {primaryLabel}
                </button>
              ) : (
                <div className="rh__viewer-action">
                  <span>{session?.status === 'running' ? '운동이 진행 중이에요' : '운영자가 운동을 준비하고 있어요'}</span>
                </div>
              )}

              {isOperator && session?.status !== 'idle' && (
                <button className="rh__text-button" onClick={() => guarded(api.sessionFinish)}>
                  운동 마무리하기
                </button>
              )}
            </section>

            <section className="rh__summary">
              <div>
                <span>운동 시간</span>
                <b className="hcb-tnum">{fmtClock(session?.elapsed_ms ?? 0)}</b>
              </div>
              <div>
                <span>완료 횟수</span>
                <b className="hcb-tnum">{reps}<em>회</em></b>
              </div>
              <div>
                <span>현재 깊이</span>
                <b className="hcb-tnum">{angle == null ? '—' : Math.round(angle)}<em>°</em></b>
              </div>
            </section>

            <details className="rh__details">
              <summary>
                <div>
                  <span className="rh__section-kicker">기기 상태</span>
                  <b>{deviceLabel}</b>
                </div>
                <i />
              </summary>
              <div className="rh__device-grid">
                <Metric label="처리 속도" value={fmtNum(stats?.fps, 1)} unit="fps" />
                <Metric label="프로세서" value={fmtNum(stats?.cpu_percent, 0)} unit="%" />
                <Metric label="온도" value={fmtNum(stats?.cpu_temp_c, 0)} unit="°C" />
                <Metric label="함께 보는 사람" value={String(stats?.app.viewer_count ?? 0)} unit="명" />
              </div>

              {isOperator && (
                <div className="rh__operator">
                  <div className="rh__operator-row">
                    <div>
                      <span>자동 추적</span>
                      <small>카메라가 움직임을 따라갑니다</small>
                    </div>
                    <button
                      className={`rh__toggle${stats?.ptz.auto_track_enabled ? ' is-on' : ''}`}
                      role="switch"
                      aria-checked={!!stats?.ptz.auto_track_enabled}
                      onClick={() => guarded(() => api.sendPtz('auto_track', { enabled: !stats?.ptz.auto_track_enabled }))}
                    >
                      <i />
                    </button>
                  </div>
                  <div className="rh__pad">
                    <PadButton label="위" className="rh__pad-up" onFire={() => guarded(() => api.sendPtz('tilt', { delta_deg: -2 }))}>↑</PadButton>
                    <PadButton label="왼쪽" className="rh__pad-left" onFire={() => guarded(() => api.sendPtz('pan', { delta_deg: -2 }))}>←</PadButton>
                    <button className="rh__pad-center" onClick={() => guarded(() => api.sendPtz('center'))}>중앙</button>
                    <PadButton label="오른쪽" className="rh__pad-right" onFire={() => guarded(() => api.sendPtz('pan', { delta_deg: 2 }))}>→</PadButton>
                    <PadButton label="아래" className="rh__pad-down" onFire={() => guarded(() => api.sendPtz('tilt', { delta_deg: 2 }))}>↓</PadButton>
                  </div>
                </div>
              )}
            </details>
          </aside>
        </section>

        <footer className="rh__footer">
          이 화면의 자세 안내는 운동 보조 정보입니다. 통증이나 어지럼증이 느껴지면 운동을 멈추고 전문가와 상담하세요.
        </footer>
      </main>

      {control.pinModalOpen && (
        <OperatorPinModal
          busy={control.pinBusy}
          error={control.pinError}
          onSubmit={control.submitPin}
          onCancel={control.cancelPinModal}
        />
      )}
    </div>
  )
}

function Metric({ label, value, unit }: { label: string; value: string; unit: string }) {
  return (
    <div className="rh__metric">
      <span>{label}</span>
      <b className="hcb-tnum">{value}<em>{unit}</em></b>
    </div>
  )
}

function PadButton({
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
