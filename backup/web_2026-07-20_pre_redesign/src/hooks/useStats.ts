import { useEffect, useRef, useState } from 'react'
import { getStats } from '../api'
import type { Stats } from '../types'

export type ConnectionState = 'connecting' | 'online' | 'reconnecting' | 'offline'

const POLL_MS = 500
const OFFLINE_AFTER_MS = 4000

export function useStats() {
  const [stats, setStats] = useState<Stats | null>(null)
  const [connection, setConnection] = useState<ConnectionState>('connecting')
  const lastOkRef = useRef<number>(0)
  const failStreakRef = useRef(0)

  useEffect(() => {
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
  }, [])

  return { stats, connection }
}
