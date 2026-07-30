import { useCallback, useEffect, useState } from 'react'
import { DEFAULT_VERSION, isVersionId, VERSIONS, type VersionId } from '../versions/registry'

const KEY = 'hcb.ui_version'

/**
 * 어떤 시안을 볼지 결정한다. 우선순위: URL(?ui=) > localStorage > 기본값.
 *
 * URL을 1순위로 둔 건 시연 중에 링크/QR만 바꿔서 시안을 전환하기 위해서다.
 * 고른 값은 저장되므로 새로고침해도 유지된다.
 */
export function useVersion() {
  const [version, setVersionState] = useState<VersionId>(() => {
    const fromUrl = new URLSearchParams(window.location.search).get('ui')
    if (isVersionId(fromUrl)) return fromUrl
    const saved = localStorage.getItem(KEY)
    if (isVersionId(saved)) return saved
    return DEFAULT_VERSION
  })

  const setVersion = useCallback((v: VersionId) => {
    setVersionState(v)
    localStorage.setItem(KEY, v)
    // 주소도 같이 갱신 — 지금 보고 있는 시안을 그대로 공유할 수 있어야 한다.
    const url = new URL(window.location.href)
    url.searchParams.set('ui', v)
    window.history.replaceState({}, '', url)
  }, [])

  // 시안마다 배경색이 완전히 달라서, 브라우저 UI(주소창)까지 맞춰준다.
  useEffect(() => {
    const meta = VERSIONS.find((v) => v.id === version)
    if (!meta) return
    document.documentElement.dataset.ui = version
    document.documentElement.style.colorScheme = meta.scheme
    let tag = document.querySelector('meta[name="theme-color"]')
    if (!tag) {
      tag = document.createElement('meta')
      tag.setAttribute('name', 'theme-color')
      document.head.appendChild(tag)
    }
    tag.setAttribute('content', meta.swatch[0])
  }, [version])

  return { version, setVersion }
}
