import { useCallback, useEffect, useState } from 'react'
import { useMjpeg } from '../../hooks/useMjpeg'
import { useOperatorControl } from '../../hooks/useOperatorControl'
import { useRepPulse } from '../../hooks/useRepPulse'
import { usePressRepeat } from '../../hooks/usePressRepeat'
import { DemoPose } from '../../components/DemoPose'
import { poseFeedback } from '../../lib/feedback'
import { fmtClock, fmtNum, loadLevel } from '../../lib/format'
import * as api from '../../api'
import type { VersionScreenProps } from '../registry'
import './aurora.css'

/**
 * AURORA — 유리 대시보드 (글래스모피즘).
 *
 * 사용자 제공 목업(2026-07-21) 기반. 연한 블루/라벤더 그라디언트 배경,
 * 프로스티드 유리 카드, 부드러운 blob 오브. 핵심 요구는 **세련된 하단
 * 조작바** — 플로팅 유리 pill + 중앙 elevated FAB + 뷰 전환.
 *
 * 글래스모피즘의 가독성 함정(NN/g 경고)을 피하려고:
 *  - 본문 텍스트는 배경 그라디언트 위가 아니라 프로스티드 카드 위에만.
 *  - 대비를 충분히(진한 슬레이트 잉크), 블러는 카드/바/오버레이에만 목적있게.
 */
