import { useEffect, useRef, useState } from 'react'
import { getStats } from '../api'
import { isDemoForced, makeDemoStats } from '../lib/demo'
import type { Stats } from '../types'

export type ConnectionState = 'connecting' | 'online' | 'reconnecting' | 'offline'

const POLL_MS = 500
const OFFLINE_AFTER_MS = 4000
/** 이 횟수만큼 연속 실패하고 한 번도 성공한 적이 없으면 데모 데이터로 넘어간다. */
const DEMO_FALLBACK_AFTER = 4

export function useStats() {
  const [stats, setStats] = useState<Stats | null>(null)
  const [connection, setConnection] = useState<ConnectionState>('connecting')
  const [demo, setDemo] = useState(() => isDemoForced())
  const lastOkRef = useRef<number>(0)
  const failStreakRef = useRef(0)

  // 데모 모드: 로봇 없이 UI를 보는 경로. 실제 stats가 한 번이라도 오면
  // 여기로 들어오지 않으므로 디바이스 동작에는 영향이 없다.
  useEffect(() => {
    if (!demo) return
    const t0 = performance.now()
    const id = setInterval(() => {
      setStats(makeDemoStats(performance.now() - t0))
      setConnection('online')
    }, POLL_MS)
    setStats(makeDemoStats(0))
    setConnection('online')
    return () => clearInterval(id)
  }, [demo])

  useEffect(() => {
    if (demo) return
    let cancelled = false
    let timer: ReturnType<typeof setTimeout>

    async function tick() {
      try {
        const data = await getStats()
        if (cancelled) return
        setStats(data)
        lastOkRef.current = Date.now()
        failStreakRef.current = 0
        setConnection('online')
      } catch {
        if (cancelled) return
        failStreakRef.current += 1
        const sinceOk = Date.now() - lastOkRef.current
        if (lastOkRef.current === 0) {
          // 한 번도 못 붙었다 = 로봇이 없는 환경(개발 PC에서 시안 보는 중)
          if (failStreakRef.current >= DEMO_FALLBACK_AFTER) {
            setDemo(true)
            return
          }
          setConnection('connecting')
        } else if (sinceOk > OFFLINE_AFTER_MS) {
          setConnection('offline')
        } else {
          setConnection('reconnecting')
        }
      } finally {
        if (!cancelled) timer = setTimeout(tick, POLL_MS)
      }
    }

    tick()
    return () => {
      cancelled = true
      clearTimeout(timer)
    }
  }, [demo])

  return { stats, connection, demo }
}
