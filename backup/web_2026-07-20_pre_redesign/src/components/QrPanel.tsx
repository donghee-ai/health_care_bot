import { useState } from 'react'
import { QRCodeSVG } from 'qrcode.react'
import { Check, Copy } from 'lucide-react'

function CopyRow({ label, url }: { label: string; url: string }) {
  const [copied, setCopied] = useState(false)
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(url)
      setCopied(true)
      setTimeout(() => setCopied(false), 1500)
    } catch {
      /* clipboard unavailable — no-op */
    }
  }
  return (
    <div className="hcb-qr-card">
      <div className="hcb-qr-card__head">
        <span>{label}</span>
        <button className="hcb-qr-card__copy" onClick={copy}>
          {copied ? <Check size={13} /> : <Copy size={13} />}
          {copied ? '복사됨' : '복사'}
        </button>
      </div>
      <div className="hcb-qr-card__body">
        <QRCodeSVG value={url} size={128} fgColor="#172033" bgColor="#ffffff" level="M" />
        <div className="hcb-qr-card__url">{url}</div>
      </div>
    </div>
  )
}

export function QrPanel({ isOperator }: { isOperator: boolean }) {
  const origin = window.location.origin
  const viewerUrl = `${origin}/app?role=viewer`
  const operatorUrl = `${origin}/app?role=operator`

  return (
    <div className="hcb-qr-panel">
      <CopyRow label="관람객용 QR (viewer)" url={viewerUrl} />
      {isOperator && <CopyRow label="운영자용 QR (operator)" url={operatorUrl} />}
    </div>
  )
}
