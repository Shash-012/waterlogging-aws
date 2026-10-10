import { describe, expect, it } from 'vitest'
import { getHotspots, getLatestSnapshot, getReplay } from '../api/client'
import pumpPlanFixture from '../../../contract/fixtures/pump_plan.json'
import { relativePeak } from './format'
import { HEADLINE_EVENT, readPresentMode } from './present'
import { planPumps } from './pumps'
import { formatHours, reportCallouts, replayLabel } from './replay'

describe('planPumps (fixtures stand-in for GET /pumps)', () => {
  it('matches the contract pump-plan fixture for 6 pumps', async () => {
    const plan = planPumps(await getLatestSnapshot(), await getHotspots(), 6)
    expect(plan).toEqual(pumpPlanFixture)
  })

  it('lists every HIGH-or-above spot as unassigned with 0 pumps', async () => {
    const snap = await getLatestSnapshot()
    const plan = planPumps(snap, await getHotspots(), 0)
    expect(plan.assignments).toEqual([])
    const highOrAbove = snap.hotspots.filter((h) => h.level === 'HIGH' || h.level === 'CRITICAL')
    expect(plan.unassigned).toHaveLength(highOrAbove.length)
  })

  it('leaves nothing unassigned and never exceeds 2 pumps per spot with 50 pumps', async () => {
    const plan = planPumps(await getLatestSnapshot(), await getHotspots(), 50)
    expect(plan.unassigned).toEqual([])
    expect(Math.max(...plan.assignments.map((a) => a.pumps))).toBeLessThanOrEqual(2)
    expect(plan.assignments.some((a) => a.level === 'LOW')).toBe(false)
  })
})

describe('replay callouts', () => {
  it('agree with the replay fixture metrics', async () => {
    const replay = await getReplay('2026-08-25')
    const callouts = reportCallouts(replay)
    const leads = callouts.flatMap((c) => (c.lead_hours === null ? [] : [c.lead_hours])).sort((a, b) => a - b)
    expect(callouts).toHaveLength(replay.metrics.spots_reported)
    expect(leads).toHaveLength(replay.metrics.flagged_before_report)
    const mid = leads.length / 2
    const median = leads.length % 2 ? leads[Math.floor(mid)] : (leads[mid - 1] + leads[mid]) / 2
    // The fixture rounds the median to one decimal.
    expect(median).toBeCloseTo(replay.metrics.median_lead_hours!, 1)
  })

  it('?present=1 defaults to the 28 Jun 2024 headline replay; ?event overrides it', () => {
    expect(readPresentMode('?present=1')).toEqual({ present: true, eventId: '2024-06-28' })
    expect(readPresentMode('?present=1&event=2026-08-25')).toEqual({ present: true, eventId: '2026-08-25' })
    expect(readPresentMode('')).toEqual({ present: false, eventId: null })
    expect(replayLabel(HEADLINE_EVENT)).toBe('Replay of 28 Jun 2024')
  })

  it('formats labels', () => {
    expect(replayLabel('2026-08-25')).toBe('Replay of 25 Aug 2026')
    expect(formatHours(4)).toBe('4 h')
    expect(formatHours(3.8333)).toBe('3.8 h')
    expect(relativePeak('2026-10-09T17:00:00Z', '2026-10-09T14:00:00Z')).toBe('in 3 h')
    expect(relativePeak(null, '2026-10-09T14:00:00Z')).toBe('no rain forecast')
  })
})
