export type Role = 'viewer' | 'operator'

export type ExerciseMode = 'auto' | 'squat' | 'pushup'

export type PtzState = 'in_frame' | 'edge' | 'lost'

export interface RepCounterSnapshot {
  name: string
  state: string
  reps: number
  deepest_overall_deg: number | null
  last_rep_min_deg: number | null
  current_down_min_deg: number | null
  thresholds_deg: { down: number; up: number }
}

export interface PtzSnapshot {
  enabled: boolean
  state: PtzState
  miss_frames: number
  last_seen_x: number | null
  pan_cmds_total: number
  tilt_cmds_total: number
  margin: number
  grace_frames: number
  auto_track_enabled: boolean
  pan_deg: number
  tilt_deg: number
}

export interface SessionSnapshot {
  session_id: string | null
  mode: ExerciseMode
  status: 'idle' | 'running' | 'paused' | 'finished'
  target_reps: number
  started_at_ms: number | null
  elapsed_ms: number
  last_finished: SessionSummary | null
}

export interface SessionSummary {
  session_id: string | null
  mode: ExerciseMode
  elapsed_ms: number
  squat_reps: number
  pushup_reps: number
  squat_best_deg: number | null
  pushup_best_deg: number | null
  avg_fps: number | null
  finished_at_ms: number
}

export interface ControlSnapshot {
  locked: boolean
  locked_by: string | null
  lock_remaining_ms: number
}

export interface Stats {
  frame: number
  fps: number
  loop_ms: number
  mode: ExerciseMode
  exercise_active: 'squat' | 'pushup' | 'unknown' | null
  orientation: 'vertical' | 'horizontal' | null
  angle_deg: { left: number | null; right: number | null; used: number | null }
  person_center_norm: [number | null, number | null]
  squat: RepCounterSnapshot
  pushup: RepCounterSnapshot
  ptz: PtzSnapshot
  last_ptz_cmd: string | null
  dropped_frames: number
  rss_mb: number
  cpu_temp_c: number | null
  frame_ts_ms: number
  app: {
    session: SessionSnapshot
    control: ControlSnapshot
    viewer_count: number
  }
}
