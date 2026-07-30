import { useState } from 'react'
import { ChevronLeft, ChevronRight, Cpu, Info, QrCode, Settings2, SlidersHorizontal } from 'lucide-react'
import { QrPanel } from '../components/QrPanel'
import { InfoRow } from '../components/InfoRow'
import type { ConnectionState } from '../hooks/useStats'
import type { Role, Stats } from '../types'

type PanelKey = 'device' | 'qr' | 'camera' | 'exercise' | 'app' | null

const MENU: { key: Exclude<PanelKey, null>; label: string; icon: typeof QrCode }[] = [
  { key: 'device', label: '장비 상태', icon: Cpu },
  { key: 'qr', label: 'QR 및 접속', icon: QrCode },
  { key: 'camera', label: '카메라 설정', icon: Settings2 },
  { key: 'exercise', label: '운동 인식 설정', icon: SlidersHorizontal },
  { key: 'app', label: '앱 정보', icon: Info },
]

const CONN_LABEL: Record<ConnectionState, string> = {
  connecting: '연결 중',
  online: '정상',
  reconnecting: '재연결 중',
  offline: '끊김',
}

export function MoreScreen({
  stats,
  connection,
  role,
}: {
  stats: Stats | null
  connection: ConnectionState
  role: Role
}) {
  const [panel, setPanel] = useState<PanelKey>(null)

  if (panel) {
    const item = MENU.find((m) => m.key === panel)!
    return (
      <div className="hcb-screen hcb-more">
        <button className="hcb-more__back" onClick={() => setPanel(null)}>
          <ChevronLeft size={16} /> 더보기
        </button>
        <h2 className="hcb-more__title">{item.label}</h2>

        {panel === 'device' && (
          <div className="hcb-card hcb-info-list">
            <InfoRow label="연결 상태" value={CONN_LABEL[connection]} />
            <InfoRow label="FPS" value={stats?.fps?.toFixed(1) ?? '—'} />
            <InfoRow label="추론 루프(지연)" value={stats ? `${stats.loop_ms.toFixed(0)} ms` : '—'} />
            <InfoRow label="Dropped frames" value={stats?.dropped_frames ?? '—'} />
            <InfoRow label="PTZ serial" value={stats?.ptz.enabled ? '연결됨' : '비활성'} />
            <InfoRow label="메모리 사용량" value={stats ? `${stats.rss_mb.toFixed(0)} MB` : '—'} />
            <InfoRow label="CPU 온도" value={stats?.cpu_temp_c != null ? `${stats.cpu_temp_c.toFixed(1)}°C` : '—'} />
            <InfoRow label="모델" value="MoveNet Thunder INT8 (TFLite)" />
          </div>
        )}

        {panel === 'qr' && (
          <>
            <QrPanel isOperator={role === 'operator'} />
            <div className="hcb-card hcb-info-list">
              <InfoRow label="현재 호스트" value={window.location.host} />
              <InfoRow label="접속 도메인" value="healthbot.local (mDNS)" />
            </div>
          </>
        )}

        {panel === 'camera' && (
          <div className="hcb-card hcb-info-list">
            <InfoRow label="Frame-out margin" value={stats ? `${(stats.ptz.margin * 100).toFixed(0)}%` : '—'} />
            <InfoRow label="Lost grace" value={stats ? `${stats.ptz.grace_frames} frames` : '—'} />
            <InfoRow label="Pan 누적 명령" value={stats?.ptz.pan_cmds_total ?? '—'} />
            <InfoRow label="Tilt 누적 명령" value={stats?.ptz.tilt_cmds_total ?? '—'} />
            <p className="hcb-muted hcb-more__note">
              해상도·JPEG 품질 등은 안정성 검증 후 실시간 변경을 지원할 예정입니다. 현재는 읽기 전용입니다.
            </p>
          </div>
        )}

        {panel === 'exercise' && (
          <div className="hcb-card hcb-info-list">
            <InfoRow
              label="Squat 임계각"
              value={stats ? `${stats.squat.thresholds_deg.down}° / ${stats.squat.thresholds_deg.up}°` : '—'}
            />
            <InfoRow
              label="Pushup 임계각"
              value={stats ? `${stats.pushup.thresholds_deg.down}° / ${stats.pushup.thresholds_deg.up}°` : '—'}
            />
            <InfoRow label="현재 모드" value={stats?.mode ?? '—'} />
            <InfoRow label="자세 판정" value={stats?.orientation ?? '—'} />
          </div>
        )}

        {panel === 'app' && (
          <div className="hcb-card hcb-info-list">
            <InfoRow label="기기" value="UNO Q · Qualcomm Dragonwing QRB2210" />
            <InfoRow label="앱 버전" value="1.0.0" />
            <InfoRow label="역할" value={role === 'operator' ? '운영자' : '관람객'} />
          </div>
        )}
      </div>
    )
  }

  return (
    <div className="hcb-screen hcb-more">
      <div className="hcb-card hcb-more__menu">
        {MENU.map((m) => (
          <button key={m.key} className="hcb-more__menu-item" onClick={() => setPanel(m.key)}>
            <span>
              <m.icon size={17} />
              {m.label}
            </span>
            <ChevronRight size={16} />
          </button>
        ))}
      </div>
      <div className="hcb-card hcb-more__brand">
        <div className="hcb-more__brand-mark">Q</div>
        <div>
          <strong>UNO Q Health Care Bot</strong>
          <div className="hcb-muted">버전 1.0.0</div>
        </div>
      </div>
    </div>
  )
}
