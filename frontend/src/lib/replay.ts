import type { Replay } from '../types/contract'
import { formatIstDate, hoursBetween } from './format'

export interface ReportCallout {
  hotspot_id: string
  first_report_at: string
  source_url: string
  note?: string
  // First frame where the spot reached HIGH or above, if before the report.
  flagged_at: string | null
  lead_hours: number | null
}

// Same definition as the replay metrics: lead = first report minus the first
// frame at HIGH or above, counted only when the flag came before the report.
export function reportCallouts(replay: Replay): ReportCallout[] {
  const firstFlag = new Map<string, string>()
  for (const frame of replay.frames) {
    for (const h of frame.hotspots) {
      if ((h.level === 'HIGH' || h.level === 'CRITICAL') && !firstFlag.has(h.hotspot_id)) {
        firstFlag.set(h.hotspot_id, frame.as_of)
      }
    }
  }
  return replay.ground_truth.map((g) => {
    const flag = firstFlag.get(g.hotspot_id) ?? null
    const lead = flag ? hoursBetween(flag, g.first_report_at) : null
    const before = lead !== null && lead > 0
    return {
      hotspot_id: g.hotspot_id,
      first_report_at: g.first_report_at,
      source_url: g.source_url,
      note: g.note ?? undefined,
      flagged_at: before ? flag : null,
      lead_hours: before ? lead : null,
    }
  })
}

export function formatHours(h: number): string {
  const rounded = Math.round(h * 10) / 10
  return `${Number.isInteger(rounded) ? rounded.toFixed(0) : rounded.toFixed(1)} h`
}

export function replayLabel(eventId: string): string {
  return `Replay of ${formatIstDate(eventId)}`
}
