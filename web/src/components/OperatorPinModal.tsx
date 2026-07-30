import { useState } from 'react'
import './operator-pin-modal.css'

interface Props {
  busy: boolean
  error: string | null
  tone?: 'light' | 'dark'
  onSubmit: (pin: string) => void
  onCancel: () => void
}

export function OperatorPinModal({
  busy,
  error,
  tone = 'light',
  onSubmit,
  onCancel,
}: Props) {
  const [pin, setPin] = useState('')

  return (
    <div className={`opm opm--${tone}`} onClick={onCancel} role="presentation">
      <form
        className="opm__box"
        onClick={(event) => event.stopPropagation()}
        onSubmit={(event) => {
          event.preventDefault()
          onSubmit(pin)
        }}
      >
        <span className="opm__eyebrow">운영자 확인</span>
        <h2 className="opm__title">로봇을 조작하려면 PIN이 필요해요</h2>
        <p className="opm__copy">한 번에 한 명의 운영자만 운동 세션과 카메라를 제어할 수 있습니다.</p>
        <input
          className="opm__input hcb-tnum"
          value={pin}
          onChange={(event) => setPin(event.target.value.replace(/\D/g, '').slice(0, 8))}
          inputMode="numeric"
          autoComplete="one-time-code"
          placeholder="PIN 입력"
          aria-label="운영자 PIN"
          autoFocus
        />
        {error && <p className="opm__error">{error}</p>}
        <div className="opm__actions">
          <button type="button" className="opm__button" onClick={onCancel}>취소</button>
          <button type="submit" className="opm__button opm__button--primary" disabled={busy || !pin}>
            {busy ? '확인 중…' : '확인'}
          </button>
        </div>
      </form>
    </div>
  )
}
