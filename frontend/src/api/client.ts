// Data layer. VITE_DATA_SOURCE=fixtures (default) reads contract/fixtures/;
// VITE_DATA_SOURCE=live calls the core API at VITE_CORE_API_URL.
import { formatIstDate, formatIstTime } from '../lib/format'
import type {
  AlertRequest,
  AlertResponse,
  Health,
  Hotspot,
  HotspotList,
  PumpPlan,
  Replay,
  ReplayIndex,
  Snapshot,
} from '../types/contract'

export type DataSource = 'fixtures' | 'live'

export const dataSource: DataSource =
  import.meta.env.VITE_DATA_SOURCE === 'live' ? 'live' : 'fixtures'

const coreApiUrl = (import.meta.env.VITE_CORE_API_URL ?? '').replace(/\/+$/, '')

export class ApiError extends Error {
  status: number
  code: string
  constructor(status: number, code: string, message: string) {
    super(message)
    this.status = status
    this.code = code
  }
}

async function getLive<T>(path: string): Promise<T> {
  if (!coreApiUrl) throw new ApiError(0, 'config', 'VITE_CORE_API_URL is not set')
  const res = await fetch(`${coreApiUrl}${path}`)
  const body = await res.json().catch(() => null)
  if (!res.ok) {
    const err = body?.error
    throw new ApiError(res.status, err?.code ?? 'http', err?.message ?? res.statusText)
  }
  return body as T
}

// Fixtures are loaded lazily so a live build doesn't load them up front.
const fixtures = import.meta.glob<{ default: unknown }>('../../../contract/fixtures/*.json')

async function getFixture<T>(name: string): Promise<T> {
  const load = fixtures[`../../../contract/fixtures/${name}.json`]
  if (!load) throw new ApiError(404, 'not_found', `No fixture ${name}`)
  return (await load()).default as T
}

export function getHealth(): Promise<Health> {
  return dataSource === 'live' ? getLive('/health') : getFixture('health')
}

export function getHotspots(): Promise<HotspotList> {
  return dataSource === 'live' ? getLive('/hotspots') : getFixture('hotspots')
}

export async function getHotspot(id: string): Promise<Hotspot> {
  if (dataSource === 'live') return getLive(`/hotspots/${encodeURIComponent(id)}`)
  const found = (await getFixture<HotspotList>('hotspots')).find((h) => h.hotspot_id === id)
  if (!found) throw new ApiError(404, 'not_found', `No hotspot ${id}`)
  return found
}

// In fixtures mode, `fixture` picks the rainy ("live") or the dry snapshot.
export function getLatestSnapshot(fixture: 'live' | 'dry' = 'live'): Promise<Snapshot> {
  return dataSource === 'live' ? getLive('/scores/latest') : getFixture(`snapshot_${fixture}`)
}

export function getPumpPlan(count: number): Promise<PumpPlan> {
  return dataSource === 'live' ? getLive(`/pumps?count=${count}`) : getFixture('pump_plan')
}

export function getReplays(): Promise<ReplayIndex> {
  return dataSource === 'live' ? getLive('/replays') : getFixture('replay_index')
}

export function getReplay(eventId: string): Promise<Replay> {
  return dataSource === 'live'
    ? getLive(`/replays/${encodeURIComponent(eventId)}`)
    : getFixture(`replay_${eventId}`)
}

// --- Ops API: alerts. With fixtures, POST /alerts is faked locally. ---

const opsApiUrl = (import.meta.env.VITE_OPS_API_URL ?? '').replace(/\/+$/, '')

export async function postAlert(req: AlertRequest, idToken?: string): Promise<AlertResponse> {
  if (dataSource === 'fixtures') return fakePostAlert(req)
  if (!opsApiUrl) throw new ApiError(0, 'config', 'VITE_OPS_API_URL is not set')
  const res = await fetch(`${opsApiUrl}/alerts`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...(idToken ? { Authorization: `Bearer ${idToken}` } : {}),
    },
    body: JSON.stringify(req),
  })
  const body = await res.json().catch(() => null)
  if (!res.ok) {
    const err = body?.error
    throw new ApiError(res.status, err?.code ?? 'http', err?.message ?? res.statusText)
  }
  return body as AlertResponse
}

const DEDUPE_MS = 30 * 60_000
const fakeSent = new Map<string, { at: number; response: AlertResponse }>()

async function fakePostAlert(req: AlertRequest): Promise<AlertResponse> {
  const key = `${req.hotspot_id}|${req.run_id}|${req.mode}`
  const prev = fakeSent.get(key)
  if (prev && Date.now() - prev.at < DEDUPE_MS) return { ...prev.response, duplicate: true }

  const h = await getHotspot(req.hotspot_id)
  const peak = req.peak_at ? `, peak expected ${formatIstTime(req.peak_at)}` : ''
  const peakHi = req.peak_at ? `, चरम लगभग ${formatIstTime(req.peak_at)}` : ''
  const tagEn = req.mode === 'replay' && req.event_id ? `[Replay · ${formatIstDate(req.event_id)}] ` : ''
  const tagHi = req.mode === 'replay' && req.event_id ? `[रीप्ले · ${formatIstDate(req.event_id)}] ` : ''
  const response: AlertResponse = {
    alert_id: `local-${Date.now()}`,
    sent_at: new Date().toISOString().replace(/\.\d+Z$/, 'Z'),
    duplicate: false,
    text_en: `${tagEn}${req.level} waterlogging risk at ${h.name_en} (risk ${req.risk.toFixed(3)})${peak}. ${h.avoid_en} ${h.diversion_en}`,
    text_hi: `${tagHi}${h.name_hi} पर जलभराव का खतरा: ${req.level} (जोखिम ${req.risk.toFixed(3)})${peakHi}. ${h.avoid_hi} ${h.diversion_hi}`,
    deliveries: [
      { group: 'traffic-police-demo', ok: true },
      { group: 'rwa-demo', ok: true },
    ],
  }
  fakeSent.set(key, { at: Date.now(), response })
  return response
}
