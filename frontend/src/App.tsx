import { useCallback, useEffect, useMemo, useState } from 'react'
import { dataSource, getHotspots, getLatestSnapshot, postAlert } from './api/client'
import { CityBanner } from './components/CityBanner'
import { DetailPanel, type AlertState } from './components/DetailPanel'
import { HotspotList, type Lang, type Row } from './components/HotspotList'
import { HotspotMap } from './components/HotspotMap'
import type { Hotspot, Snapshot } from './types/contract'

const LIVE_POLL_MS = 5 * 60_000

export default function App() {
  const [hotspots, setHotspots] = useState<Hotspot[] | null>(null)
  const [snapshot, setSnapshot] = useState<Snapshot | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [lang, setLang] = useState<Lang>('en')
  const [sample, setSample] = useState<'live' | 'dry'>('live')
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [alert, setAlert] = useState<AlertState>({ kind: 'idle' })

  useEffect(() => {
    getHotspots()
      .then(setHotspots)
      .catch((e: unknown) => setError(e instanceof Error ? e.message : String(e)))
  }, [])

  useEffect(() => {
    let cancelled = false
    const load = () =>
      getLatestSnapshot(sample)
        .then((s) => !cancelled && setSnapshot(s))
        .catch((e: unknown) => !cancelled && setError(e instanceof Error ? e.message : String(e)))
    load()
    const timer = dataSource === 'live' ? setInterval(load, LIVE_POLL_MS) : undefined
    return () => {
      cancelled = true
      clearInterval(timer)
    }
  }, [sample])

  const scores = useMemo(
    () => new Map((snapshot?.hotspots ?? []).map((s) => [s.hotspot_id, s])),
    [snapshot],
  )

  const rows: Row[] = useMemo(() => {
    if (!hotspots || !snapshot) return []
    const byId = new Map(hotspots.map((h) => [h.hotspot_id, h]))
    return [...snapshot.hotspots]
      .sort((a, b) => a.rank - b.rank)
      .flatMap((score) => {
        const hotspot = byId.get(score.hotspot_id)
        return hotspot ? [{ hotspot, score }] : []
      })
  }, [hotspots, snapshot])

  const selected = rows.find((r) => r.hotspot.hotspot_id === selectedId) ?? null

  const select = useCallback((id: string | null) => {
    setSelectedId(id)
    setAlert({ kind: 'idle' })
  }, [])

  const sendAlert = useCallback(async () => {
    if (!selected || !snapshot) return
    setAlert({ kind: 'sending' })
    try {
      const res = await postAlert({
        hotspot_id: selected.hotspot.hotspot_id,
        run_id: snapshot.run_id,
        mode: snapshot.mode,
        event_id: null,
        level: selected.score.level,
        risk: selected.score.risk,
        peak_at: selected.score.peak_at,
      })
      setAlert({ kind: 'sent', duplicate: res.duplicate, text: lang === 'hi' ? res.text_hi : res.text_en })
    } catch (e: unknown) {
      setAlert({ kind: 'error', message: e instanceof Error ? e.message : String(e) })
    }
  }, [selected, snapshot, lang])

  return (
    <div className="wl-app">
      <header className="wl-header">
        <h1>Delhi Waterlogging Early Warning</h1>
        <div className="wl-controls">
          {dataSource === 'fixtures' && (
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
        </div>
      </header>

      {error && <p role="alert" className="wl-error">Could not load data: {error}</p>}
      {!error && (!hotspots || !snapshot) && <p className="wl-loading">Loading…</p>}

      {hotspots && snapshot && (
        <>
          <CityBanner snapshot={snapshot} refreshes={dataSource === 'live'} />
          <main className="wl-main">
            <div className="wl-map-wrap">
              <p className="wl-count">
                {hotspots.length} hotspots · data: {dataSource}
              </p>
              <HotspotMap hotspots={hotspots} scores={scores} selectedId={selectedId} onSelect={select} />
            </div>
            <aside className="wl-side">
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
                />
              )}
            </aside>
          </main>
        </>
      )}
    </div>
  )
}
