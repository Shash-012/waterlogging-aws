import { useEffect, useMemo, useState } from 'react'
import type { Replay, ReplaySummary } from '../types/contract'
import { formatIstDateTime } from '../lib/format'
import { formatHours, reportCallouts } from '../lib/replay'

// At 1× one hourly frame plays per second.
const FRAME_MS = 1000

interface Props {
  replays: ReplaySummary[]
  eventId: string | null
  onPick: (eventId: string) => void
  replay: Replay | null
  frameIndex: number
  onFrame: (i: number) => void
  nameOf: (id: string) => string
}

export function ReplayPlayer({ replays, eventId, onPick, replay, frameIndex, onFrame, nameOf }: Props) {
  const [playing, setPlaying] = useState(false)
  const [speed, setSpeed] = useState<1 | 4>(1)
  const last = replay ? replay.frames.length - 1 : 0

  useEffect(() => {
    if (!playing || !replay) return
    if (frameIndex >= last) {
      setPlaying(false)
      return
    }
    const t = setTimeout(() => onFrame(frameIndex + 1), FRAME_MS / speed)
    return () => clearTimeout(t)
  }, [playing, replay, frameIndex, last, speed, onFrame])

  const callouts = useMemo(() => (replay ? reportCallouts(replay) : []), [replay])
  const frame = replay?.frames[frameIndex]
  const visible = frame ? callouts.filter((c) => c.first_report_at <= frame.as_of) : []

  return (
    <section className="wl-card wl-replay" aria-labelledby="wl-replay-title">
      <h2 id="wl-replay-title">Replay</h2>
      <label>
        Event{' '}
        <select
          value={eventId ?? ''}
          onChange={(e) => {
            setPlaying(false)
            onPick(e.target.value)
          }}
        >
          {replays.map((r) => (
            <option key={r.event_id} value={r.event_id}>
              {r.title_en} ({r.kind})
            </option>
          ))}
        </select>
      </label>

      {replay && frame && (
        <>
          <div className="wl-replay-controls">
            <button
              type="button"
              onClick={() => {
                if (!playing && frameIndex >= last) onFrame(0)
                setPlaying(!playing)
              }}
            >
              {playing ? 'Pause' : 'Play'}
            </button>
            <button type="button" aria-pressed={speed === 4} onClick={() => setSpeed(speed === 1 ? 4 : 1)}>
              {speed}×
            </button>
            <input
              type="range"
              min={0}
              max={last}
              value={frameIndex}
              aria-label="Replay hour"
              aria-valuetext={formatIstDateTime(frame.as_of)}
              onChange={(e) => onFrame(Number(e.target.value))}
            />
          </div>
          <p className="wl-hint">
            Hour {frameIndex + 1} of {replay.frames.length} · {formatIstDateTime(frame.as_of)}
          </p>

          <dl className="wl-metrics" aria-label="Replay results">
            <div>
              <dt>Spots reported flooded</dt>
              <dd>{replay.metrics.spots_reported}</dd>
            </div>
            <div>
              <dt>Flagged HIGH before report</dt>
              <dd>{replay.metrics.flagged_before_report}</dd>
            </div>
            <div>
              <dt>Median warning</dt>
              <dd>
                {replay.metrics.median_lead_hours === null ? '—' : formatHours(replay.metrics.median_lead_hours)}
              </dd>
            </div>
            <div>
              <dt>Flags with no report found</dt>
              <dd>{replay.metrics.unconfirmed_flags}</dd>
            </div>
          </dl>

          {visible.length > 0 && (
            <ul className="wl-callouts" aria-label="Flood reports so far">
              {visible.map((c) => (
                <li key={c.hotspot_id}>
                  <strong>{nameOf(c.hotspot_id)}</strong>:{' '}
                  {c.lead_hours !== null
                    ? `Flagged HIGH ${formatHours(c.lead_hours)} before the first report`
                    : 'Not flagged HIGH before the first report'}
                  {c.note && <span className="wl-hint"> · {c.note}</span>}{' '}
                  <a href={c.source_url} target="_blank" rel="noreferrer">
                    source
                  </a>
                </li>
              ))}
            </ul>
          )}
        </>
      )}
    </section>
  )
}
