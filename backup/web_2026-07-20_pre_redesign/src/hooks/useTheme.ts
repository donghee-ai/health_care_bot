import { useCallback, useEffect, useState } from 'react'

export type ThemeId = 'dragonwing' | 'reference'
const KEY = 'hcb.theme'

function readInitial(): ThemeId {
  const saved = localStorage.getItem(KEY)
  return saved === 'reference' ? 'reference' : 'dragonwing'
}

export function useTheme() {
  const [theme, setThemeState] = useState<ThemeId>(readInitial)

  useEffect(() => {
    document.documentElement.dataset.theme = theme
  }, [theme])

  const setTheme = useCallback((t: ThemeId) => {
    localStorage.setItem(KEY, t)
    setThemeState(t)
  }, [])

  const toggle = useCallback(() => {
    setTheme(theme === 'dragonwing' ? 'reference' : 'dragonwing')
  }, [theme, setTheme])

  return { theme, setTheme, toggle }
}
