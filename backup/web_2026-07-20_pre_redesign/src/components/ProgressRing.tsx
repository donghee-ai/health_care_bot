interface ProgressRingProps {
  value: number
  target: number
  size?: number
  stroke?: number
  label?: string
}

export function ProgressRing({ value, target, size = 176, stroke = 14, label }: ProgressRingProps) {
  const radius = (size - stroke) / 2
  const circumference = 2 * Math.PI * radius
  const pct = target > 0 ? Math.min(1, value / target) : 0
  const offset = circumference * (1 - pct)

  return (
    <div className="hcb-ring" style={{ width: size, height: size }}>
      <svg width={size} height={size}>
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke="var(--bg-alt)"
          strokeWidth={stroke}
        />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke="url(#hcbRingGrad)"
          strokeWidth={stroke}
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          transform={`rotate(-90 ${size / 2} ${size / 2})`}
          style={{ transition: 'stroke-dashoffset 0.4s ease' }}
        />
        <defs>
          <linearGradient id="hcbRingGrad" x1="0" y1="0" x2="1" y2="1">
            <stop offset="0%" stopColor="var(--primary-light)" />
            <stop offset="100%" stopColor="var(--accent-blue)" />
          </linearGradient>
        </defs>
      </svg>
      <div className="hcb-ring__center">
        <div className="hcb-ring__target">목표 {target}회</div>
        <div className="hcb-ring__value">
          {value}
          <span>/{target}</span>
        </div>
        <div className="hcb-ring__pct">{Math.round(pct * 100)}%</div>
        {label && <div className="hcb-ring__label">{label}</div>}
      </div>
    </div>
  )
}
