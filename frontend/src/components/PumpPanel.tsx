import type { PumpPlan } from '../types/contract'

export const MAX_PUMPS = 50

interface Props {
  count: number
  onCount: (n: number) => void
  plan: PumpPlan | null
  nameOf: (id: string) => string
}

export function PumpPanel({ count, onCount, plan, nameOf }: Props) {
  const assigned = plan?.assignments.reduce((n, a) => n + a.pumps, 0) ?? 0
  return (
    <section className="wl-card" aria-labelledby="wl-pumps-title">
      <h2 id="wl-pumps-title">Pumps</h2>
      <label className="wl-pump-input">
        Pumps available{' '}
        <input
          type="number"
          min={0}
          max={MAX_PUMPS}
          step={1}
          value={count}
          onChange={(e) => {
            const n = Math.round(Number(e.target.value))
            if (Number.isFinite(n)) onCount(Math.min(MAX_PUMPS, Math.max(0, n)))
          }}
        />
      </label>
      {plan && (
        <>
          <p className="wl-hint" role="status">
            {assigned} of {plan.pumps_available} pumps assigned to {plan.assignments.length} spot
            {plan.assignments.length === 1 ? '' : 's'}.
          </p>
          {plan.unassigned.length > 0 && (
            <div className="wl-warn" role="alert">
              <strong>
                {plan.unassigned.length} HIGH-or-above spot{plan.unassigned.length === 1 ? '' : 's'} without a pump:
              </strong>
              <ul>
                {plan.unassigned.map((u) => (
                  <li key={u.hotspot_id}>
                    {nameOf(u.hotspot_id)} ({u.level})
                  </li>
                ))}
              </ul>
            </div>
          )}
        </>
      )}
    </section>
  )
}
