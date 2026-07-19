import type { ExerciseMode, Stats } from './types'

const CLIENT_ID_KEY = 'hcb.client_id'

export function getClientId(): string {
  let id = localStorage.getItem(CLIENT_ID_KEY)
  if (!id) {
    id = 'phone-' + Math.random().toString(36).slice(2, 8)
    localStorage.setItem(CLIENT_ID_KEY, id)
  }
  return id
}

async function post<T>(path: string, body: Record<string, unknown> = {}): Promise<T> {
  const res = await fetch(path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ client_id: getClientId(), ...body }),
  })
  return res.json() as Promise<T>
}

export async function getStats(): Promise<Stats> {
  const res = await fetch('/stats.json', { cache: 'no-store' })
  if (!res.ok) throw new Error(`stats.json ${res.status}`)
  return res.json() as Promise<Stats>
}

export interface OkResponse {
  ok: boolean
  error?: string
  [key: string]: unknown
}

export const claimControl = (pin: string) => post<OkResponse>('/api/control/claim', { pin })
export const heartbeatControl = () => post<OkResponse>('/api/control/heartbeat')
export const releaseControl = () => post<OkResponse>('/api/control/release')

export const sendPtz = (command: 'pan' | 'tilt' | 'center' | 'auto_track' | 'stop', extra: Record<string, unknown> = {}) =>
  post<OkResponse>('/api/ptz', { command, ...extra })

export const setMode = (mode: ExerciseMode) => post<OkResponse>('/api/mode', { mode })

export const sessionStart = (target_reps?: number) => post<OkResponse>('/api/session/start', { target_reps })
export const sessionPause = () => post<OkResponse>('/api/session/pause')
export const sessionResume = () => post<OkResponse>('/api/session/resume')
export const sessionReset = () => post<OkResponse>('/api/session/reset')
export const sessionFinish = () => post<OkResponse>('/api/session/finish')
