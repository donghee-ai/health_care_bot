import { useCallback, useEffect, useRef, useState } from 'react'
import type { ConnectionState } from './useStats'

/**
 * MJPEG 스트림의 "동작"만 담당한다 — 생김새는 각 시안이 알아서 그린다.
 *
 * <img>에 붙은 multipart 스트림은 끊겨도 브라우저가 재시도하지 않고
 * 마지막 프레임을 그대로 붙들고 있는다. 그래서 연결이 회복될 때
 * src에 쿼리를 붙여 강제로 다시 붙게 만든다.
 */
export function useMjpeg(connection: ConnectionState, demo: boolean) {
  const [nonce, setNonce] = useState(0)
  const containerRef = useRef<HTMLDivElement>(null)
  const [fullscreen, setFullscreen] = useState(false)

  useEffect(() => {
    if (connection !== 'reconnecting' && connection !== 'offline') return
    const t = setInterval(() => setNonce((n) => n + 1), 2000)
    return () => clearInterval(t)
  }, [connection])

  useEffect(() => {
    const onFs = () => setFullscreen(!!document.fullscreenElement)
    document.addEventListener('fullscreenchange', onFs)
    return () => document.removeEventListener('fullscreenchange', onFs)
  }, [])

  const toggleFullscreen = useCallback(() => {
    if (document.fullscreenElement) document.exitFullscreen()
    else containerRef.current?.requestFullscreen?.()
  }, [])

  // 데모 모드에는 실제 스트림이 없다. src를 비워두고 시안이 대체 화면을 그린다.
  const src = demo ? null : `/stream.mjpg${nonce ? `?r=${nonce}` : ''}`
  const live = !demo && connection !== 'offline' && connection !== 'connecting'

  return { src, live, containerRef, fullscreen, toggleFullscreen }
}
