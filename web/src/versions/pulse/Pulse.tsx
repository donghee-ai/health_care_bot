import { useCallback, useState } from 'react'
import { useMjpeg } from '../../hooks/useMjpeg'
import { useOperatorControl } from '../../hooks/useOperatorControl'
import { useRepPulse } from '../../hooks/useRepPulse'
import { usePressRepeat } from '../../hooks/usePressRepeat'
import { DemoPose } from '../../components/DemoPose'
import { poseFeedback } from '../../lib/feedback'
import { fmtClock, fmtNum } from '../../lib/format'
import * as api from '../../api'
import type { VersionScreenProps } from '../registry'
import './pulse.css'

/**
 * PULSE — 밝은 프로덕트 콘솔.
 *
 * 목업(2026-07-21 사용자 제공) 기반. Toss 스타일 프로덕트 앱 느낌 +
 * Qualcomm Dragonwing 산업용 엣지 AI. 흰 배경, 컬러풀한 라운드 카드,
 * 큰 친근한 버튼.
 *
 * 다른 시안과의 차이:
 * - 스쿼트/푸시업을 **두 카드로 동시에** 보여준다 (종목별 강조색:
 *   스쿼트=보라, 푸시업=초록). 백엔드는 두 카운터를 항상 돌리므로 가능.
 * - PTZ에 STEP(2/5/10°) 선택이 있어 넛지 크기를 고른다.
 * - 유일하게 부드러운 그림자와 큰 라운드를 적극적으로 쓰는 밝은 테마.
 */