export default function Aurora({ stats, connection, role, demo, onOpenPicker }: VersionScreenProps) {
  const cam = useMjpeg(connection, demo)
  const control = useOperatorControl(role, stats?.app.control)
  const isOperator = role === 'operator'

  const [view, setView] = useState<'live' | 'device' | 'control'>('live')
  const [shareOpen, setShareOpen] = useState(false)
  const [step, setStep] = useState(5)

  const squat = stats?.squat
  const reps = squat?.reps ?? 0
  const session = stats?.app.session
  const target = session?.target_reps ?? 20
  const angle = stats?.angle_deg.used ?? null
  const fb = poseFeedback(stats)
  const pulse = useRepPulse(reps)
  const pct = target > 0 ? Math.min(100, Math.round((reps / target) * 100)) : 0
  const deep = angle != null && angle <= (squat?.thresholds_deg.down ?? 100)

  const fpsSeries = useRolling(stats?.fps)
  const running = session?.status === 'running'

  const guarded = async (fn: () => Promise<unknown>) => {
    if (await control.requestControl()) await fn()
  }
  const pan = (d: number) => api.sendPtz('pan', { delta_deg: d * step })
  // 서보 convention: 양수 delta = 카메라 '아래'(캘리브레이션 2026-07-17_02).
  // 화면 '위' 버튼이 실제로 위로 가도록 부호를 반전한다.
  const tilt = (d: number) => api.sendPtz('tilt', { delta_deg: -d * step })

  const viewerUrl = (() => {
    const u = new URL(window.location.href)
    u.searchParams.delete('role')
    return u.toString()
  })()
  const [copied, setCopied] = useState(false)
  const copyLink = useCallback(() => {
    navigator.clipboard?.writeText(viewerUrl).then(() => {
      setCopied(true)
      setTimeout(() => setCopied(false), 1600)
    })
  }, [viewerUrl])

  // 중앙 FAB: 운영자=세션 토글, 뷰어=공유
  const fab = isOperator
    ? {
        icon: running ? 'pause' : 'play',
        onClick: () =>
          guarded(
            running ? api.sessionPause
            : session?.status === 'paused' ? api.sessionResume
            : () => api.sessionStart(target),
          ),
      }
    : { icon: 'share', onClick: () => setShareOpen(true) }

  const R = 84
  const C = 2 * Math.PI * R

  return (
    <div className="aur">
      <div className="aur__bg" aria-hidden="true">
        <span className="aur__orb aur__orb--1" />
        <span className="aur__orb aur__orb--2" />
        <span className="aur__orb aur__orb--3" />
      </div>

      {/* ---------- 헤더 ---------- */}
      <header className="aur__head">
        <div>
          <p className="aur__hello">안녕하세요</p>
          <h1 className="aur__title">건강 대시보드</h1>
        </div>
        <div className="aur__head-right">
          <span className={`aur__status aur__status--${connection === 'online' ? 'on' : 'off'}`}>
            <i /> {connection === 'online' ? 'ONLINE' : connection === 'offline' ? 'OFFLINE' : '연결 중'}
          </span>
          {demo && <span className="aur__demo">DEMO</span>}
          <button className="aur__chip" onClick={onOpenPicker}>시안</button>
        </div>
      </header>

      <main className="aur__main">
        {/* ================= 라이브 ================= */}
        {view === 'live' && (
          <>
            <div className="aur__glass aur__cam-card">
              <div className="aur__cam" ref={cam.containerRef}>
                {cam.src && cam.live ? (
                  <img className="aur__cam-img" src={cam.src} alt="라이브 카메라" />
                ) : demo ? (
                  <DemoPose
                    className="aur__cam-pose" angle={angle}
                    sway={stats?.ptz.pan_deg != null ? stats.ptz.pan_deg / 24 : 0}
                    skeleton="rgba(255,255,255,0.6)" joint="#ffffff"
                    hot="#7c9cff" hotActive={deep}
                  />
                ) : (
                  <div className="aur__cam-void">화면을 불러오는 중이에요</div>
                )}
                <div className="aur__cam-badges">
                  <span className="aur__cam-badge" data-live={cam.live || demo}>
                    <i /> {cam.live ? 'LIVE' : demo ? 'SYNTH' : 'OFF'}
                  </span>
                  <span className="aur__cam-badge aur__cam-badge--fps hcb-tnum">{fmtNum(stats?.fps, 0)} FPS</span>
                </div>
                {isOperator && (
                  <>
                    <NudgeEdge cls="up" onFire={() => guarded(() => tilt(1))}><IcoArrow d="up" /></NudgeEdge>
                    <NudgeEdge cls="down" onFire={() => guarded(() => tilt(-1))}><IcoArrow d="down" /></NudgeEdge>
                    <NudgeEdge cls="left" onFire={() => guarded(() => pan(-1))}><IcoArrow d="left" /></NudgeEdge>
                    <NudgeEdge cls="right" onFire={() => guarded(() => pan(1))}><IcoArrow d="right" /></NudgeEdge>
                  </>
                )}
                <button className="aur__cam-fs" onClick={cam.toggleFullscreen} aria-label="전체화면">⤢</button>
              </div>
            </div>

            {/* 스쿼트 진행 링 */}
            <div className="aur__glass aur__ring-card">
              <div className="aur__ring-head">
                <span>오늘의 스쿼트</span>
                <span className="aur__ring-time hcb-tnum">{fmtClock(session?.elapsed_ms ?? 0)}</span>
              </div>
              <div className="aur__ring-wrap">
                <svg viewBox="0 0 200 200" className="aur__ring-svg" aria-hidden="true">
                  <defs>
                    <linearGradient id="aur-ring-grad" x1="0" y1="0" x2="1" y2="1">
                      <stop offset="0%" stopColor="#7c9cff" />
                      <stop offset="100%" stopColor="#6d5efc" />
                    </linearGradient>
                  </defs>
                  <circle className="aur__ring-track" cx="100" cy="100" r={R} />
                  <circle
                    className="aur__ring-fill" cx="100" cy="100" r={R}
                    stroke="url(#aur-ring-grad)" strokeDasharray={C}
                    strokeDashoffset={C * (1 - Math.min(1, reps / target))}
                  />
                </svg>
                <div className={`aur__ring-center${pulse.pulsing ? ' is-pulse' : ''}`}>
                  <span className="aur__ring-reps hcb-tnum">{reps}</span>
                  <span className="aur__ring-sub hcb-tnum">{pct}% · /{target}</span>
                </div>
              </div>
              <p className={`aur__coach aur__coach--${fb.tone}`}>{fb.text}</p>
            </div>
          </>
        )}

        {/* ================= 장치 ================= */}
        {view === 'device' && (
          <>
            <div className="aur__stat-grid">
              <StatTile label="프로세서" value={fmtNum(stats?.cpu_percent, 0)} unit="%" tone={loadLevel(stats?.cpu_percent, 85, 95)} accent />
              <StatTile label="온도" value={fmtNum(stats?.cpu_temp_c, 0)} unit="°C" tone={loadLevel(stats?.cpu_temp_c, 75, 82)} />
              <StatTile label="처리 속도" value={fmtNum(stats?.fps, 1)} unit="fps" />
              <StatTile label="메모리" value={fmtNum(stats?.rss_mb, 0)} unit="MB" />
            </div>

            <div className="aur__glass aur__chart-card">
              <div className="aur__chart-head">
                <span className="aur__chart-num hcb-tnum">{fmtNum(stats?.fps, 1)}</span>
                <span className="aur__chart-lbl">최근 처리 속도 (fps)</span>
              </div>
              <Sparkline series={fpsSeries} />
            </div>

            <div className="aur__glass aur__kv-card">
              <Kv label="카메라 좌우" value={`${(stats?.ptz.pan_deg ?? 0) >= 0 ? '+' : ''}${fmtNum(stats?.ptz.pan_deg, 0)}°`} />
              <Kv label="카메라 상하" value={`${(stats?.ptz.tilt_deg ?? 0) >= 0 ? '+' : ''}${fmtNum(stats?.ptz.tilt_deg, 0)}°`} />
              <Kv label="유실 프레임" value={`${stats?.dropped_frames ?? 0}장`} />
              <Kv label="함께 보는 사람" value={`${stats?.app.viewer_count ?? 0}명`} />
            </div>
          </>
        )}

        {/* ================= 제어 ================= */}
        {view === 'control' && (
          isOperator ? (
            <div className="aur__glass aur__ctl-card">
              <div className="aur__ctl-head">
                <h2>카메라 제어</h2>
                <span className={`aur__lock${control.iAmHolder ? ' is-on' : ''}`}>
                  {control.iAmHolder ? '권한 있음' : '권한 필요'}
                </span>
              </div>

              <div className="aur__pad">
                <PadBtn cls="up" onFire={() => guarded(() => tilt(1))}><IcoArrow d="up" /></PadBtn>
                <PadBtn cls="left" onFire={() => guarded(() => pan(-1))}><IcoArrow d="left" /></PadBtn>
                <button className="aur__pad-center" onClick={() => guarded(() => api.sendPtz('center'))}>중앙</button>
                <PadBtn cls="right" onFire={() => guarded(() => pan(1))}><IcoArrow d="right" /></PadBtn>
                <PadBtn cls="down" onFire={() => guarded(() => tilt(-1))}><IcoArrow d="down" /></PadBtn>
              </div>

              <div className="aur__ctl-row">
                <span>자동 추적</span>
                <button
                  className={`aur__switch${stats?.ptz.auto_track_enabled ? ' is-on' : ''}`}
                  role="switch" aria-checked={!!stats?.ptz.auto_track_enabled}
                  onClick={() => guarded(() => api.sendPtz('auto_track', { enabled: !stats?.ptz.auto_track_enabled }))}
                >
                  <i />
                </button>
              </div>

              <div className="aur__ctl-row">
                <span>이동 폭</span>
                <div className="aur__step">
                  {[2, 5, 10].map((s) => (
                    <button key={s} className={`aur__step-btn${step === s ? ' is-on' : ''}`} onClick={() => setStep(s)}>{s}°</button>
                  ))}
                </div>
              </div>

              <div className="aur__ctl-btns">
                <button className="aur__btn" onClick={() => guarded(api.sessionReset)}>초기화</button>
                <button className="aur__btn" onClick={() => guarded(api.sessionFinish)}>세션 종료</button>
              </div>
            </div>
          ) : (
            <div className="aur__glass aur__ctl-card">
              <p className="aur__viewer-note">지금은 함께 보고만 있어요. 로봇을 움직이려면 운영자 주소로 접속해 주세요.</p>
            </div>
          )
        )}
      </main>

      {/* ================= 세련된 하단 조작바 ================= */}
      <nav className="aur__nav" aria-label="화면 전환">
        <NavTab active={view === 'live'} onClick={() => setView('live')} label="라이브"><IcoHome /></NavTab>
        <NavTab active={view === 'device'} onClick={() => setView('device')} label="장치"><IcoChart /></NavTab>

        <button className="aur__fab" onClick={fab.onClick} aria-label={isOperator ? '세션' : '공유'}>
          <span className="aur__fab-ring" aria-hidden="true" />
          {fab.icon === 'play' && <IcoPlay />}
          {fab.icon === 'pause' && <IcoPause />}
          {fab.icon === 'share' && <IcoShare />}
        </button>

        <NavTab active={false} onClick={() => setShareOpen(true)} label="공유"><IcoShare /></NavTab>
        <NavTab active={view === 'control'} onClick={() => setView('control')} label="제어"><IcoSliders /></NavTab>
      </nav>

      {/* ---------- 공유 시트 ---------- */}
      {shareOpen && (
        <div className="aur__sheet" onClick={() => setShareOpen(false)} role="presentation">
          <div className="aur__sheet-box" onClick={(e) => e.stopPropagation()}>
            <h3>세션 공유</h3>
            <p className="aur__sheet-url hcb-tnum">{viewerUrl.replace(/^https?:\/\//, '')}</p>
            <button className="aur__btn aur__btn--primary" onClick={copyLink}>{copied ? '복사됨 ✓' : '링크 복사'}</button>
            <button className="aur__btn" onClick={() => setShareOpen(false)}>닫기</button>
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

/* ---------- 롤링 히스토리 (차트용, AURORA 로컬) ---------- */
function useRolling(v: number | null | undefined, n = 40): number[] {
  const [arr, setArr] = useState<number[]>([])
  useEffect(() => {
    if (v == null || Number.isNaN(v)) return
    setArr((prev) => {
      const next = prev.concat(v)
      return next.length > n ? next.slice(next.length - n) : next
    })
  }, [v, n])
  return arr
}

/* ---------- 부품 ---------- */

function Sparkline({ series }: { series: number[] }) {
  if (series.length < 2) return <div className="aur__spark aur__spark--empty" />
  const w = 100, h = 44
  const lo = Math.min(...series), hi = Math.max(...series)
  const sp = hi - lo || 1
  const pts = series.map((v, i) => `${(i / (series.length - 1)) * w},${h - ((v - lo) / sp) * h}`)
  return (
    <svg className="aur__spark" viewBox={`0 0 ${w} ${h}`} preserveAspectRatio="none" aria-hidden="true">
      <defs>
        <linearGradient id="aur-area" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="#7c9cff" stopOpacity="0.4" />
          <stop offset="100%" stopColor="#7c9cff" stopOpacity="0" />
        </linearGradient>
      </defs>
      <polygon className="aur__spark-area" points={`0,${h} ${pts.join(' ')} ${w},${h}`} fill="url(#aur-area)" />
      <polyline className="aur__spark-line" points={pts.join(' ')} />
    </svg>
  )
}

function StatTile({
  label, value, unit, tone = 'ok', accent,
}: { label: string; value: string; unit: string; tone?: string; accent?: boolean }) {
  return (
    <div className={`aur__glass aur__tile${accent ? ' aur__tile--accent' : ''}`} data-tone={tone}>
      <span className="aur__tile-label">{label}</span>
      <span className="aur__tile-value hcb-tnum">{value}<em>{unit}</em></span>
    </div>
  )
}

function Kv({ label, value }: { label: string; value: string }) {
  return (
    <div className="aur__kv">
      <span>{label}</span>
      <b className="hcb-tnum">{value}</b>
    </div>
  )
}

function NavTab({
  active, onClick, label, children,
}: { active: boolean; onClick: () => void; label: string; children: React.ReactNode }) {
  return (
    <button className={`aur__tab${active ? ' is-active' : ''}`} onClick={onClick} aria-current={active}>
      {children}
      <span>{label}</span>
    </button>
  )
}

function NudgeEdge({ cls, onFire, children }: { cls: string; onFire: () => void; children: React.ReactNode }) {
  const press = usePressRepeat(onFire)
  return <button className={`aur__nudge aur__nudge--${cls}`} {...press} aria-label={cls}>{children}</button>
}

function PadBtn({ cls, onFire, children }: { cls: string; onFire: () => void; children: React.ReactNode }) {
  const press = usePressRepeat(onFire)
  return <button className={`aur__pad-btn aur__pad-btn--${cls}`} {...press} aria-label={cls}>{children}</button>
}

/* ---------- 아이콘 (인라인 SVG) ---------- */
const S = { width: 22, height: 22, viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', strokeWidth: 2, strokeLinecap: 'round' as const, strokeLinejoin: 'round' as const }
const IcoHome = () => <svg {...S}><path d="M3 10.5 12 3l9 7.5" /><path d="M5 9.5V21h14V9.5" /></svg>
const IcoChart = () => <svg {...S}><path d="M4 20V10M10 20V4M16 20v-7M22 20H2" /></svg>
const IcoSliders = () => <svg {...S}><path d="M4 6h16M4 12h16M4 18h16" /><circle cx="9" cy="6" r="2" fill="currentColor" stroke="none" /><circle cx="15" cy="12" r="2" fill="currentColor" stroke="none" /><circle cx="8" cy="18" r="2" fill="currentColor" stroke="none" /></svg>
const IcoShare = () => <svg {...S}><circle cx="18" cy="5" r="3" /><circle cx="6" cy="12" r="3" /><circle cx="18" cy="19" r="3" /><path d="m8.6 13.5 6.8 4M15.4 6.5l-6.8 4" /></svg>
const IcoPlay = () => <svg {...S} width={24} height={24} fill="currentColor" stroke="none"><path d="M8 5v14l11-7z" /></svg>
const IcoPause = () => <svg {...S} width={24} height={24} fill="currentColor" stroke="none"><path d="M7 5h4v14H7zM13 5h4v14h-4z" /></svg>
const IcoArrow = ({ d }: { d: 'up' | 'down' | 'left' | 'right' }) => {
  const p = { up: 'M6 15l6-6 6 6', down: 'M6 9l6 6 6-6', left: 'M15 6l-6 6 6 6', right: 'M9 6l6 6-6 6' }[d]
  return <svg {...S} width={18} height={18}><path d={p} /></svg>
}

function PinGate({
  busy, error, onSubmit, onCancel,
}: { busy: boolean; error: string | null; onSubmit: (pin: string) => void; onCancel: () => void }) {
  const [pin, setPin] = useState('')
  return (
    <div className="aur__sheet" onClick={onCancel} role="presentation">
      <form className="aur__sheet-box" onClick={(e) => e.stopPropagation()}
            onSubmit={(e) => { e.preventDefault(); onSubmit(pin) }}>
        <h3>조작 권한</h3>
        <p className="aur__pin-note">로봇은 한 번에 한 사람만 움직일 수 있어요.</p>
        <input className="aur__pin-input hcb-tnum" value={pin} inputMode="numeric" autoFocus aria-label="PIN"
               onChange={(e) => setPin(e.target.value.replace(/\D/g, '').slice(0, 8))} placeholder="––––" />
        {error && <p className="aur__pin-err">{error}</p>}
        <button type="submit" className="aur__btn aur__btn--primary" disabled={busy || !pin}>{busy ? '확인 중…' : '들어가기'}</button>
        <button type="button" className="aur__btn" onClick={onCancel}>취소</button>
      </form>
    </div>
  )
}
