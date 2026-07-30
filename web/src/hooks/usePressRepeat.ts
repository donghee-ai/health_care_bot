import { useCallback, useEffect, useRef } from 'react'

/**
 * 누르고 있으면 반복 실행. PTZ 방향키용.
 *
 * 기존 구현은 탭 1회당 명령 1회여서, 카메라를 조금 크게 돌리려면
 * 화면을 여러 번 두드려야 했다. 서보가 20ms/° 로 도는 걸 감안하면
 * 누르고 있는 동안 이어서 도는 쪽이 물리 동작과 훨씬 잘 맞는다.
 */
export function usePressRepeat(fn: () => void, { delay = 340, interval = 160 } = {}) {
  const fnRef = useRef(fn)
  fnRef.current = fn
  const timers = useRef<{ t?: number; i?: number }>({})

  const stop = useCallback(() => {
    if (timers.current.t) clearTimeout(timers.current.t)
    if (timers.current.i) clearInterval(timers.current.i)
    timers.current = {}
  }, [])

  const start = useCallback(() => {
    stop()
    fnRef.current()
    // 첫 반복까지는 뜸을 들인다 — 짧게 톡 누른 걸 연타로 오해하면 안 된다
    timers.current.t = window.setTimeout(() => {
      timers.current.i = window.setInterval(() => fnRef.current(), interval)
    }, delay)
  }, [delay, interval, stop])

  useEffect(() => stop, [stop])

  return {
    onPointerDown: (e: React.PointerEvent) => {
      e.preventDefault()
      ;(e.currentTarget as HTMLElement).setPointerCapture?.(e.pointerId)
      start()
    },
    onPointerUp: stop,
    onPointerCancel: stop,
    onPointerLeave: stop,
  }
}
