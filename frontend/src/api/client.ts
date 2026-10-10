// Data layer. VITE_DATA_SOURCE=fixtures (default) reads contract/fixtures/;
// VITE_DATA_SOURCE=live calls the core API at VITE_CORE_API_URL.
import type {
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
