import { AlertCircle, CheckCircle2, Info, MapPin, MemoryStick, Thermometer, Timer, Zap } from 'lucide-react'
import { LiveCamera } from '../components/LiveCamera'
import type { ConnectionState } from '../hooks/useStats'
import type { Stats } from '../types'
import { poseFeedback } from '../lib/feedback'

const TRACK_LABEL: Record<string, { text: string; tone: 'success' | 'warning' | 'danger' }> = {
  in_frame: { text: 'Tracking', tone: 'success' },
  edge: { text: 'Repositioning', tone: 'warning' },
  lost: { text: 'Lost', tone: 'danger' },
}

const FEEDBACK_ICON = { success: CheckCircle2, warning: AlertCircle, neutral: Info }

export function LiveScreen({ stats, connection }: { stats: Stats | null; connection: ConnectionState }) {
  const exercise = stats?.exercise_active
  const reps = exercise === 'squat' ? stats?.squat.reps : exercise === 'pushup' ? stats?.pushup.reps : 0
  const track = stats ? TRACK_LABEL[stats.ptz.state] ?? TRACK_LABEL.lost : undefined
  const fb = poseFeedback(stats)
  const FbIcon = FEEDBACK_ICON[fb.tone]
  const exerciseLabel = exercise === 'squat' ? 'Squat' : exercise === 'pushup' ? 'Pushup' : '대기 중'

  return (
    <div className="hcb-screen hcb-live">
      <LiveCamera
        connection={connection}
        topLeft={
          <>
            <span className="hcb-chip" style={{ background: 'rgba(255,60,60,0.85)' }}>
              <span className="hcb-badge-dot" /> LIVE
            </span>
          </>
        }
        topRight={
          track && (
            <span className="hcb-chip">
              <MapPin size={11} /> {track.text}
            </span>
          )
        }
      />

      <div className="hcb-live__side">
        <div className="hcb-live__stat hcb-card">
          <div className="hcb-live__stat-label">현재 운동</div>
          <div className="hcb-live__stat-row">
            <span className="hcb-live__exercise">{exerciseLabel}</span>
            <span className="hcb-live__reps">{reps ?? 0}<small>회</small></span>
          </div>
        </div>

        <div className={`hcb-feedback hcb-card hcb-feedback--${fb.tone}`}>
          <FbIcon size={20} />
          <span>{fb.text}</span>
        </div>

        {/* 데스크톱 전용 — 모바일에서는 라이브 화면을 카메라+현재 운동+피드백까지만
            보여준다 (index.css `.hcb-live__telemetry` 참고) */}
        <div className="hcb-live__telemetry">
          <div className="hcb-card">
            <Zap size={14} />
            <span>{stats?.fps != null ? stats.fps.toFixed(1) : '—'}</span>
            <small>FPS</small>
          </div>
          <div className="hcb-card">
            <Timer size={14} />
            <span>{stats ? `${stats.loop_ms.toFixed(0)}` : '—'}</span>
            <small>ms 지연</small>
          </div>
          <div className="hcb-card">
            <Thermometer size={14} />
            <span>{stats?.cpu_temp_c != null ? stats.cpu_temp_c.toFixed(0) : '—'}</span>
            <small>°C CPU</small>
          </div>
          <div className="hcb-card">
            <MemoryStick size={14} />
            <span>{stats ? stats.rss_mb.toFixed(0) : '—'}</span>
            <small>MB RAM</small>
          </div>
        </div>
      </div>
    </div>
  )
}
