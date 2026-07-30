import { useEffect, useRef, useState } from 'react'

/**
 * 횟수가 늘어난 "순간"을 감지해 짧게 true를 뱉는다.
 *
 * 500ms polling이라 숫자는 뚝 바뀌는데, 그것만으로는 1회가 인정됐다는
 * 사건성이 전혀 안 느껴진다. 네 버전 모두 이 펄스를 받아 각자의 방식으로
 * (링 튕김 / 밑줄 스윕 / 스코어보드 플래시 / 물결) 표현한다.
 */
export function useRepPulse(reps: number | undefined, holdMs = 620) {
  const [pulse, setPulse] = useState(0)
  const prev = useRef<number | undefined>(undefined)

  useEffect(() => {
    if (reps == null) return
    // 첫 관측치는 기준점만 잡는다 — 화면 진입하자마자 터지면 안 된다.
    if (prev.current == null) {
      prev.current = reps
      return
    }
    if (reps > prev.current) {
      prev.current = reps
      setPulse((n) => n + 1)
    } else if (reps < prev.current) {
      prev.current = reps // 리셋된 경우
    }
  }, [reps])

  const [active, setActive] = useState(false)
  useEffect(() => {
    if (pulse === 0) return
    setActive(true)
    const t = setTimeout(() => setActive(false), holdMs)
    return () => clearTimeout(t)
  }, [pulse, holdMs])

  return { pulseKey: pulse, pulsing: active }
}
