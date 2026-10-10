import type { Snapshot } from '../types/contract'
import { addHours, formatIstDateTime, formatIstTime, formatScore } from '../lib/format'

type Status = Snapshot['city']['status']

const STATUS_LABEL: Record<Status, string> = {
  STANDBY: 'Standby',
  RAIN_WATCH: 'Rain watch',
  ALERT: 'Alert',
  SEVERE: 'Severe',
}

interface Props {
  snapshot: Snapshot
  // Live snapshots refresh hourly; fixtures and replay frames don't.
  refreshes: boolean
}

export function CityBanner({ snapshot, refreshes }: Props) {
  const { status, rain_trigger_max, spots_raining } = snapshot.city
  return (
    <section className={`wl-banner wl-banner-${status.toLowerCase()}`} aria-label="City status">
      <div className="wl-banner-status">
        <span className="wl-banner-label">Delhi</span>
        <strong data-testid="city-status">{STATUS_LABEL[status]}</strong>
      </div>
      <dl className="wl-banner-facts">
        <div>
          <dt>Highest rain trigger</dt>
          <dd>{formatScore(rain_trigger_max)}</dd>
        </div>
        <div>
          <dt>Spots with rain</dt>
          <dd>{spots_raining}</dd>
        </div>
        <div>
          <dt>As of</dt>
          <dd>{formatIstDateTime(snapshot.as_of)}</dd>
        </div>
        {refreshes && (
          <div>
            <dt>Next update</dt>
            <dd>about {formatIstTime(addHours(snapshot.as_of, 1))}</dd>
          </div>
        )}
      </dl>
    </section>
  )
}
