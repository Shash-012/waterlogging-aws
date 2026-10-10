// The contract's pump-plan rule, used only to fake GET /pumps in fixtures mode.
// Live mode always uses Agent A's API.
import type { Hotspot, PumpPlan, Snapshot } from '../types/contract'

const LEVEL_ORDER = { LOW: 0, WATCH: 1, HIGH: 2, CRITICAL: 3 } as const

export function planPumps(snapshot: Snapshot, hotspots: Hotspot[], count: number): PumpPlan {
  const importance = new Map(hotspots.map((h) => [h.hotspot_id, h.importance]))
  const spots = [...snapshot.hotspots].sort(
    (a, b) =>
      LEVEL_ORDER[b.level] - LEVEL_ORDER[a.level] ||
      b.risk - a.risk ||
      (importance.get(b.hotspot_id) ?? 0) - (importance.get(a.hotspot_id) ?? 0),
  )
  const pumps = new Map<string, number>()
  let left = count
  for (const s of spots) {
    if ((s.level === 'HIGH' || s.level === 'CRITICAL') && left > 0) {
      pumps.set(s.hotspot_id, 1)
      left--
    }
  }
  for (const s of spots) {
    if (s.level === 'CRITICAL' && pumps.has(s.hotspot_id) && left > 0) {
      pumps.set(s.hotspot_id, 2)
      left--
    }
  }
  for (const s of spots) {
    if (s.level === 'WATCH' && left > 0) {
      pumps.set(s.hotspot_id, 1)
      left--
    }
  }
  return {
    run_id: snapshot.run_id,
    pumps_available: count,
    assignments: spots
      .filter((s) => pumps.has(s.hotspot_id))
      .map((s) => ({ hotspot_id: s.hotspot_id, pumps: pumps.get(s.hotspot_id)!, level: s.level, risk: s.risk })),
    unassigned: spots.flatMap((s) =>
      (s.level === 'HIGH' || s.level === 'CRITICAL') && !pumps.has(s.hotspot_id)
        ? [{ hotspot_id: s.hotspot_id, level: s.level, risk: s.risk }]
        : [],
    ),
  }
}
