import { useState } from 'react'
import { Lock } from 'lucide-react'

interface PinModalProps {
  open: boolean
  busy: boolean
  error: string | null
  onSubmit: (pin: string) => void
  onCancel: () => void
}

export function PinModal({ open, busy, error, onSubmit, onCancel }: PinModalProps) {
  const [pin, setPin] = useState('')
  if (!open) return null

  return (
    <div className="hcb-modal-backdrop" onClick={onCancel}>
      <div className="hcb-modal" onClick={(e) => e.stopPropagation()}>
        <div className="hcb-modal__icon">
          <Lock size={20} />
        </div>
        <h3>운영자 PIN 입력</h3>
        <p>PTZ 제어와 세션 관리를 위해 운영자 PIN이 필요합니다.</p>
        <input
          className="hcb-modal__input"
          type="password"
          inputMode="numeric"
          placeholder="PIN"
          value={pin}
          autoFocus
          onChange={(e) => setPin(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && onSubmit(pin)}
        />
        {error && <div className="hcb-modal__error">{error}</div>}
        <div className="hcb-modal__actions">
          <button className="hcb-btn hcb-btn--soft" onClick={onCancel}>
            취소
          </button>
          <button className="hcb-btn hcb-btn--primary" disabled={busy || !pin} onClick={() => onSubmit(pin)}>
            {busy ? '확인 중…' : '확인'}
          </button>
        </div>
      </div>
    </div>
  )
}
