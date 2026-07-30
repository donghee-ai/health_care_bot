import type { ThemeId } from '../hooks/useTheme'

export function ThemeToggle({ theme, onChange }: { theme: ThemeId; onChange: (t: ThemeId) => void }) {
  return (
    <div className="hcb-theme-toggle" role="group" aria-label="테마 선택">
      <button
        className={theme === 'dragonwing' ? 'is-active' : ''}
        onClick={() => onChange('dragonwing')}
        title="Dragonwing (기본)"
      >
        DW
      </button>
      <button
        className={theme === 'reference' ? 'is-active' : ''}
        onClick={() => onChange('reference')}
        title="Reference (레퍼런스 톤)"
      >
        Ref
      </button>
    </div>
  )
}
