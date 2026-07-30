import { useState } from 'react'
import { useMjpeg } from '../../hooks/useMjpeg'
import { useOperatorControl } from '../../hooks/useOperatorControl'
import { useRepPulse } from '../../hooks/useRepPulse'
import { usePressRepeat } from '../../hooks/usePressRepeat'
import { DemoPose } from '../../components/DemoPose'
import { poseFeedback } from '../../lib/feedback'
import { CONNECTION_LABEL, fmtClock, fmtNum, TRACK_LABEL } from '../../lib/format'
import * as api from '../../api'
import type { VersionScreenProps } from '../registry'
import './calm.css'

/**
 * CALM — 숨쉬는 코치.
 *
 * 전제: 이 앱은 사람을 다그치지 않는다. Gentler Streak이 애플 디자인
 * 어워드를 받은 이유가 "못 채운 날을 실패로 만들지 않는 설계"였다는
 * 점을 그대로 가져왔다.
 *
 * 다른 세 시안과의 차이:
 * - 숫자를 크게 쓰되 링 안에 넣어 '얼마나 남았나'를 먼저 보게 한다.
 *   INSTRUMENT/STADIUM이 값을 보여준다면 여기는 상태를 보여준다.
 * - 장치 상태는 숫자를 앞세우지 않고 "괜찮음/지켜보는 중"으로 번역해
 *   먼저 말한다. 정확한 수치는 그 아래 작게 둔다.
 * - 모서리를 크게 굴리고 면을 부드럽게 띄운다. 앞의 셋이 전부
 *   각진 화면이라, 여기서만 촉감을 만든다.
 */
