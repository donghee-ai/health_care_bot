import { useEffect, useRef, useState } from 'react'
import { Maximize2, WifiOff } from 'lucide-react'
import type { ConnectionState } from '../hooks/useStats'

interface LiveCameraProps {
  connection: ConnectionState
  showGuide?: boolean
  topLeft?: React.ReactNode
  topRight?: React.ReactNode
  bottomOverlay?: React.ReactNode
  aspect?: string
}

export function LiveCamera({
  connection,
  showGuide = false,
  topLeft,
  topRight,
  bottomOverlay,
  aspect = '4 / 3',
}: LiveCameraProps) {
  const [cacheBust, setCacheBust] = useState(0)
  const containerRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (connection !== 'reconnecting' && connection !== 'offline') return
    const t = setInterval(() => setCacheBust((n) => n + 1), 2000)
    return () => clearInterval(t)
  }, [connection])

  const showOverlay = connection === 'offline' || connection === 'connecting'

  const toggleFullscreen = () => {
    if (!containerRef.current) return
    if (document.fullscreenElement) {
      document.exitFullscreen()
    } else {
      containerRef.current.requestFullscreen?.()
    }
  }

  return (
    <div className="hcb-camera" style={{ aspectRatio: aspect }} ref={containerRef}>
      {!showOverlay && (
        <img
          className="hcb-camera__img"
          src={`/stream.mjpg${cacheBust ? `?r=${cacheBust}` : ''}`}
          alt="live camera"
        />
      )}
      {showOverlay && (
        <div className="hcb-camera__offline">
          <WifiOff size={28} strokeWidth={1.6} />
          <span>{connection === 'connecting' ? '연결 중…' : '스트림 연결 끊김 — 재연결 중'}</span>
        </div>
      )}
      {showGuide && !showOverlay && (
        <div className="hcb-camera__guide">
          {Array.from({ length: 9 }).map((_, i) => (
            <span key={i} />
          ))}
        </div>
      )}
      <div className="hcb-camera__top hcb-camera__top--left">{topLeft}</div>
      <div className="hcb-camera__top hcb-camera__top--right">
        {topRight}
        <button className="hcb-camera__fs" onClick={toggleFullscreen} aria-label="전체화면">
          <Maximize2 size={14} />
        </button>
      </div>
      {bottomOverlay && <div className="hcb-camera__bottom">{bottomOverlay}</div>}
    </div>
  )
}
