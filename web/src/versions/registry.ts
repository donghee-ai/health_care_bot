import type { ConnectionState } from '../hooks/useStats'
import type { Role, Stats } from '../types'

/** 시안이 공통으로 받는 것 — 데이터 계약은 하나, 표현만 다르다.
 *
 * 처음엔 시안이 4종(INSTRUMENT/ALMANAC/STADIUM/CALM)이었다. 검토 결과
 * CALM만 후보로 남기고 나머지 셋은 삭제했다. 시안 전환 구조(레지스트리·
 * 피커·useVersion)는 일부러 남겨뒀다 — CALM이 "확정된 UI"가 아니라
 * "아직 검토 중인 후보"임을 구조로 드러내고, 나중에 후보를 다시 늘리거나
 * 교체할 때 그대로 쓰기 위함이다. */
export interface VersionProps {
  stats: Stats | null
  connection: ConnectionState
  role: Role
  demo: boolean
}

/** 시안 컴포넌트가 실제로 받는 props. 시안 전환 UI는 앱 껍데기가 소유하고,
    각 시안은 자기 스타일에 맞는 트리거만 그린다. */
export type VersionScreenProps = VersionProps & { onOpenPicker: () => void }

export type VersionId = 'calm' | 'rehab' | 'session' | 'pulse' | 'aurora' | 'core'

export interface VersionMeta {
  id: VersionId
  /** 시안 이름 */
  name: string
  /** 한 줄 성격 */
  tagline: string
  /** 어떤 레퍼런스 계열에서 왔는지 — 시안 고를 때 근거가 보이게 */
  lineage: string
  /** 피커에서 보여줄 대표 색 3개 */
  swatch: [string, string, string]
  scheme: 'dark' | 'light'
}

export const VERSIONS: VersionMeta[] = [
  {
    id: 'calm',
    name: 'CALM',
    tagline: '숨쉬는 코치',
    lineage: 'Gentler Streak · Apple Fitness · Things 3',
    swatch: ['#eef2ef', '#0f4c3a', '#f2b705'],
    scheme: 'light',
  },
  {
    id: 'pulse',
    name: 'PULSE',
    tagline: '밝은 프로덕트 콘솔',
    lineage: 'Toss · 프로덕트 앱 · Qualcomm Dragonwing',
    swatch: ['#f4f6fb', '#2f7dff', '#6f4dff'],
    scheme: 'light',
  },
  {
    id: 'aurora',
    name: 'AURORA',
    tagline: '유리 대시보드',
    lineage: '글래스모피즘 · 플로팅 바 · 소프트 대시보드',
    swatch: ['#e8eefb', '#7c9cff', '#6d5efc'],
    scheme: 'light',
  },
  {
    id: 'core',
    name: 'CORE',
    tagline: '연산 집중 · 무영상',
    lineage: '카메라/포즈 없이 스쿼트+장치 수치만',
    swatch: ['#0b0e13', '#4fd1c4', '#9aa4b2'],
    scheme: 'dark',
  },
  {
    id: 'rehab',
    name: 'CARE',
    tagline: '신뢰하는 재활 코치',
    lineage: 'Hinge Health · Sword Health',
    swatch: ['#f4f0e7', '#135842', '#e26e3e'],
    scheme: 'light',
  },
  {
    id: 'session',
    name: 'LIVE',
    tagline: '세션 집중 스포츠',
    lineage: 'Apple Fitness+ · Gentler Streak',
    swatch: ['#0d100e', '#b9ff35', '#f4f1e9'],
    scheme: 'dark',
  },
]

export const DEFAULT_VERSION: VersionId = 'calm'

export function isVersionId(v: string | null): v is VersionId {
  return !!v && VERSIONS.some((x) => x.id === v)
}
