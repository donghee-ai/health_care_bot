import { useState } from 'react'
import { useOperatorControl } from '../../hooks/useOperatorControl'
import { useRepPulse } from '../../hooks/useRepPulse'
import { usePressRepeat } from '../../hooks/usePressRepeat'
import { poseFeedback } from '../../lib/feedback'
import { CONNECTION_LABEL, fmtClock, fmtNum, loadLevel, TRACK_LABEL } from '../../lib/format'
import * as api from '../../api'
import type { VersionScreenProps } from '../registry'
import './core.css'

/**
 * CORE — 연산 집중 · 무영상.
 *
 * 카메라 영상도 포즈 그리기도 없이 **스쿼트 카운트 + 장치 상태 수치만**
 * 보여준다. `/stream.mjpg`를 아예 안 열어서 클라이언트 영상 디코딩과
 * 서버의 스트리밍 스레드가 없다. 저사양/저대역 환경, 또는 "숫자만 보면
 * 되는" 모니터링용.
 *
 * 주의: 서버(main.py) 자체는 이 세션에서 안 건드렸으므로 여전히 매 프레임
 * 인코딩한다(뷰어 유무와 무관). 즉 이 시안은 클라이언트·네트워크 부담을
 * 없앨 뿐, 로봇 추론 속도를 직접 올리진 않는다. (서버가 뷰어 없을 때
 * 인코딩까지 건너뛰게 하려면 백엔드 게이팅이 별도로 필요 — 기존 동작
 * 보존을 위해 지금은 미적용.)
 */