export default function Calm({ stats, connection, role, demo, onOpenPicker }: VersionScreenProps) {
  const cam = useMjpeg(connection, demo)
  const control = useOperatorControl(role, stats?.app.control)
  const isOperator = role === 'operator'

  const squat = stats?.squat
  const reps = squat?.reps ?? 0
  const session = stats?.app.session
  const target = session?.target_reps ?? 20
  const { pulsing } = useRepPulse(reps)
  const angle = stats?.angle_deg.used ?? null
  const fb = poseFeedback(stats)

  const conn = CONNECTION_LABEL[connection]
  const track = stats ? TRACK_LABEL[stats.ptz.state] ?? TRACK_LABEL.lost : null

  const down = squat?.thresholds_deg.down ?? 100
  const up = squat?.thresholds_deg.up ?? 150
  const floor = down - 30
  const depth = angle == null ? 0 : Math.max(0, Math.min(100, ((up - angle) / (up - floor)) * 100))
  const deepEnough = angle != null && angle <= down
  const remain = Math.max(0, target - reps)
  const progress = Math.min(1, reps / target)

  // 장치 상태를 숫자가 아니라 한 문장으로 먼저 말한다.
  const cpu = stats?.cpu_percent ?? 0
  const temp = stats?.cpu_temp_c ?? 0
  const deviceMood =
    connection === 'offline' ? { text: '로봇과 연결이 끊겼어요', tone: 'bad' }
    : temp >= 80 || cpu >= 93 ? { text: '로봇이 조금 무리하고 있어요', tone: 'warn' }
    : { text: '로봇이 편안하게 돌아가고 있어요', tone: 'good' }

  const guarded = async (fn: () => Promise<unknown>) => {
    if (await control.requestControl()) await fn()
  }

  const R = 132
  const C = 2 * Math.PI * R

  return (
    <div className="clm">
      <header className="clm__top">
        <div className="clm__top-l">
          <span className={`clm__dot clm__dot--${conn.tone}`} />
          <span className="clm__top-text">{conn.ko}</span>
          {demo && <span className="clm__demo">둘러보기</span>}
        </div>
        <button className="clm__top-btn" onClick={onOpenPicker}>
          시안 정보
        </button>
      </header>

      <main className="clm__main">
        {/* ---------- 링 ---------- */}
        <section className="clm__hero">
          <div className={`clm__ring${pulsing ? ' is-count' : ''}`}>
            <svg viewBox="0 0 300 300" className="clm__ring-svg" aria-hidden="true">
              <circle className="clm__ring-track" cx="150" cy="150" r={R} />
              <circle
                className="clm__ring-fill"
                cx="150" cy="150" r={R}
                strokeDasharray={C}
                strokeDashoffset={C * (1 - progress)}
              />
            </svg>
            <div className="clm__ring-in">
              <span className="clm__count hcb-tnum">{reps}</span>
              <span className="clm__count-sub">
                {remain > 0 ? `${remain}회 남았어요` : '오늘 목표를 채웠어요'}
              </span>
            </div>
          </div>

          <p className={`clm__coach clm__coach--${fb.tone}`}>{fb.text}</p>

          <div className="clm__pills">
            <Pill label="목표" value={`${target}회`} />
            <Pill label="시간" value={fmtClock(session?.elapsed_ms ?? 0)} />
            <Pill
              label="상태"
              value={
                session?.status === 'running' ? '진행 중'
                : session?.status === 'paused' ? '잠시 멈춤'
                : '대기'
              }
            />
          </div>
        </section>

        {/* ---------- 자세 ---------- */}
        <section className="clm__card">
          <h2 className="clm__card-title">
            지금 자세
            <span className="clm__card-note">{track?.ko ?? '—'}</span>
          </h2>

          <div className="clm__view" ref={cam.containerRef}>
            {cam.src && cam.live ? (
              <img className="clm__view-img" src={cam.src} alt="라이브 카메라" />
            ) : demo ? (
              <DemoPose
                className="clm__view-pose"
                angle={angle}
                sway={stats?.ptz.pan_deg != null ? stats.ptz.pan_deg / 24 : 0}
                skeleton="rgba(15,76,58,0.28)"
                joint="#0f4c3a"
                hot="#f2b705"
                hotActive={deepEnough}
              />
            ) : (
              <div className="clm__view-void">화면을 불러오는 중이에요</div>
            )}
            <button className="clm__view-fs" onClick={cam.toggleFullscreen} aria-label="전체화면">
              ⤢
            </button>
          </div>

          {/* 깊이 — 눈금이 아니라 "여기까지 내려오면 인정" 한 점만 */}
          <div className="clm__depth">
            <div className="clm__depth-head">
              <span>앉은 깊이</span>
              <b className="hcb-tnum">{angle == null ? '—' : `${Math.round(angle)}°`}</b>
            </div>
            <div className="clm__depth-track">
              <div className="clm__depth-fill" data-deep={deepEnough} style={{ width: `${depth}%` }} />
            </div>
            <p className="clm__depth-hint">
              {deepEnough
                ? '충분히 내려왔어요. 천천히 올라오세요.'
                : `무릎이 ${down}도까지 내려오면 한 번으로 세어요.`}
            </p>
          </div>
        </section>

        {/* ---------- 로봇 ---------- */}
        <section className="clm__card">
          <h2 className="clm__card-title">로봇 상태</h2>

          <div className={`clm__mood clm__mood--${deviceMood.tone}`}>
            <span className="clm__mood-face" aria-hidden="true" />
            <span>{deviceMood.text}</span>
          </div>

          <div className="clm__grid">
            <Metric label="처리 속도" value={fmtNum(stats?.fps, 1)} unit="fps" />
            <Metric label="처리 주기" value={fmtNum(stats?.loop_ms, 0)} unit="ms" />
            <Metric label="프로세서" value={fmtNum(stats?.cpu_percent, 0)} unit="%" warn={cpu >= 90} />
            <Metric label="온도" value={fmtNum(stats?.cpu_temp_c, 0)} unit="°C" warn={temp >= 78} />
            <Metric label="메모리" value={fmtNum(stats?.rss_mb, 0)} unit="MB" />
            <Metric label="함께 보는 사람" value={String(stats?.app.viewer_count ?? 0)} unit="명" />
          </div>

          <div className="clm__cam-row">
            <span className="clm__cam-label">카메라 방향</span>
            <span className="clm__cam-val hcb-tnum">
              좌우 {(stats?.ptz.pan_deg ?? 0) >= 0 ? '+' : ''}{fmtNum(stats?.ptz.pan_deg, 0)}°
              <i />
              상하 {(stats?.ptz.tilt_deg ?? 0) >= 0 ? '+' : ''}{fmtNum(stats?.ptz.tilt_deg, 0)}°
            </span>
          </div>
        </section>

        {/* ---------- 조작 ---------- */}
        {isOperator ? (
          <section className="clm__card">
            <h2 className="clm__card-title">
              조작
              <span className="clm__card-note">{control.iAmHolder ? '권한 있음' : '권한 필요'}</span>
            </h2>

            <div className="clm__btns">
              {session?.status === 'running' ? (
                <>
                  <button className="clm__btn" onClick={() => guarded(api.sessionPause)}>잠시 멈춤</button>
                  <button className="clm__btn" onClick={() => guarded(api.sessionFinish)}>마무리</button>
                </>
              ) : session?.status === 'paused' ? (
                <>
                  <button className="clm__btn clm__btn--go" onClick={() => guarded(api.sessionResume)}>이어서 하기</button>
                  <button className="clm__btn" onClick={() => guarded(api.sessionFinish)}>마무리</button>
                </>
              ) : (
                <button className="clm__btn clm__btn--go" onClick={() => guarded(() => api.sessionStart(target))}>
                  시작하기
                </button>
              )}
              <button className="clm__btn" onClick={() => guarded(api.sessionReset)}>처음부터</button>
            </div>

            <div className="clm__row">
              <span>카메라가 알아서 따라오기</span>
              <button
                className={`clm__toggle${stats?.ptz.auto_track_enabled ? ' is-on' : ''}`}
                role="switch"
                aria-checked={!!stats?.ptz.auto_track_enabled}
                onClick={() =>
                  guarded(() => api.sendPtz('auto_track', { enabled: !stats?.ptz.auto_track_enabled }))
                }
              >
                <i />
              </button>
            </div>

            <div className="clm__pad-wrap">
              <span className="clm__pad-label">직접 움직이기</span>
              <div className="clm__pad">
                <PadBtn cls="up" label="↑" onFire={() => guarded(() => api.sendPtz('tilt', { delta_deg: -2 }))} />
                <PadBtn cls="left" label="←" onFire={() => guarded(() => api.sendPtz('pan', { delta_deg: -2 }))} />
                <button className="clm__pad-btn clm__pad-btn--home" onClick={() => guarded(() => api.sendPtz('center'))}>
                  가운데
                </button>
                <PadBtn cls="right" label="→" onFire={() => guarded(() => api.sendPtz('pan', { delta_deg: 2 }))} />
                <PadBtn cls="down" label="↓" onFire={() => guarded(() => api.sendPtz('tilt', { delta_deg: 2 }))} />
              </div>
            </div>
          </section>
        ) : (
          <p className="clm__viewer-note">
            지금은 함께 보고만 있어요. 로봇을 움직이려면 운영자 주소로 접속해 주세요.
          </p>
        )}

        <footer className="clm__foot">
          카메라 한 대로 재는 값이라, 서 있는 각도에 따라 깊이가 조금씩 다르게 잡힐 수 있어요.
        </footer>
      </main>

      {control.pinModalOpen && (
        <PinGate
          busy={control.pinBusy}
          error={control.pinError}
          onSubmit={control.submitPin}
          onCancel={control.cancelPinModal}
        />
      )}
    </div>
  )
}

