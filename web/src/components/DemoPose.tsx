import { useEffect, useRef, useState } from 'react'

/**
 * 데모 모드용 합성 포즈 뷰.
 *
 * 로봇 없이 시안을 볼 때 카메라 자리가 빈 사각형이면 레이아웃 판단이
 * 불가능하다. 그래서 MoveNet 17 keypoint와 같은 골격을 스쿼트 깊이에
 * 맞춰 그려서, 실제 스트림이 들어왔을 때의 밀도를 미리 볼 수 있게 한다.
 *
 * 실기와 혼동되면 안 되므로 시안 쪽에서 항상 "DEMO" 표식을 같이 띄운다.
 */

// MoveNet과 같은 연결 관계 (얼굴 세부는 생략 — 화면에서 점 뭉침만 만든다)
const EDGES: [keyof Pose, keyof Pose][] = [
  ['nose', 'neck'],
  ['neck', 'lShoulder'], ['neck', 'rShoulder'],
  ['lShoulder', 'lElbow'], ['lElbow', 'lWrist'],
  ['rShoulder', 'rElbow'], ['rElbow', 'rWrist'],
  ['lShoulder', 'lHip'], ['rShoulder', 'rHip'],
  ['lHip', 'rHip'], ['lShoulder', 'rShoulder'],
  ['lHip', 'lKnee'], ['lKnee', 'lAnkle'],
  ['rHip', 'rKnee'], ['rKnee', 'rAnkle'],
]

type Pt = [number, number]
interface Pose {
  nose: Pt; neck: Pt
  lShoulder: Pt; rShoulder: Pt
  lElbow: Pt; rElbow: Pt
  lWrist: Pt; rWrist: Pt
  lHip: Pt; rHip: Pt
  lKnee: Pt; rKnee: Pt
  lAnkle: Pt; rAnkle: Pt
}

const lerp = (a: number, b: number, t: number) => a + (b - a) * t

/** d: 0 = 기립, 1 = 최대 하강. x는 오른쪽이 +. */
function buildPose(d: number, sway: number, jitter: number): Pose {
  const cx = 50 + sway * 7
  const j = () => (Math.random() - 0.5) * jitter // 검출 흔들림 흉내

  const hipY = lerp(50, 70, d)
  const kneeY = lerp(71.5, 74, d)
  const shY = lerp(27, 47, d)
  const noseY = lerp(15.5, 35, d)
  const kneeSpread = lerp(7.5, 11, d)
  const ankleY = 92

  // 팔은 내려간 만큼 앞으로 들어올린다 (맨몸 스쿼트의 전형적 밸런스 동작)
  const elbowY = lerp(41, 50, d)
  const wristY = lerp(54, 47, d)
  const armSpread = lerp(10, 15, d)

  return {
    nose: [cx + j(), noseY + j()],
    neck: [cx + j(), shY - 3 + j()],
    lShoulder: [cx - 8.5 + j(), shY + j()],
    rShoulder: [cx + 8.5 + j(), shY + j()],
    lElbow: [cx - armSpread + j(), elbowY + j()],
    rElbow: [cx + armSpread + j(), elbowY + j()],
    lWrist: [cx - armSpread - 1 + j(), wristY + j()],
    rWrist: [cx + armSpread + 1 + j(), wristY + j()],
    lHip: [cx - 5.5 + j(), hipY + j()],
    rHip: [cx + 5.5 + j(), hipY + j()],
    lKnee: [cx - kneeSpread + j(), kneeY + j()],
    rKnee: [cx + kneeSpread + j(), kneeY + j()],
    lAnkle: [cx - 6.5 + j(), ankleY + j()],
    rAnkle: [cx + 6.5 + j(), ankleY + j()],
  }
}

interface Props {
  /** 무릎 각도(도). 여기서 깊이를 역산한다. */
  angle: number | null
  /** 좌우 위치 -1~1 (PTZ 추적 시각화와 맞물린다) */
  sway?: number
  skeleton?: string
  joint?: string
  /** 관절 강조색 — 임계 각도 도달 시 */
  hot?: string
  hotActive?: boolean
  className?: string
}

export function DemoPose({
  angle,
  sway = 0,
  skeleton = 'rgba(255,255,255,0.85)',
  joint = '#ffffff',
  hot = '#c8f751',
  hotActive = false,
  className,
}: Props) {
  // 168° 기립 ↔ 80° 최대하강 을 0~1로
  const d = angle == null ? 0 : Math.max(0, Math.min(1, (168 - angle) / 88))
  const [pose, setPose] = useState<Pose>(() => buildPose(d, sway, 0))
  const raf = useRef(0)

  useEffect(() => {
    // 500ms polling보다 촘촘하게 다시 그려야 움직임이 끊겨 보이지 않는다
    let alive = true
    const loop = () => {
      if (!alive) return
      setPose(buildPose(d, sway, 0.5))
      raf.current = window.setTimeout(loop, 90)
    }
    loop()
    return () => {
      alive = false
      clearTimeout(raf.current)
    }
  }, [d, sway])

  const stroke = hotActive ? hot : skeleton
  const dot = hotActive ? hot : joint

  return (
    <svg
      className={className}
      /* 인체가 실제로 점유하는 범위로 좁혀 잡는다. 0~100을 그대로 쓰면
         4:3 화면에서 사람이 가운데 조그맣게 떠 있어 밀도 판단이 안 된다. */
      viewBox="22 6 56 92"
      preserveAspectRatio="xMidYMid meet"
      role="img"
      aria-label="데모 자세 시각화"
    >
      {EDGES.map(([a, b]) => (
        <line
          key={`${a}-${b}`}
          x1={pose[a][0]} y1={pose[a][1]}
          x2={pose[b][0]} y2={pose[b][1]}
          stroke={stroke}
          strokeWidth={1.1}
          strokeLinecap="round"
        />
      ))}
      {Object.entries(pose).map(([k, p]) => (
        <circle key={k} cx={p[0]} cy={p[1]} r={1.5} fill={dot} />
      ))}
      {/* 무릎 각도를 재는 지점을 명시 — 이 앱이 무엇을 보고 있는지 드러낸다 */}
      <circle cx={pose.rKnee[0]} cy={pose.rKnee[1]} r={3.4} fill="none" stroke={hot} strokeWidth={0.8} opacity={0.9} />
    </svg>
  )
}