export default function Core({ stats, connection, role, demo, onOpenPicker }: VersionScreenProps) {
  const control = useOperatorControl(role, stats?.app.control)
  const isOperator = role === 'operator'

  const squat = stats?.squat
  const reps = squat?.reps ?? 0
  const session = stats?.app.session
  const target = session?.target_reps ?? 20
  const angle = stats?.angle_deg.used ?? null
  const fb = poseFeedback(stats)
  const { pulsing } = useRepPulse(reps)

  const conn = CONNECTION_LABEL[connection]
  const track = stats ? TRACK_LABEL[stats.ptz.state] ?? TRACK_LABEL.lost : null
  const down = squat?.thresholds_deg.down ?? 100
  const up = squat?.thresholds_deg.up ?? 150
  const floor = down - 30
  const depth = angle == null ? 0 : Math.max(0, Math.min(100, ((up - angle) / (up - floor)) * 100))
  const gatePct = ((up - down) / (up - floor)) * 100
  const deepEnough = angle != null && angle <= down
  const pct = target > 0 ? Math.min(100, Math.round((reps / target) * 100)) : 0

  const cpuLvl = loadLevel(stats?.cpu_percent, 85, 95)
  const tempLvl = loadLevel(stats?.cpu_temp_c, 75, 82)

  const guarded = async (fn: () => Promise<unknown>) => {
    if (await control.requestControl()) await fn()
  }
  const pan = (d: number) => api.sendPtz('pan', { delta_deg: d })
  const tilt = (d: number) => api.sendPtz('tilt', { delta_deg: -d })

  return (
    <div className="core">
      <header className="core__bar">
        <span className="core__id">
          <i className="core__dot" data-tone={conn.tone} /> CORE
        </span>
        <span className="core__headless">무영상 · HEADLESS</span>
        <div className="core__bar-r">
          <Read label="LINK" value={conn.en} tone={conn.tone} />
          <Read label="FPS" value={fmtNum(stats?.fps, 1)} />
          <Read label="ROLE" value={isOperator ? 'OP' : 'VIEW'} />
          {demo && <span className="core__demo">DEMO</span>}
          <button className="core__ui" onClick={onOpenPicker}>시안</button>
        </div>
      </header>

      <main className="core__grid">
        {/* ---------- 스쿼트 ---------- */}
        <section className="core__panel core__squat">
          <div className="core__panel-h"><span>SQUAT</span><span className="core__panel-h-r">{session?.status?.toUpperCase() ?? 'IDLE'} · {fmtClock(session?.elapsed_ms ?? 0)}</span></div>
          <div className="core__squat-body">
            <div className={`core__count hcb-tnum${pulsing ? ' is-pulse' : ''}`}>
              {String(reps).padStart(2, '0')}<span className="core__count-t">/{target}</span>
            </div>
            <div className="core__prog" role="meter" aria-valuenow={reps} aria-valuemin={0} aria-valuemax={target}>
              <div className="core__prog-fill" style={{ width: `${pct}%` }} />
              <span className="core__prog-pct hcb-tnum">{pct}%</span>
            </div>

            <div className="core__depth">
              <div className="core__depth-h">
                <span>DEPTH · {squat?.state ?? '—'}</span>
                <b className="hcb-tnum">{angle == null ? '—' : `${Math.round(angle)}°`}</b>
              </div>
              <div className="core__depth-track">
                <div className="core__depth-fill" data-deep={deepEnough} style={{ width: `${depth}%` }} />
                <span className="core__depth-gate" style={{ left: `${gatePct}%` }} />
              </div>
              <div className="core__depth-legend">
                <span>{up}° 기립</span>
                <span className="core__depth-gate-l" style={{ left: `${gatePct}%` }}>{down}° 인정</span>
              </div>
            </div>

            <p className="core__fb" data-tone={fb.tone}>{fb.text}</p>
          </div>
        </section>

        {/* ---------- 장치 ---------- */}
        <section className="core__panel core__dev">
          <div className="core__panel-h"><span>DEVICE</span><span className="core__panel-h-r">UNO Q · Dragonwing</span></div>
          <div className="core__cells">
            <Cell label="CPU" value={fmtNum(stats?.cpu_percent, 0)} unit="%" tone={cpuLvl} />
            <Cell label="TEMP" value={fmtNum(stats?.cpu_temp_c, 0)} unit="°C" tone={tempLvl} />
            <Cell label="FPS" value={fmtNum(stats?.fps, 1)} unit="hz" />
            <Cell label="LOOP" value={fmtNum(stats?.loop_ms, 0)} unit="ms" />
            <Cell label="RAM" value={fmtNum(stats?.rss_mb, 0)} unit="mb" />
            <Cell label="DROP" value={String(stats?.dropped_frames ?? 0)} unit="fr" tone={(stats?.dropped_frames ?? 0) > 30 ? 'warn' : 'ok'} />
            <Cell label="PAN" value={`${(stats?.ptz.pan_deg ?? 0) >= 0 ? '+' : ''}${fmtNum(stats?.ptz.pan_deg, 0)}`} unit="°" />
            <Cell label="TILT" value={`${(stats?.ptz.tilt_deg ?? 0) >= 0 ? '+' : ''}${fmtNum(stats?.ptz.tilt_deg, 0)}`} unit="°" />
          </div>
          <div className="core__meta">
            <span>TRACK <b data-tone={track?.tone}>{track?.en ?? '—'}</b></span>
            <span>AUTO <b>{stats?.ptz.auto_track_enabled ? 'ON' : 'OFF'}</b></span>
            <span>VIEW <b>{stats?.app.viewer_count ?? 0}</b></span>
            <span>FRAME <b className="hcb-tnum">{stats?.frame ?? 0}</b></span>
          </div>
        </section>

        {/* ---------- 조작 ---------- */}
        <section className="core__panel core__ctl">
          <div className="core__panel-h">
            <span>CONTROL</span>
            <span className="core__panel-h-r">{isOperator ? (control.iAmHolder ? 'GRANTED' : 'LOCKED') : 'VIEW ONLY'}</span>
          </div>
          {!isOperator ? (
            <p className="core__ctl-note">관측 전용. 조작은 <code>?role=operator</code>로 접속한 기기에서.</p>
          ) : (
            <div className="core__ctl-body">
              <div className="core__btns">
                {session?.status === 'running' ? (
                  <>
                    <button className="core__btn" onClick={() => guarded(api.sessionPause)}>PAUSE</button>
                    <button className="core__btn" onClick={() => guarded(api.sessionFinish)}>STOP</button>
                  </>
                ) : session?.status === 'paused' ? (
                  <>
                    <button className="core__btn core__btn--go" onClick={() => guarded(api.sessionResume)}>RESUME</button>
                    <button className="core__btn" onClick={() => guarded(api.sessionFinish)}>STOP</button>
                  </>
                ) : (
                  <button className="core__btn core__btn--go" onClick={() => guarded(() => api.sessionStart(target))}>START</button>
                )}
                <button className="core__btn" onClick={() => guarded(api.sessionReset)}>RESET</button>
              </div>

              <div className="core__row">
                <span>AUTO TRACK</span>
                <button className={`core__sw${stats?.ptz.auto_track_enabled ? ' is-on' : ''}`} role="switch"
                        aria-checked={!!stats?.ptz.auto_track_enabled}
                        onClick={() => guarded(() => api.sendPtz('auto_track', { enabled: !stats?.ptz.auto_track_enabled }))}>
                  <i />
                </button>
              </div>

              <div className="core__row core__row--pad">
                <span>PTZ <em>(무영상 · 블라인드)</em></span>
                <div className="core__pad">
                  <PadBtn cls="up" label="▲" onFire={() => guarded(() => tilt(2))} />
                  <PadBtn cls="left" label="◀" onFire={() => guarded(() => pan(-2))} />
                  <button className="core__pad-c" onClick={() => guarded(() => api.sendPtz('center'))}>⌂</button>
                  <PadBtn cls="right" label="▶" onFire={() => guarded(() => pan(2))} />
                  <PadBtn cls="down" label="▼" onFire={() => guarded(() => tilt(-2))} />
                </div>
              </div>
            </div>
          )}
        </section>
      </main>

      {control.pinModalOpen && (
        <PinGate busy={control.pinBusy} error={control.pinError}
                 onSubmit={control.submitPin} onCancel={control.cancelPinModal} />
      )}
    </div>
  )
}