/* ---------- 부품 ---------- */

function Pill({ label, value }: { label: string; value: string }) {
  return (
    <div className="clm__pill">
      <span className="clm__pill-label">{label}</span>
      <span className="clm__pill-value hcb-tnum">{value}</span>
    </div>
  )
}

function Metric({
  label, value, unit, warn,
}: { label: string; value: string; unit: string; warn?: boolean }) {
  return (
    <div className="clm__metric" data-warn={warn}>
      <span className="clm__metric-label">{label}</span>
      <span className="clm__metric-value hcb-tnum">
        {value}
        <em>{unit}</em>
      </span>
    </div>
  )
}

function PadBtn({ cls, label, onFire }: { cls: string; label: string; onFire: () => void }) {
  const press = usePressRepeat(onFire)
  return (
    <button className={`clm__pad-btn clm__pad-btn--${cls}`} {...press} aria-label={cls}>
      {label}
    </button>
  )
}

function PinGate({
  busy, error, onSubmit, onCancel,
}: {
  busy: boolean; error: string | null
  onSubmit: (pin: string) => void; onCancel: () => void
}) {
  const [pin, setPin] = useState('')
  return (
    <div className="clm__gate" onClick={onCancel} role="presentation">
      <form
        className="clm__gate-box"
        onClick={(e) => e.stopPropagation()}
        onSubmit={(e) => {
          e.preventDefault()
          onSubmit(pin)
        }}
      >
        <h3 className="clm__gate-title">조작 권한이 필요해요</h3>
        <p className="clm__gate-note">로봇은 한 번에 한 사람만 움직일 수 있어요.</p>
        <input
          className="clm__gate-input hcb-tnum"
          value={pin}
          onChange={(e) => setPin(e.target.value.replace(/\D/g, '').slice(0, 8))}
          inputMode="numeric"
          autoFocus
          aria-label="PIN"
        />
        {error && <p className="clm__gate-err">{error}</p>}
        <div className="clm__btns">
          <button type="button" className="clm__btn" onClick={onCancel}>닫기</button>
          <button type="submit" className="clm__btn clm__btn--go" disabled={busy || !pin}>
            {busy ? '확인 중' : '확인'}
          </button>
        </div>
      </form>
    </div>
  )
}
