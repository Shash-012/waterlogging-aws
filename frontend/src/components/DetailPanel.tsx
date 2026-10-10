import type { Hotspot, SnapshotHotspot } from '../types/contract'
import { formatIstTime, formatScore, relativePeak } from '../lib/format'
import type { Lang } from './HotspotList'
import { LevelChip } from './LevelChip'

function Bar({ label, value, detail }: { label: string; value: number; detail?: string }) {
  return (
    <div className="wl-bar">
      <div className="wl-bar-head">
        <span>{label}</span>
        <span>{formatScore(value)}</span>
      </div>
      <div
        className="wl-bar-track"
        role="meter"
        aria-label={label}
        aria-valuemin={0}
        aria-valuemax={1}
        aria-valuenow={value}
      >
        <div className="wl-bar-fill" style={{ width: `${Math.round(value * 100)}%` }} />
      </div>
      {detail && <div className="wl-bar-detail">{detail}</div>}
    </div>
  )
}

export type AlertState =
  | { kind: 'idle' }
  | { kind: 'sending' }
  | { kind: 'sent'; duplicate: boolean; text: string }
  | { kind: 'error'; message: string }

interface Props {
  hotspot: Hotspot
  score: SnapshotHotspot
  asOf: string
  lang: Lang
  onClose: () => void
  onSendAlert: () => void
  alert: AlertState
}

export function DetailPanel({ hotspot, score, asOf, lang, onClose, onSendAlert, alert }: Props) {
  const canAlert = score.level === 'HIGH' || score.level === 'CRITICAL'
  const hi = lang === 'hi'
  return (
    <section className="wl-detail" aria-labelledby="wl-detail-title">
      <header className="wl-detail-head">
        <h2 id="wl-detail-title" lang={lang}>
          {hi ? hotspot.name_hi : hotspot.name_en}
        </h2>
        <button type="button" className="wl-link" onClick={onClose}>
          Close
        </button>
      </header>
      <p className="wl-detail-summary">
        <LevelChip level={score.level} /> risk {formatScore(score.risk)} · rank {score.rank} · peak{' '}
        {score.peak_at ? `${formatIstTime(score.peak_at)} (${relativePeak(score.peak_at, asOf)})` : 'none forecast'}
      </p>

      <h3>Why this level?</h3>
      <p className="wl-explain">
        Risk = rain trigger {formatScore(score.rain_trigger)} × susceptibility {formatScore(score.susceptibility)}
      </p>
      <Bar
        label="Rain trigger"
        value={score.rain_trigger}
        detail={`${score.intensity_mm_h} mm/h forecast peak · ${score.rain_24h_mm} mm in last 24 h · effective ${score.effective_intensity_mm_h} mm/h`}
      />
      <Bar
        label="Flood history"
        value={hotspot.factors.history}
        detail={`${hotspot.flood_seasons} of the last monsoon seasons with reports`}
      />
      <Bar
        label="Low-lying"
        value={hotspot.factors.low_lying}
        detail={`${hotspot.relative_depth_m} m below its surroundings`}
      />
      <Bar
        label="Catchment"
        value={hotspot.factors.catchment}
        detail={`${hotspot.catchment_km2} km² drains here`}
      />

      <h3>{hi ? 'बचें' : 'Avoid'}</h3>
      <p lang={lang}>{hi ? hotspot.avoid_hi : hotspot.avoid_en}</p>
      <h3>{hi ? 'वैकल्पिक मार्ग' : 'Diversion'}</h3>
      <p lang={lang}>{hi ? hotspot.diversion_hi : hotspot.diversion_en}</p>

      <div className="wl-alert">
        <button
          type="button"
          className="wl-primary"
          disabled={!canAlert || alert.kind === 'sending'}
          onClick={onSendAlert}
        >
          {alert.kind === 'sending' ? 'Sending…' : 'Send alert'}
        </button>
        {!canAlert && <p className="wl-hint">Alerts can be sent at HIGH or CRITICAL.</p>}
        {alert.kind === 'sent' && (
          <p role="status" className="wl-hint">
            {alert.duplicate ? 'Already sent in the last 30 minutes: ' : 'Sent: '}
            {alert.text}
          </p>
        )}
        {alert.kind === 'error' && (
          <p role="alert" className="wl-error">
            Could not send: {alert.message}
          </p>
        )}
      </div>

      <p className="wl-sources">
        Sources:{' '}
        {hotspot.sources.map((s, i) => (
          <a key={s} href={s} target="_blank" rel="noreferrer">
            [{i + 1}]
          </a>
        ))}
      </p>
    </section>
  )
}
