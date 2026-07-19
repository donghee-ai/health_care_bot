import { useCallback, useEffect, useRef, useState } from 'react'
import { claimControl, getClientId, heartbeatControl, releaseControl } from '../api'
import type { ControlSnapshot, Role } from '../types'

const HEARTBEAT_MS = 20_000
const URL_PIN_KEY = 'hcb.last_pin'

export function useOperatorControl(role: Role, control: ControlSnapshot | undefined) {
  const clientId = getClientId()
  const [pinModalOpen, setPinModalOpen] = useState(false)
  const [pinError, setPinError] = useState<string | null>(null)
  const [pinBusy, setPinBusy] = useState(false)
  // claim 성공 직후 ~500ms polling이 따라잡기 전까지 배지가 즉시 반영되도록 하는 낙관적 상태.
  // 서버 snapshot이 도착하면 그걸로 대체되므로 실제 소유권 판정에는 영향 없음.
  const [optimisticHolder, setOptimisticHolder] = useState(false)
  const resolverRef = useRef<((ok: boolean) => void) | null>(null)

  const iAmHolder = optimisticHolder || (!!control?.locked && control.locked_by === clientId)
  const lockedByOther = !!control?.locked && !!control.locked_by && control.locked_by !== clientId && !optimisticHolder

  useEffect(() => {
    if (!control) return
    if (control.locked && control.locked_by === clientId) setOptimisticHolder(false)
    else if (control.locked && control.locked_by !== clientId) setOptimisticHolder(false)
  }, [control, clientId])

  // 다른 운영자가 세션을 넘겨받은 뒤 하트비트로 lock을 계속 연장.
  useEffect(() => {
    if (role !== 'operator' || !iAmHolder) return
    const t = setInterval(() => {
      heartbeatControl().catch(() => {})
    }, HEARTBEAT_MS)
    return () => clearInterval(t)
  }, [role, iAmHolder])

  // 새로고침 후에도 같은 PIN이면 자동 재획득 시도 (배지 없이 조용히).
  useEffect(() => {
    if (role !== 'operator' || iAmHolder) return
    const savedPin = sessionStorage.getItem(URL_PIN_KEY)
    if (!savedPin) return
    claimControl(savedPin).catch(() => {})
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [role])

  useEffect(() => {
    return () => {
      if (iAmHolder) releaseControl().catch(() => {})
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const submitPin = useCallback(async (pin: string) => {
    setPinBusy(true)
    setPinError(null)
    try {
      const res = await claimControl(pin)
      if (res.ok) {
        sessionStorage.setItem(URL_PIN_KEY, pin)
        setOptimisticHolder(true)
        setPinModalOpen(false)
        resolverRef.current?.(true)
        resolverRef.current = null
        return true
      }
      const msg = res.error === 'locked_by_other'
        ? '다른 기기가 제어 중입니다'
        : 'PIN이 올바르지 않습니다'
      setPinError(msg)
      return false
    } catch {
      setPinError('네트워크 오류')
      return false
    } finally {
      setPinBusy(false)
    }
  }, [])

  /** 제어권을 아직 못 얻었으면 PIN 모달을 띄우고, 얻으면 즉시 true. */
  const requestControl = useCallback((): Promise<boolean> => {
    if (iAmHolder) return Promise.resolve(true)
    setPinError(null)
    setPinModalOpen(true)
    return new Promise((resolve) => {
      resolverRef.current = resolve
    })
  }, [iAmHolder])

  const cancelPinModal = useCallback(() => {
    setPinModalOpen(false)
    resolverRef.current?.(false)
    resolverRef.current = null
  }, [])

  return {
    clientId,
    iAmHolder,
    lockedByOther,
    pinModalOpen,
    pinError,
    pinBusy,
    requestControl,
    submitPin,
    cancelPinModal,
  }
}
