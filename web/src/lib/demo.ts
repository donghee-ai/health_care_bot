import type { Stats } from '../types'

/**
 * 로봇 없이 UI를 볼 수 있게 하는 모의 stats 생성기.
 *
 * 디자인 시안 검토·스크린샷·발표 리허설을 로봇 전원 없이 하려고 넣었다.
 * `?demo=1`로 강제하거나, `/stats.json`이 처음부터 안 잡히면 자동으로 켜진다
 * (로봇에 붙어 있을 때는 실제 데이터가 먼저 오므로 절대 켜지지 않는다).
 *
 * 값은 실측 범위에 맞췄다 — FPS ~10.8, CPU ~83%는 디바이스에서 실제로
 * 나온 수치다(WORK_SUMMARY.md). 그래야 시안에서 본 레이아웃이 실기에서도
 * 그대로 성립한다.
 */

export function isDemoForced(): boolean {
  return new URLSearchParams(window.location.search).get('demo') === '1'
}

/** 스크린샷 재현성을 위해 시간을 고정할 수 있게 seed를 받는다. */
export function makeDemoStats(t: number): Stats {
  // 스쿼트 1회 ≈ 3.2초 주기. 무릎 각도를 사인파로 흉내낸다.
  const period = 3200
  const phase = (t % period) / period
  const knee = 168 - 88 * Math.sin(Math.PI * phase) // 168° ↔ 80°
  const reps = Math.floor(t / period)
  const going = phase < 0.5
  const state = knee < 100 ? 'DOWN' : going ? 'DESCEND' : 'UP'

  const fps = 10.8 + Math.sin(t / 2200) * 1.6
  const cpu = 83 + Math.sin(t / 5000) * 6

  return {
    frame: Math.floor(t / 92),
    fps,
    loop_ms: 1000 / fps,
    mode: 'squat',
    exercise_active: 'squat',
    orientation: 'vertical',
    angle_deg: { left: knee + 2.1, right: knee - 1.4, used: knee },
    person_center_norm: [0.5 + Math.sin(t / 4300) * 0.16, 0.52],
    squat: {
      name: 'squat',
      state,
      reps,
      deepest_overall_deg: 80.4,
      last_rep_min_deg: 86.2,
      current_down_min_deg: state === 'DOWN' ? knee : null,
      thresholds_deg: { down: 100, up: 150 },
    },
    pushup: {
      name: 'pushup',
      state: 'UP',
      reps: 0,
      deepest_overall_deg: null,
      last_rep_min_deg: null,
      current_down_min_deg: null,
      thresholds_deg: { down: 90, up: 150 },
    },
    ptz: {
      enabled: true,
      state: 'in_frame',
      miss_frames: 0,
      last_seen_x: 0.5 + Math.sin(t / 4300) * 0.16,
      pan_cmds_total: 412 + Math.floor(t / 900),
      tilt_cmds_total: 87,
      margin: 0.18,
      grace_frames: 6,
      auto_track_enabled: true,
      pan_deg: Math.sin(t / 4300) * 22,
      tilt_deg: -4.5,
    },
    last_ptz_cmd: 'pan +1.8°',
    dropped_frames: 3,
    rss_mb: 412 + Math.sin(t / 9000) * 8,
    cpu_temp_c: 58 + Math.sin(t / 7000) * 3,
    cpu_percent: cpu,
    frame_ts_ms: Date.now(),
    app: {
      session: {
        session_id: 'demo-session',
        mode: 'squat',
        status: 'running',
        target_reps: 20,
        started_at_ms: Date.now() - t,
        elapsed_ms: t,
        last_finished: null,
      },
      control: { locked: false, locked_by: null, lock_remaining_ms: 0 },
      viewer_count: 2,
    },
  }
}
