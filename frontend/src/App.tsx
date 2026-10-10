import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  ApiError,
  dataSource,
  getHotspots,
  getLatestSnapshot,
  getPumpPlan,
  getReplay,
  getReplays,
  postAlert,
} from './api/client'
import { useAuth } from './auth/context'
import { CityBanner } from './components/CityBanner'
import { DetailPanel, type AlertState } from './components/DetailPanel'
import { HotspotList, type Lang, type Row } from './components/HotspotList'
import { HotspotMap, type ReportPin } from './components/HotspotMap'
import { PumpPanel } from './components/PumpPanel'
import { ReplayPlayer } from './components/ReplayPlayer'
import type { Hotspot, PumpPlan, Replay, ReplaySummary, Snapshot } from './types/contract'
import { formatIstDateTime } from './lib/format'
import { readPresentMode } from './lib/present'
import { planPumps } from './lib/pumps'
import { replayLabel } from './lib/replay'

const LIVE_POLL_MS = 5 * 60_000
const DEFAULT_PUMPS = 6

type View = 'now' | 'replay'

const message = (e: unknown) => (e instanceof Error ? e.message : String(e))

export default function App() {
  const [{ present, eventId: requestedEvent }] = useState(() => readPresentMode(window.location.search))
  const { session, signOut } = useAuth()
  const [hotspots, setHotspots] = useState<Hotspot[] | null>(null)
  const [latest, setLatest] = useState<Snapshot | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [lang, setLang] = useState<Lang>('en')
  const [sample, setSample] = useState<'live' | 'dry'>('live')
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [alert, setAlert] = useState<AlertState>({ kind: 'idle' })

  const [view, setView] = useState<View>(requestedEvent ? 'replay' : 'now')
  const [pumpCount, setPumpCount] = useState(DEFAULT_PUMPS)
  const [pumpPlan, setPumpPlan] = useState<PumpPlan | null>(null)

  const [replays, setReplays] = useState<ReplaySummary[]>([])
  const [eventId, setEventId] = useState<string | null>(requestedEvent)
  const [replay, setReplay] = useState<Replay | null>(null)
  const [frameIndex, setFrameIndex] = useState(0)

  useEffect(() => {
    getHotspots().then(setHotspots).catch((e) => setError(message(e)))
  }, [])

  useEffect(() => {
    let cancelled = false
    const load = () =>
      getLatestSnapshot(sample)
        .then((s) => !cancelled && setLatest(s))
        .catch((e) => !cancelled && setError(message(e)))
    load()
    const timer = dataSource === 'live' ? setInterval(load, LIVE_POLL_MS) : undefined
    return () => {
      cancelled = true
      clearInterval(timer)
    }
  }, [sample])

  // Refetch the plan when the count or the underlying snapshot changes.
  useEffect(() => {
    let cancelled = false
    getPumpPlan(pumpCount, sample)
      .then((p) => !cancelled && setPumpPlan(p))
      .catch((e) => !cancelled && setError(message(e)))
    return () => {
      cancelled = true
    }
  }, [pumpCount, sample, latest?.run_id])

  useEffect(() => {
    if (view !== 'replay' || replays.length) return
    getReplays()
      .then((list) => {
        setReplays(list)
        // Fall back to the first storm when no event (or an unknown one) was asked for.
        if (list.length && !list.some((r) => r.event_id === eventId)) {
          setEventId((list.find((r) => r.kind === 'storm') ?? list[0]).event_id)
        }
      })
      .catch((e) => setError(message(e)))
  }, [view, replays.length, eventId])

  useEffect(() => {
    if (!eventId || !replays.some((r) => r.event_id === eventId)) return
    let cancelled = false
    setReplay(null)
    getReplay(eventId)
      .then((r) => {
        if (cancelled) return
        setReplay(r)
        setFrameIndex(0)
      })
      .catch((e) => !cancelled && setError(message(e)))
    return () => {
      cancelled = true
    }
  }, [eventId, replays])

  const inReplay = view === 'replay'
  const snapshot: Snapshot | null = inReplay ? (replay?.frames[frameIndex] ?? null) : latest

  const byId = useMemo(() => new Map((hotspots ?? []).map((h) => [h.hotspot_id, h])), [hotspots])
  const nameOf = useCallback(
    (id: string) => {
      const h = byId.get(id)
      return h ? (lang === 'hi' ? h.name_hi : h.name_en) : id
    },
    [byId, lang],
  )

  const scores = useMemo(
    () => new Map((snapshot?.hotspots ?? []).map((s) => [s.hotspot_id, s])),
    [snapshot],
  )

  const rows: Row[] = useMemo(() => {
    if (!snapshot) return []
    return [...snapshot.hotspots]
      .sort((a, b) => a.rank - b.rank)
      .flatMap((score) => {
        const hotspot = byId.get(score.hotspot_id)
        return hotspot ? [{ hotspot, score }] : []
      })
  }, [byId, snapshot])

  // GET /pumps only covers the latest run, so a replay hour uses the contract's
  // pump rule on that frame (see handoff/requests-b.md).
  const activePlan: PumpPlan | null = useMemo(() => {
    if (!inReplay) return pumpPlan
    return snapshot && hotspots ? planPumps(snapshot, hotspots, pumpCount) : null
  }, [inReplay, pumpPlan, snapshot, hotspots, pumpCount])

  const pumpsById = useMemo(
    () => (activePlan ? new Map(activePlan.assignments.map((a) => [a.hotspot_id, a.pumps])) : undefined),
    [activePlan],
  )

  // Ground-truth reports appear on the map once the replay reaches their time.
  const reports: ReportPin[] | undefined = useMemo(() => {
    if (!inReplay || !replay || !snapshot) return undefined
    return replay.ground_truth
      .filter((g) => g.first_report_at <= snapshot.as_of)
      .map((g) => ({
        hotspot_id: g.hotspot_id,
        label: `Reported flooded at ${formatIstDateTime(g.first_report_at)}`,
      }))
  }, [inReplay, replay, snapshot])

  const selected = rows.find((r) => r.hotspot.hotspot_id === selectedId) ?? null

  const select = useCallback((id: string | null) => {
    setSelectedId(id)
    setAlert({ kind: 'idle' })
  }, [])

  const switchView = (v: View) => {
    setView(v)
    setAlert({ kind: 'idle' })
  }

  const sendAlert = useCallback(async () => {
    if (!selected || !snapshot) return
    setAlert({ kind: 'sending' })
    try {
      const res = await postAlert({
        hotspot_id: selected.hotspot.hotspot_id,
        run_id: snapshot.run_id,
        mode: snapshot.mode,
        event_id: snapshot.mode === 'replay' ? eventId : null,
        level: selected.score.level,
        risk: selected.score.risk,
        peak_at: selected.score.peak_at,
      }, session?.idToken)
      setAlert({ kind: 'sent', duplicate: res.duplicate, text: lang === 'hi' ? res.text_hi : res.text_en })
    } catch (e: unknown) {
      // The ops API rejected the token (expired or revoked): sign in again.
      if (e instanceof ApiError && e.status === 401) signOut()
      else setAlert({ kind: 'error', message: message(e) })
    }
  }, [selected, snapshot, eventId, lang, session, signOut])

  return (
    <div className={present ? 'wl-app wl-present' : 'wl-app'}>
      <header className="wl-header">
        <h1>Delhi Waterlogging Early Warning</h1>
        <div className="wl-controls">
          <div className="wl-tabs" role="group" aria-label="View">
            <button type="button" aria-pressed={!inReplay} onClick={() => switchView('now')}>
              Now
            </button>
            <button type="button" aria-pressed={inReplay} onClick={() => switchView('replay')}>
              Replay
            </button>
          </div>
          {dataSource === 'fixtures' && !inReplay && !present && (
            <label>
              Sample{' '}
              <select value={sample} onChange={(e) => setSample(e.target.value as 'live' | 'dry')}>
                <option value="live">Rainy</option>
                <option value="dry">Dry</option>
              </select>
            </label>
          )}
          <button
            type="button"
            className="wl-toggle"
            aria-label={lang === 'en' ? 'Show Hindi names' : 'Show English names'}
            onClick={() => setLang(lang === 'en' ? 'hi' : 'en')}
          >
            {lang === 'en' ? 'हिंदी' : 'English'}
          </button>
          {session && (
            <span className="wl-user">
              Signed in as <strong>{session.username}</strong>{' '}
              <button type="button" className="wl-link" onClick={signOut}>
                Sign out
              </button>
            </span>
          )}
        </div>
      </header>

      {inReplay && eventId && (
        <p className="wl-replay-label" role="note">
          {replayLabel(eventId)}
        </p>
      )}

      {error && <p role="alert" className="wl-error">Could not load data: {error}</p>}
      {!error && (!hotspots || !snapshot) && <p className="wl-loading">Loading…</p>}

      {hotspots && snapshot && (
        <>
          <CityBanner snapshot={snapshot} refreshes={dataSource === 'live' && !inReplay} />
          <main className="wl-main">
            <div className="wl-map-wrap">
              {!present && (
                <p className="wl-count">
                  {hotspots.length} hotspots · data: {dataSource}
                </p>
              )}
              <HotspotMap
                hotspots={hotspots}
                scores={scores}
                selectedId={selectedId}
                onSelect={select}
                pumpsById={pumpsById}
                reports={reports}
              />
            </div>
            <aside className="wl-side">
              {inReplay && (
                <ReplayPlayer
                  replays={replays}
                  eventId={eventId}
                  onPick={setEventId}
                  replay={replay}
                  frameIndex={frameIndex}
                  onFrame={setFrameIndex}
                  nameOf={nameOf}
                />
              )}
              <PumpPanel
                count={pumpCount}
                onCount={setPumpCount}
                plan={activePlan}
                nameOf={nameOf}
                note={inReplay ? 'For the replay hour shown' : undefined}
              />
              {selected ? (
                <DetailPanel
                  hotspot={selected.hotspot}
                  score={selected.score}
                  asOf={snapshot.as_of}
                  lang={lang}
                  onClose={() => select(null)}
                  onSendAlert={sendAlert}
                  alert={alert}
                />
              ) : (
                <HotspotList
                  rows={rows}
                  asOf={snapshot.as_of}
                  lang={lang}
                  selectedId={selectedId}
                  onSelect={select}
                  pumpsById={pumpsById}
                />
              )}
            </aside>
          </main>
        </>
      )}
    </div>
  )
}
