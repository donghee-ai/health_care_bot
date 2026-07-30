import type { Stats } from '../types'

export interface FeedbackResult {
  text: string
  tone: 'success' | 'warning' | 'neutral'
}

/** 각도/상태 기반 실시간 자세 피드백. 의료 진단 표현은 사용하지 않는다. */
export function poseFeedback(stats: Stats | null): FeedbackResult {
  if (!stats || !stats.exercise_active || stats.exercise_active === 'unknown') {
    return { text: '사람을 인식하는 중입니다', tone: 'neutral' }
  }

  const angle = stats.angle_deg.used
  if (angle == null) {
    return { text: '관절 각도를 계산할 수 없습니다', tone: 'neutral' }
  }

  if (stats.exercise_active === 'squat') {
    const c = stats.squat
    if (c.state === 'DOWN') {
      return angle > 110
        ? { text: '조금 더 내려가세요', tone: 'warning' }
        : { text: '좋은 깊이입니다', tone: 'success' }
    }
    if (c.last_rep_min_deg != null) {
      return c.last_rep_min_deg > 100
        ? { text: '조금 얕아요 — 더 깊게 앉아보세요', tone: 'warning' }
        : { text: '무릎과 발끝이 안정적입니다', tone: 'success' }
    }
    return { text: '스쿼트 준비 자세입니다', tone: 'neutral' }
  }

  if (stats.exercise_active === 'pushup') {
    const c = stats.pushup
    if (c.state === 'DOWN') {
      return angle > 100
        ? { text: '조금 더 내려가세요', tone: 'warning' }
        : { text: '좋은 깊이입니다', tone: 'success' }
    }
    if (c.last_rep_min_deg != null) {
      return c.last_rep_min_deg > 90
        ? { text: '팔꿈치를 조금 더 접어보세요', tone: 'warning' }
        : { text: '끝까지 잘 밀어냈습니다', tone: 'success' }
    }
    return { text: '푸시업 준비 자세입니다', tone: 'neutral' }
  }

  return { text: '자세 인식 중입니다', tone: 'neutral' }
}
