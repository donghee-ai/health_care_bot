import { useEffect, useRef } from 'react'
import { VERSIONS, type VersionId } from '../versions/registry'

interface Props {
  open: boolean
  current: VersionId
  onSelect: (v: VersionId) => void
  onClose: () => void
}

/**
 * 시안 전환 시트.
 *
 * 네 시안은 서로 다른 제품처럼 보이는 게 목적이라 공통 UI를 최대한 안 만들었다.
 * 이 시트만 예외 — 시안 밖의 "메타" 레이어라서, 어느 시안 위에 떠도 이물감이
 * 없도록 무채색 + 시스템 폰트로 중립적으로 잡았다.
 */
export function VersionPicker({ open, current, onSelect, onClose }: Props) {
  const sheetRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!open) return
    // 열리면 시트로 초점을 옮겨 키보드/스크린리더가 시트 안에서 시작하게 한다
    sheetRef.current?.focus()
    const prev = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    return () => {
      document.body.style.overflow = prev
    }
  }, [open])

  if (!open) return null

  return (
    <div className="vp-backdrop" onClick={onClose} role="presentation">
      <div
        className="vp-sheet"
        ref={sheetRef}
        tabIndex={-1}
        role="dialog"
        aria-modal="true"
        aria-label="디자인 시안 선택"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="vp-grip" aria-hidden="true" />
        <div className="vp-head">
          <h2 className="vp-title">디자인 시안</h2>
          <p className="vp-sub">
            {VERSIONS.length > 1
              ? `같은 데이터, ${VERSIONS.length}가지 해석. 숫자 키로도 전환됩니다.`
              : '로봇 확정 전 검토 중인 후보입니다.'}
          </p>
        </div>

        <ul className="vp-list">
          {VERSIONS.map((v, i) => {
            const active = v.id === current
            return (
              <li key={v.id}>
                <button
                  className={`vp-item${active ? ' is-active' : ''}`}
                  onClick={() => onSelect(v.id)}
                  aria-current={active}
                >
                  <span className="vp-swatch" aria-hidden="true">
                    {v.swatch.map((c) => (
                      <i key={c} style={{ background: c }} />
                    ))}
                  </span>
                  <span className="vp-item__text">
                    <span className="vp-item__name">
                      {v.name}
                      <em className="vp-item__tag">{v.tagline}</em>
                    </span>
                    <span className="vp-item__lineage">{v.lineage}</span>
                  </span>
                  <kbd className="vp-key">{i + 1}</kbd>
                </button>
              </li>
            )
          })}
        </ul>

        <button className="vp-close" onClick={onClose}>
          닫기
        </button>
      </div>
    </div>
  )
}