/* ---------- 부품 ---------- */
function Read({ label, value, tone }: { label: string; value: string; tone?: string }) {
  return <span className="core__read" data-tone={tone}><em>{label}</em><b className="hcb-tnum">{value}</b></span>
}
function Cell({ label, value, unit, tone = 'ok' }: { label: string; value: string; unit: string; tone?: string }) {
  return (
    <div className="core__cell" data-tone={tone}>
      <span className="core__cell-l">{label}</span>
      <span className="core__cell-v hcb-tnum">{value}<em>{unit}</em></span>
    </div>
  )
}
function PadBtn({ cls, label, onFire }: { cls: string; label: string; onFire: () => void }) {
  const press = usePressRepeat(onFire)
  return <button className={`core__pad-b core__pad-b--${cls}`} {...press} aria-label={cls}>{label}</button>
}
function PinGate({ busy, error, onSubmit, onCancel }: { busy: boolean; error: string | null; onSubmit: (p: string) => void; onCancel: () => void }) {
  const [pin, setPin] = useState('')
  return (
    <div className="core__gate" onClick={onCancel} role="presentation">
      <form className="core__gate-box" onClick={(e) => e.stopPropagation()} onSubmit={(e) => { e.preventDefault(); onSubmit(pin) }}>
        <div className="core__panel-h"><span>AUTHORISATION</span><span className="core__panel-h-r">PIN</span></div>
        <input className="core__gate-in hcb-tnum" value={pin} inputMode="numeric" autoFocus aria-label="PIN" placeholder="––––"
               onChange={(e) => setPin(e.target.value.replace(/\D/g, '').slice(0, 8))} />
        {error && <p className="core__gate-err">{error}</p>}
        <div className="core__btns">
          <button type="button" className="core__btn" onClick={onCancel}>CANCEL</button>
          <button type="submit" className="core__btn core__btn--go" disabled={busy || !pin}>{busy ? '···' : 'UNLOCK'}</button>
        </div>
      </form>
    </div>
  )
}