export default function Pulse({ stats, connection, role, demo, onOpenPicker }: VersionScreenProps) {
  const cam = useMjpeg(connection, demo)
  const control = useOperatorControl(role, stats?.app.control)
  const isOperator = role === 'operator'

  const squat = stats?.squat
  const pushup = stats?.pushup
  const session = stats?.app.session
  const target = session?.target_reps ?? 20
  const angle = stats?.angle_deg.used ?? null
  const fb = poseFeedback(stats)
  const active = stats?.exercise_active

  const squatPulse = useRepPulse(squat?.reps)
  const pushupPulse = useRepPulse(pushup?.reps)

  const [step, setStep] = useState(5)
  const [qrOpen, setQrOpen] = useState(false)
  const [copied, setCopied] = useState(false)

  const online = connection === 'online'
  const track =
    stats?.ptz.state === 'in_frame' ? { label: 'TRACKING', tone: 'track' as const }
    : stats?.ptz.state === 'edge' ? { label: 'REPOSITIONING', tone: 'warn' as const }
    : { label: 'LOST', tone: 'lost' as const }

  const guarded = async (fn: () => Promise<unknown>) => {
    if (await control.requestControl()) await fn()
  }
  const pan = (d: number) => api.sendPtz('pan', { delta_deg: d * step })
  // 서보 convention: 양수 delta = 카메라 '아래'(캘리브레이션 2026-07-17_02).
  // 화면 '위' 버튼이 실제로 위로 가도록 부호를 반전한다.
  const tilt = (d: number) => api.sendPtz('tilt', { delta_deg: -d * step })

  // 관람객이 스캔/공유할 뷰어 URL (operator 파라미터 제거)
  const viewerUrl = (() => {
    const u = new URL(window.location.href)
    u.searchParams.delete('role')
    return u.toString()
  })()
  const copyLink = useCallback(() => {
    navigator.clipboard?.writeText(viewerUrl).then(() => {
      setCopied(true)
      setTimeout(() => setCopied(false), 1600)
    })
  }, [viewerUrl])

  const finished = session?.status === 'finished' && session.last_finished

  return (
    <div className="pls">
      {/* ---------- 상단 바 ---------- */}
      <header className="pls__top">
        <div className="pls__brand">
          <span className="pls__logo" aria-hidden="true" />
          <span className="pls__brand-name">Health Care Bot</span>
          <span className="pls__brand-sub">UNO Q · Dragonwing</span>
        </div>
        <div className="pls__top-right">
          <span className={`pls__pill pls__pill--${online ? 'online' : 'off'}`}>
            <i /> {online ? 'ONLINE' : connection === 'offline' ? 'OFFLINE' : '연결 중'}
          </span>
          <span className="pls__fps hcb-tnum">{fmtNum(stats?.fps, 0)} FPS</span>
          <span className="pls__role">{isOperator ? 'Operator' : 'Viewer'}</span>
          {demo && <span className="pls__demo">DEMO</span>}
          <button className="pls__ui-btn" onClick={onOpenPicker}>시안</button>
        </div>
      </header>

      <main className="pls__main">
        {/* ---------- 카메라 ---------- */}
        <section className="pls__cam-wrap">
          <div className="pls__cam" ref={cam.containerRef}>
            {cam.src && cam.live ? (
              <img className="pls__cam-img" src={cam.src} alt="라이브 카메라" />
            ) : demo ? (
              <DemoPose
                className="pls__cam-pose"
                angle={angle}
                sway={stats?.ptz.pan_deg != null ? stats.ptz.pan_deg / 24 : 0}
                skeleton="rgba(255,255,255,0.55)"
                joint="#ffffff"
                hot="#28d7e8"
                hotActive={angle != null && angle <= (squat?.thresholds_deg.down ?? 100)}
              />
            ) : (
              <div className="pls__cam-void">화면을 불러오는 중이에요</div>
            )}

            <span className="pls__grid" aria-hidden="true" />

            {/* 상단 오버레이 */}
            <div className="pls__cam-top">
              <span className="pls__badge pls__badge--live" data-live={cam.live || demo}>
                <i /> {cam.live ? 'LIVE' : demo ? 'SYNTH' : 'OFF'}
              </span>
              <span className={`pls__badge pls__badge--${track.tone}`}>{track.label}</span>
            </div>

            {/* 좌상단 각도 / 좌하단 카운트 */}
            <div className="pls__cam-read pls__cam-read--tl">
              <span className="pls__cam-read-k">각도</span>
              <span className="pls__cam-read-v hcb-tnum">{angle == null ? '—' : `${Math.round(angle)}°`}</span>
            </div>
            <div className="pls__cam-read pls__cam-read--bl">
              <span className="pls__cam-read-k">COUNT</span>
              <span className="pls__cam-read-v hcb-tnum">{(squat?.reps ?? 0) + (pushup?.reps ?? 0)}</span>
            </div>

            {/* 카메라 위 넛지 화살표 (운영자) */}
            {isOperator && (
              <>
                <NudgeEdge cls="up" label="▲" onFire={() => guarded(() => tilt(1))} />
                <NudgeEdge cls="down" label="▼" onFire={() => guarded(() => tilt(-1))} />
                <NudgeEdge cls="left" label="◀" onFire={() => guarded(() => pan(-1))} />
                <NudgeEdge cls="right" label="▶" onFire={() => guarded(() => pan(1))} />
              </>
            )}

            <button className="pls__cam-fs" onClick={cam.toggleFullscreen} aria-label="전체화면">⤢</button>
          </div>

          <p className={`pls__coach pls__coach--${fb.tone}`}>{fb.text}</p>
        </section>

        {/* ---------- 운동 카드 2개 ---------- */}
        <section className="pls__cards">
          <ExerciseCard
            name="SQUAT" ko="스쿼트" accent="squat"
            reps={squat?.reps ?? 0} state={squat?.state}
            angle={active === 'squat' ? angle : null}
            active={active === 'squat'} pulsing={squatPulse.pulsing} pulseKey={squatPulse.pulseKey} target={target}
          />
          <ExerciseCard
            name="PUSHUP" ko="푸시업" accent="pushup"
            reps={pushup?.reps ?? 0} state={pushup?.state}
            angle={active === 'pushup' ? angle : null}
            active={active === 'pushup'} pulsing={pushupPulse.pulsing} pulseKey={pushupPulse.pulseKey} target={target}
          />
        </section>

        {/* ---------- 조작 / 뷰어 ---------- */}
        {isOperator ? (
          <section className="pls__panel">
            <div className="pls__panel-head">
              <h2>제어</h2>
              <span className={`pls__lock${control.iAmHolder ? ' is-on' : ''}`}>
                {control.iAmHolder ? '권한 있음' : '권한 필요'}
              </span>
            </div>

            {/* 세션 */}
            <div className="pls__btn-row">
              {session?.status === 'running' ? (
                <>
                  <button className="pls__btn" onClick={() => guarded(api.sessionPause)}>일시정지</button>
                  <button className="pls__btn pls__btn--primary" onClick={() => guarded(api.sessionFinish)}>세션 종료</button>
                </>
              ) : session?.status === 'paused' ? (
                <>
                  <button className="pls__btn pls__btn--primary" onClick={() => guarded(api.sessionResume)}>이어서</button>
                  <button className="pls__btn" onClick={() => guarded(api.sessionFinish)}>종료</button>
                </>
              ) : (
                <button className="pls__btn pls__btn--primary pls__btn--wide" onClick={() => guarded(() => api.sessionStart(target))}>
                  세션 시작
                </button>
              )}
              <button className="pls__btn" onClick={() => guarded(api.sessionReset)}>초기화</button>
            </div>

            {/* PTZ 패드 */}
            <div className="pls__ptz">
              <div className="pls__pad">
                <PadBtn cls="up" label="▲" onFire={() => guarded(() => tilt(1))} />
                <PadBtn cls="left" label="◀" onFire={() => guarded(() => pan(-1))} />
                <button className="pls__pad-center" onClick={() => guarded(() => api.sendPtz('center'))}>CENTER</button>
                <PadBtn cls="right" label="▶" onFire={() => guarded(() => pan(1))} />
                <PadBtn cls="down" label="▼" onFire={() => guarded(() => tilt(-1))} />
              </div>

              <div className="pls__ptz-side">
                <label className="pls__toggle-row">
                  <span>자동 추적</span>
                  <button
                    className={`pls__switch${stats?.ptz.auto_track_enabled ? ' is-on' : ''}`}
                    role="switch" aria-checked={!!stats?.ptz.auto_track_enabled}
                    onClick={() => guarded(() => api.sendPtz('auto_track', { enabled: !stats?.ptz.auto_track_enabled }))}
                  >
                    <i />
                  </button>
                </label>

                <div className="pls__step">
                  <span className="pls__step-label">STEP</span>
                  <div className="pls__step-opts">
                    {[2, 5, 10].map((s) => (
                      <button key={s} className={`pls__step-btn${step === s ? ' is-on' : ''}`} onClick={() => setStep(s)}>
                        {s}°
                      </button>
                    ))}
                  </div>
                </div>

                <button className="pls__qr-btn" onClick={() => setQrOpen(true)}>
                  <span className="pls__qr-ico" aria-hidden="true" /> 공유 · QR
                </button>
              </div>
            </div>
          </section>
        ) : (
          <section className="pls__panel pls__panel--share">
            <div className="pls__share-card" onClick={() => setQrOpen(true)} role="button" tabIndex={0}>
              <QrGlyph />
              <div>
                <h3>세션 공유</h3>
                <p>QR을 스캔하거나 링크를 복사해 함께 보세요.</p>
              </div>
            </div>
          </section>
        )}

        <footer className="pls__foot">
          카메라 한 대로 재는 값이라, 서 있는 각도에 따라 깊이가 조금씩 다르게 잡힐 수 있어요.
          {session != null && <> · 경과 {fmtClock(session.elapsed_ms ?? 0)}</>}
        </footer>
      </main>

      {/* ---------- 세션 요약 ---------- */}
      {finished && (
        <SessionSummary
          summary={session!.last_finished!}
          onClose={() => guarded(api.sessionReset)}
          onShare={() => setQrOpen(true)}
        />
      )}

      {/* ---------- QR / 공유 시트 ---------- */}
      {qrOpen && (
        <div className="pls__sheet" onClick={() => setQrOpen(false)} role="presentation">
          <div className="pls__sheet-box" onClick={(e) => e.stopPropagation()}>
            <QrGlyph big />
            <p className="pls__sheet-url hcb-tnum">{viewerUrl.replace(/^https?:\/\//, '')}</p>
            <button className="pls__btn pls__btn--primary pls__btn--wide" onClick={copyLink}>
              {copied ? '복사됨 ✓' : '링크 복사'}
            </button>
            <button className="pls__btn pls__btn--wide" onClick={() => setQrOpen(false)}>닫기</button>
          </div>
        </div>
      )}

      {/* ---------- PIN ---------- */}
      {control.pinModalOpen && (
        <PinGate busy={control.pinBusy} error={control.pinError}
                 onSubmit={control.submitPin} onCancel={control.cancelPinModal} />
      )}
    </div>
  )
}

/* ---------- 부품 ---------- */

function ExerciseCard({
  name, ko, accent, reps, state, angle, active, pulsing, pulseKey, target,
}: {
  name: string; ko: string; accent: 'squat' | 'pushup'
  reps: number; state?: string; angle: number | null
  active: boolean; pulsing: boolean; pulseKey: number; target: number
}) {
  return (
    <div className={`pls__card pls__card--${accent}${active ? ' is-active' : ''}`}>
      <div className="pls__card-head">
        <span className="pls__card-name">{name}</span>
        <span className="pls__card-ko">{ko}</span>
        {active && <span className="pls__card-live">●</span>}
      </div>
      <div className={`pls__card-num hcb-tnum${pulsing ? ' is-pulse' : ''}`}>
        {reps}
        <span className="pls__card-target">/{target}</span>
        {/* 1회 인정 순간의 '사건성' — +1 플로터가 떠오르며 사라진다.
            key가 바뀔 때마다 CSS 애니메이션이 다시 재생된다. */}
        {pulseKey > 0 && <span key={pulseKey} className="pls__floater" aria-hidden="true">+1</span>}
      </div>
      <div className="pls__card-foot">
        <span className="pls__card-state">{state ?? '—'}</span>
        <span className="pls__card-angle hcb-tnum">{angle == null ? '' : `${Math.round(angle)}°`}</span>
      </div>
    </div>
  )
}

function NudgeEdge({ cls, label, onFire }: { cls: string; label: string; onFire: () => void }) {
  const press = usePressRepeat(onFire)
  return <button className={`pls__nudge pls__nudge--${cls}`} {...press} aria-label={cls}>{label}</button>
}

function PadBtn({ cls, label, onFire }: { cls: string; label: string; onFire: () => void }) {
  const press = usePressRepeat(onFire)
  return <button className={`pls__pad-btn pls__pad-btn--${cls}`} {...press} aria-label={cls}>{label}</button>
}

function QrGlyph({ big }: { big?: boolean }) {
  // 실제 QR 인코딩 대신 데모용 결정론적 패턴 (링크 복사가 실제 공유 경로).
  const cells = []
  const seed = [1, 0, 1, 1, 0, 0, 1, 0, 1, 1, 1, 0, 0, 1, 0, 1, 1, 0, 1, 0, 0, 1, 1, 0, 1]
  for (let i = 0; i < 49; i++) cells.push(seed[(i * 7 + 3) % seed.length] ^ (i % 3 === 0 ? 1 : 0))
  return (
    <div className={`pls__qr${big ? ' pls__qr--big' : ''}`} aria-hidden="true">
      <div className="pls__qr-grid">
        {cells.map((c, i) => <i key={i} data-on={!!c} />)}
      </div>
    </div>
  )
}

function SessionSummary({
  summary, onClose, onShare,
}: {
  summary: import('../../types').SessionSummary
  onClose: () => void; onShare: () => void
}) {
  const total = (summary.squat_reps ?? 0) + (summary.pushup_reps ?? 0)
  return (
    <div className="pls__summary">
      <div className="pls__summary-card">
        <div className="pls__summary-check">✓</div>
        <h2>완료!</h2>
        <div className="pls__summary-total hcb-tnum">{total}<span>회</span></div>
        <dl className="pls__summary-rows">
          <div><dt>스쿼트</dt><dd className="hcb-tnum">{summary.squat_reps ?? 0}회</dd></div>
          <div><dt>푸시업</dt><dd className="hcb-tnum">{summary.pushup_reps ?? 0}회</dd></div>
          <div><dt>가장 깊었던 각도</dt><dd className="hcb-tnum">{summary.squat_best_deg == null ? '—' : `${Math.round(summary.squat_best_deg)}°`}</dd></div>
          <div><dt>총 시간</dt><dd className="hcb-tnum">{fmtClock(summary.elapsed_ms ?? 0)}</dd></div>
        </dl>
        <button className="pls__btn pls__btn--primary pls__btn--wide" onClick={onShare}>결과 공유</button>
        <button className="pls__btn pls__btn--wide" onClick={onClose}>새 세션</button>
      </div>
    </div>
  )
}

function PinGate({
  busy, error, onSubmit, onCancel,
}: {
  busy: boolean; error: string | null; onSubmit: (pin: string) => void; onCancel: () => void
}) {
  const [pin, setPin] = useState('')
  return (
    <div className="pls__sheet" onClick={onCancel} role="presentation">
      <form className="pls__sheet-box" onClick={(e) => e.stopPropagation()}
            onSubmit={(e) => { e.preventDefault(); onSubmit(pin) }}>
        <h3 className="pls__pin-title">조작 권한</h3>
        <p className="pls__pin-note">로봇은 한 번에 한 사람만 움직일 수 있어요.</p>
        <input className="pls__pin-input hcb-tnum" value={pin} inputMode="numeric" autoFocus aria-label="PIN"
               onChange={(e) => setPin(e.target.value.replace(/\D/g, '').slice(0, 8))} placeholder="––––" />
        {error && <p className="pls__pin-err">{error}</p>}
        <button type="submit" className="pls__btn pls__btn--primary pls__btn--wide" disabled={busy || !pin}>
          {busy ? '확인 중…' : '들어가기'}
        </button>
        <button type="button" className="pls__btn pls__btn--wide" onClick={onCancel}>취소</button>
      </form>
    </div>
  )
}
