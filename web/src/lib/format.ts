/** 네 버전이 공유하는 포맷터. 표기 규칙이 버전마다 갈리지 않게 한 곳에 모은다. */

export function fmtClock(ms: number): string {
  const s = Math.max(0, Math.floor(ms / 1000))
  const mm = String(Math.floor(s / 60)).padStart(2, '0')
  const ss = String(s % 60).padStart(2, '0')
  return `${mm}:${ss}`
}

/** 값이 없을 때 '0'이 아니라 em dash를 쓴다 — 0과 "모름"은 다른 상태다. */
export function fmtNum(v: number | null | undefined, digits = 0): string {
  if (v == null || Number.isNaN(v)) return '—'
  return v.toFixed(digits)
}

export function fmtDeg(v: number | null | undefined): string {
  return v == null ? '—' : `${Math.round(v)}°`
}

export function pct(v: number, max: number): number {
  if (max <= 0) return 0
  return Math.max(0, Math.min(100, (v / max) * 100))
}

export type Load = 'ok' | 'warn' | 'crit' | 'idle'

/** CPU/온도처럼 "여유가 있나"를 색으로 읽게 하는 공통 구간 판정. */
export function loadLevel(v: number | null | undefined, warn = 70, crit = 90): Load {
  if (v == null) return 'idle'
  if (v >= crit) return 'crit'
  if (v >= warn) return 'warn'
  return 'ok'
}

export const EXERCISE_LABEL: Record<string, string> = {
  squat: '스쿼트',
  pushup: '푸시업',
  unknown: '인식 중',
}

export const TRACK_LABEL: Record<string, { ko: string; en: string; tone: Load }> = {
  in_frame: { ko: '추적 중', en: 'TRACKING', tone: 'ok' },
  edge: { ko: '가장자리', en: 'EDGE', tone: 'warn' },
  lost: { ko: '놓침', en: 'LOST', tone: 'crit' },
}

export const CONNECTION_LABEL: Record<string, { ko: string; en: string; tone: Load }> = {
  online: { ko: '연결됨', en: 'ONLINE', tone: 'ok' },
  connecting: { ko: '연결 중', en: 'CONNECTING', tone: 'idle' },
  reconnecting: { ko: '재연결 중', en: 'RETRYING', tone: 'warn' },
  offline: { ko: '연결 끊김', en: 'OFFLINE', tone: 'crit' },
}
