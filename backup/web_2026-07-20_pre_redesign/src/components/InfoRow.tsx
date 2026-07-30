export function InfoRow({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="hcb-info-row">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  )
}
